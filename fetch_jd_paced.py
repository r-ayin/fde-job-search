# -*- coding: utf-8 -*-
"""低频 JD 抓取：真实导航 + DOM 读取。

为什么换成这个（对比 fetch_fde_jd2.py）：
  fetch_fde_jd2.py 走 /wapi/zpgeek/job/detail.json 直接 fetch，间隔 7s，
  结果 36 个全部返回 code:37「您的环境存在异常」——接口直调是封禁的直接推手。
  本脚本改用 Page.navigate 打开 job_detail 页面再读 DOM：
    1) 服务端看到的是正常的页面浏览（真人也会点开岗位详情）
    2) DOM 读取走 Runtime.evaluate，零网络请求
    3) 间隔放大到 15~25s 随机，单轮上限 30

风控处理：
  - 每次抓取后检查页面/响应里的风控信号，命中即熔断落盘
  - 熔断后必须人工确认（删除 jd_state.json 或 --reset）才能继续
"""
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from pacing import is_risk_signal  # noqa: E402
from send_paced import RelayCDP  # noqa: E402

STATE = "jd_state.json"
DEFAULT_MIN_GAP = 15.0
DEFAULT_MAX_GAP = 25.0
DEFAULT_CAP = 30

# 只读 DOM，不发网络请求
EXTRACT = r"""
(() => {
  const g = s => document.querySelector(s);
  const txt = el => el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : '';
  const body = (document.body.innerText || '');
  return JSON.stringify({
    url: location.href,
    bodyHead: body.slice(0, 500),
    ok: !!g('.job-sec-text'),
    title: txt(g('.name h1') || g('h1')),
    salary: txt(g('.salary')),
    company: txt(g('.sider-company .company-info') || g('.sider-company .name') || g('.company-info .name')),
    desc: txt(g('.job-sec-text')),
    tags: [...document.querySelectorAll('.job-keyword-list li')].map(e => txt(e)).filter(Boolean),
    expEdu: txt(g('.job-primary .text') || g('.info-primary p'))
  });
})()
"""


class JDState:
    def __init__(self, path=STATE, cap=DEFAULT_CAP):
        self.path, self.cap = path, cap
        self.data = {"date": time.strftime("%Y-%m-%d"), "fetched": 0, "tripped": None}
        if os.path.exists(path):
            try:
                d = json.load(open(path, encoding="utf-8"))
                if d.get("date") == self.data["date"]:
                    self.data = d
                elif d.get("tripped"):
                    # 换天了但还处于熔断状态，保留熔断标记
                    self.data["tripped"] = d["tripped"]
            except Exception:
                pass

    @property
    def fetched(self):
        return self.data.get("fetched", 0)

    @property
    def tripped(self):
        return self.data.get("tripped")

    def bump(self):
        self.data["fetched"] = self.fetched + 1
        self.save()

    def trip(self, reason):
        self.data["tripped"] = str(reason)
        self.save()
        print(f"⛔ 熔断：{reason}")

    def reset(self):
        self.data["tripped"] = None
        self.save()

    def save(self):
        json.dump(self.data, open(self.path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("todo", nargs="?", default="fde_todo2.json")
    ap.add_argument("--out", default="fde_jd_vision.json")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--min-gap", type=float, default=DEFAULT_MIN_GAP)
    ap.add_argument("--max-gap", type=float, default=DEFAULT_MAX_GAP)
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--reset", action="store_true", help="清除熔断状态")
    args = ap.parse_args()

    st = JDState(cap=args.cap)
    if args.reset:
        st.reset()
        print("已清除熔断状态")

    if st.tripped:
        print(f"⛔ 当前处于熔断状态（{st.tripped}）。确认账号正常后用 --reset 清除。")
        return

    todo = json.load(open(args.todo, encoding="utf-8"))
    res = json.load(open(args.out, encoding="utf-8")) if os.path.exists(args.out) else []
    done = {x["eid"] for x in res if x.get("desc")}
    remain = [t for t in todo if t["eid"] not in done]

    allow = min(args.limit, args.cap - st.fetched)
    if allow <= 0:
        print(f"今日已达上限 {st.fetched}/{st.cap}，停止")
        return
    print(f"待抓 {len(remain)} | 本次抓 {allow} | 今日已抓 {st.fetched}/{st.cap} | "
          f"间隔 {args.min_gap:.0f}~{args.max_gap:.0f}s")

    cdp = RelayCDP()
    batch = remain[:allow]
    for i, t in enumerate(batch):
        eid = t["eid"]
        print(f"\n[{i+1}/{len(batch)}] {t.get('brandName') or t.get('brand')} | "
              f"{(t.get('jobName') or '')[:26]}")
        d = None
        try:
            cdp.send("Page.navigate",
                     {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
            for _ in range(14):
                time.sleep(1.2)
                raw = cdp.val(EXTRACT)
                if not raw:
                    continue
                d = json.loads(raw)
                if d.get("ok") and eid in (d.get("url") or "") and d.get("title"):
                    break
        except Exception as e:
            d = {"ok": False, "err": str(e)[:90]}
        if not d:
            d = {"ok": False, "err": "no_response"}

        risk = is_risk_signal(d.get("url"), d.get("bodyHead"), d.get("err"))
        if risk:
            st.trip(f"命中风控信号 {risk}（第 {i+1} 个）")
            d.update({"eid": eid, "num": i + 1})
            res.append(d)
            json.dump(res, open(args.out, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            break

        d["eid"] = eid
        d["listName"] = t.get("jobName")
        d["listBrand"] = t.get("brandName") or t.get("brand")
        res.append(d)
        st.bump()
        print(f"   {'OK ' if d.get('ok') else 'FAIL'} desc={len(d.get('desc') or '')}字 "
              f"{d.get('err') or ''}")
        json.dump(res, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

        if i < len(batch) - 1:
            gap = random.uniform(args.min_gap, args.max_gap)
            print(f"   间隔 {gap:.1f}s")
            time.sleep(gap)

    ok = sum(1 for x in res if x.get("desc"))
    print(f"\n完成：本次 {len(batch)}，累计有正文 {ok}/{len(res)} | 今日已抓 {st.fetched}/{st.cap}")


if __name__ == "__main__":
    main()
