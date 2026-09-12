# -*- coding: utf-8 -*-
"""完整采集 FDE 岗位（增量保存 + 断点续采）。

此前的问题：
  1. collect_search.py 用 MAX_SCROLL=10，只取到 165 条就停了；
     实测单查询上限是 **196 条**（再滚不再增加，且无「没有更多」提示 = 服务端硬截断）。
  2. `&page=N` 参数**无效**：page=1/2/3 返回完全相同的 196 条。
  3. 长任务里单次 CDP 命令可能超时，导致整轮白跑 —— 故改为逐关键词落盘。

策略：用细分关键词切分查询，每个查询独立返回一批，突破单查询上限。
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

CITY = "101210100"
KEYWORDS = [
    "fde", "FDE工程师", "FDE交付", "FDE解决方案", "FDE实施",
    "前沿部署", "前线部署", "前向部署", "forward deployed",
    "AI交付工程师", "AI实施工程师", "AI落地工程师",
    "大模型交付", "AI解决方案工程师", "智能体交付",
    "Agent工程师", "AI应用交付", "AI项目交付",
]
GAP = 8
MAX_SCROLL = 24
OUT = "fde_all.json"
STATE = "fde_collect_state.json"


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding="utf-8"))
        except Exception:
            pass
    return {"done": [], "jobs": {}}


def save_state(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)


def safe(fn, *a, retries=2, **kw):
    """CDP 命令可能超时，重试。"""
    last = None
    for _ in range(retries + 1):
        try:
            return fn(*a, **kw)
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def collect_one(cdp, kw):
    url = (f"https://www.zhipin.com/web/geek/jobs?city={CITY}"
           f"&query={urllib.parse.quote(kw)}")
    safe(cdp.send, "Page.navigate", {"url": url})
    loaded = False
    for _ in range(16):
        time.sleep(1.2)
        try:
            if cdp.val("document.querySelectorAll('li.job-card-box').length"):
                loaded = True
                break
        except Exception:
            continue
    if not loaded:
        return None, "load_fail"

    try:
        body = cdp.val("document.body.innerText.slice(0,400)")
        risk = is_risk_signal(cdp.val("location.href"), body)
    except Exception:
        risk = None
    if risk:
        return None, f"risk:{risk}"

    cards = {}
    stall = 0
    for i in range(MAX_SCROLL):
        try:
            d = read_job_cards(cdp)
        except Exception:
            d = None
        if d:
            for c in d.get("cards") or []:
                if c.get("eid"):
                    cards[c["eid"]] = c
        n0 = len(cards)
        try:
            cdp.send("Runtime.evaluate", {
                "expression": "window.scrollTo(0, document.documentElement.scrollHeight)"})
        except Exception:
            pass
        time.sleep(1.5)
        try:
            d2 = read_job_cards(cdp)
        except Exception:
            d2 = None
        if d2:
            for c in d2.get("cards") or []:
                if c.get("eid"):
                    cards[c["eid"]] = c
        if len(cards) == n0 and i >= 3:
            stall += 1
            if stall >= 2:
                break
        else:
            stall = 0
    return cards, "ok"


def main():
    st = load_state()
    cdp = RelayCDP()
    todo = [k for k in KEYWORDS if k not in st["done"]]
    print(f"关键词 {len(KEYWORDS)} 个，已完成 {len(st['done'])}，待采 {len(todo)}")
    print(f"已有岗位 {len(st['jobs'])} 条\n")

    for i, kw in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] 「{kw}」", end=" ", flush=True)
        try:
            cards, note = collect_one(cdp, kw)
        except Exception as e:
            print(f"× 异常 {str(e)[:50]}")
            continue
        if cards is None:
            print(f"× {note}")
            if note.startswith("risk"):
                print("   ⛔ 风控，停止")
                break
            st["done"].append(kw)
            save_state(st)
            continue
        new = 0
        for eid, c in cards.items():
            if eid not in st["jobs"]:
                st["jobs"][eid] = {**c, "kw": kw}
                new += 1
        st["done"].append(kw)
        save_state(st)
        print(f"{len(cards)} 条，新增 {new}，累计 {len(st['jobs'])}")
        json.dump(list(st["jobs"].values()), open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        time.sleep(GAP)

    # 汇总 FDE
    MARKS = ["fde", "前沿部署", "前线部署", "前向部署", "forward deployed"]
    jobs = list(st["jobs"].values())
    fde = [j for j in jobs
           if any(k in (j.get("jobName") or "").lower() for k in MARKS)]
    seen, uniq = set(), []
    for j in fde:
        key = (j.get("company"), j.get("jobName"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)
    json.dump(uniq, open("fde_jobs_all.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n" + "=" * 78)
    print(f"采集岗位总数: {len(jobs)}")
    print(f"标题为 FDE/前沿部署: {len(fde)}（公司+岗位去重后 {len(uniq)}）")
    print("=" * 78)
    print(f"已写入 {OUT} / fde_jobs_all.json")


if __name__ == "__main__":
    main()
