# -*- coding: utf-8 -*-
"""发送后验证：核对会话列表里的实际送达内容（只读）。

用户要求「发送后必须核对实际送达」——不轻信脚本返回值。
检查每条目标的会话列表项：
  - 是否含我们发出的定制文案（「您好，看到「…」这个岗位」）
  - 文案里的岗位名是否与预期一致
  - 是否仍是默认招呼语（说明定制文案没发出去）
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from send_paced import RelayCDP, Sender, clean_job  # noqa: E402

TARGETS = sys.argv[1] if len(sys.argv) > 1 else "send_new_fde.json"


def main():
    cdp = RelayCDP()
    cdp.ensure_focus()
    cdp.send("Page.navigate", {"url": "https://www.zhipin.com/web/geek/chat"})
    for _ in range(16):
        time.sleep(1.2)
        if cdp.val("document.querySelectorAll('.friend-content-warp').length"):
            break
    s = Sender(cdp, dry_run=True, skip_open=True)
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
    convs = list(seen.values())
    print(f"会话快照: {len(convs)} 条\n")

    targets = json.load(open(TARGETS, encoding="utf-8"))
    ok_list, default_only, missing = [], [], []

    for x in targets:
        brand = (x.get("brand") or "").strip()
        job = clean_job(x.get("jobName") or "")
        key_brand = brand if not brand.startswith("某") else None
        hit = None
        if key_brand:
            cand = [c for c in convs if key_brand in c]
            # 优先含岗位名前 10 字的
            for c in cand:
                if job and job[:10] in c:
                    hit = c
                    break
            if hit is None and cand:
                hit = cand[0]
        else:
            cand = [c for c in convs if job and job[:12] in c]
            hit = cand[0] if cand else None

        if hit is None:
            missing.append((x, None))
            continue
        if "您好，看到" in hit:
            # 提取文档里的岗位名，核对是否一致
            m = re.search(r"您好，看到「([^」]*)」", hit)
            sent_job = m.group(1) if m else ""
            ok_list.append((x, hit, sent_job))
        else:
            default_only.append((x, hit))

    print("=" * 84)
    print(f"✅ 已送达定制文案: {len(ok_list)}")
    print("=" * 84)
    for x, hit, sent_job in ok_list:
        flag = "" if sent_job and (sent_job[:8] in clean_job(x.get("jobName") or "")
                                   or clean_job(x.get("jobName") or "")[:8] in sent_job) else "  ⚠️岗位名不一致"
        print(f"  {x.get('brand')} | 文案内岗位「{sent_job[:34]}」{flag}")

    print()
    print("=" * 84)
    print(f"⚠️ 仍是默认招呼语（定制文案未送达）: {len(default_only)}")
    print("=" * 84)
    for x, hit in default_only:
        print(f"  {x.get('brand')} | {hit[:90]}")

    print()
    print("=" * 84)
    print(f"❌ 未在会话列表找到: {len(missing)}")
    print("=" * 84)
    for x, _ in missing:
        print(f"  {x.get('brand')} | {(x.get('jobName') or '')[:40]}")

    summary = {"sent": [x.get("brand") for x, _, _ in ok_list],
               "default_only": [x.get("brand") for x, _ in default_only],
               "missing": [x.get("brand") for x, _ in missing]}
    json.dump(summary, open("verify_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n明细已写入 verify_result.json")


if __name__ == "__main__":
    main()
