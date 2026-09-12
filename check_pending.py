# -*- coding: utf-8 -*-
"""按岗位名核对目标是否已联系（只读）。

原理：我们发出的定制文案含「岗位名」，且 BOSS 列表项会显示最后一条消息。
若列表项文本里出现该岗位名，说明已联系过。

用途：从中断的批量发送中恢复，精确算出剩余待发，避免重复。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from send_paced import RelayCDP, Sender, clean_job  # noqa: E402


def collect_all(s):
    s.scroll_to_top()
    info = s._scroller()
    rounds = int(info["sh"] / info["ch"]) + 6 if info and info.get("ch") else 30
    seen = {}
    for _ in range(rounds):
        for t in s.list_convs():
            if t:
                seen[t[:110]] = t
        if s.scroll_list():
            for t in s.list_convs():
                if t:
                    seen[t[:110]] = t
            break
        time.sleep(0.6)
    return list(seen.values())


def main():
    cdp = RelayCDP()
    cdp.send("Page.navigate", {"url": "https://www.zhipin.com/web/geek/chat"})
    for _ in range(16):
        time.sleep(1.2)
        if cdp.val("document.querySelectorAll('.friend-content-warp').length"):
            break
    s = Sender(cdp, dry_run=True, skip_open=True)
    convs = collect_all(s)
    blob = "\n".join(convs)
    print(f"会话 {len(convs)} 条\n")

    targets = json.load(open("send_new_fde.json", encoding="utf-8"))
    sent, pending = [], []
    for x in targets:
        job = clean_job(x.get("jobName") or "")
        brand = x.get("brand") or ""
        # 岗位名（取前 12 字做匹配，避开截断差异）
        key = job[:12]
        hit_job = bool(key) and key in blob
        hit_brand = bool(brand) and not brand.startswith("某") and brand in blob
        if hit_job or hit_brand:
            sent.append(x)
        else:
            pending.append(x)

    print("=" * 80)
    print(f"已联系: {len(sent)}   待发: {len(pending)}")
    print("=" * 80)
    print("\n【已联系（跳过，避免重复）】")
    for x in sent:
        print(f"  ✅ {x.get('brand')} | {(x.get('jobName') or '')[:40]}")
    print("\n【待发】")
    for x in pending:
        print(f"  ⬜ {x.get('brand')} | {(x.get('jobName') or '')[:40]}")

    json.dump(pending, open("send_new_pending.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n待发清单已写入 send_new_pending.json（{len(pending)} 条）")


if __name__ == "__main__":
    main()
