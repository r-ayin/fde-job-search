# -*- coding: utf-8 -*-
"""搜集二：搜索页新岗位（DOM 零请求读取）。

用多个关键词搜索杭州 FDE/AI 相关岗位，滚动加载后读取全部岗位卡。
全程只发"页面导航"（真人浏览同样会发），不发任何接口调用。
每个关键词之间固定间隔，避免频率特征。
"""
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from dom_tools import read_job_cards  # noqa: E402
from pacing import is_risk_signal  # noqa: E402
from send_paced import RelayCDP  # noqa: E402

CITY = "101210100"      # 杭州
KEYWORDS = ["fde", "前沿部署", "前线部署", "AI应用工程师", "AI解决方案",
            "AI交付", "大模型应用", "AI Agent"]
GAP = 12                # 关键词间隔（秒）
MAX_SCROLL = 10         # 每个关键词最多滚动次数


def scroll_and_read(cdp, max_scroll=MAX_SCROLL):
    """滚动加载并读取岗位卡，返回去重后的列表。"""
    seen = {}
    for i in range(max_scroll):
        d = read_job_cards(cdp)
        if not d:
            break
        for c in d.get("cards") or []:
            if c.get("eid"):
                seen[c["eid"]] = c
        if d.get("hasNoMore"):
            break
        cdp.send("Runtime.evaluate", {
            "expression": "window.scrollTo(0, document.documentElement.scrollHeight)"})
        time.sleep(1.5)
        n_before = len(seen)
        d2 = read_job_cards(cdp)
        if d2:
            for c in d2.get("cards") or []:
                if c.get("eid"):
                    seen[c["eid"]] = c
        if len(seen) == n_before and i >= 2:
            break
    return list(seen.values())


def main():
    cdp = RelayCDP()
    all_jobs = {}
    for idx, kw in enumerate(KEYWORDS, 1):
        url = (f"https://www.zhipin.com/web/geek/jobs?city={CITY}"
               f"&query={urllib.parse.quote(kw)}")
        print(f"\n[{idx}/{len(KEYWORDS)}] 关键词「{kw}」")
        cdp.send("Page.navigate", {"url": url})
        ok = False
        for _ in range(14):
            time.sleep(1.2)
            n = cdp.val("document.querySelectorAll('li.job-card-box').length")
            if n:
                ok = True
                break
        if not ok:
            print("   × 未加载出岗位卡")
            continue
        # 风控检查
        body = cdp.val("document.body.innerText.slice(0,400)")
        url_now = cdp.val("location.href")
        risk = is_risk_signal(url_now, body)
        if risk:
            print(f"   ⛔ 风控信号 {risk}，停止搜集")
            break

        cards = scroll_and_read(cdp)
        new = 0
        for c in cards:
            if c["eid"] not in all_jobs:
                all_jobs[c["eid"]] = {**c, "kw": kw}
                new += 1
        print(f"   读到 {len(cards)} 条，新增 {new}，累计 {len(all_jobs)}")
        if idx < len(KEYWORDS):
            time.sleep(GAP)

    json.dump(list(all_jobs.values()), open("search_new.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n{'=' * 70}")
    print(f"搜集完成：{len(all_jobs)} 个岗位，已写入 search_new.json")
    print(f"{'=' * 70}")

    # 与已有岗位对比
    known = set()
    for f in ["jd_final.json", "jd_search_final.json", "fde_candidates2.json",
              "send_targets.json", "sent_2026-09-11.json"]:
        try:
            d = json.load(open(f, encoding="utf-8"))
            items = d.values() if isinstance(d, dict) else d
            for x in items:
                e = x.get("encryptJobId") or x.get("eid")
                if e:
                    known.add(e)
        except Exception:
            pass
    fresh = [j for j in all_jobs.values() if j["eid"] not in known]
    print(f"\n已有库对照：已知 {len(known)} 个 | 新发现 {len(fresh)} 个")
    for j in fresh[:40]:
        print(f"  [{j['kw']}] {j.get('company')} | {j.get('jobName')} | {j.get('salary')}")
    json.dump(fresh, open("search_fresh.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
