# -*- coding: utf-8 -*-
"""酷家乐（群核科技）招聘抓取。

站点：https://www.kujiale.com/pub/hr-recruit/social/postlist
列表页含全部社招岗位；详情页 /postdetail?postId=xxx

用系统 Chrome 渲染后读取（IAB 会崩主进程）。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chrome_scraper import CDP, launch_chrome  # noqa: E402

LIST = "https://www.kujiale.com/pub/hr-recruit/social/postlist"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kujiale_jd.json")

# 抓岗位卡：从 DOM 提取可点击的岗位项
JS_LIST = r"""
(() => {
  const out = [];
  // 找所有含岗位名的可点元素
  const els = [...document.querySelectorAll('a,li,div')];
  for (const e of els) {
    const t = (e.innerText || '').trim();
    if (!t || t.length < 3 || t.length > 50) continue;
    if (e.children.length > 2) continue;
    if (!/工程师|经理|专家|顾问|交付|解决方案|算法|产品|开发|架构|运营/.test(t)) continue;
    const b = e.getBoundingClientRect();
    if (b.width === 0 || b.height === 0) continue;
    out.push({text: t, x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2),
              cls: (e.className || '').toString().slice(0, 50), tag: e.tagName});
  }
  return JSON.stringify({url: location.href, n: out.length, items: out});
})()
"""


def main():
    proc, ws = launch_chrome()
    cdp = CDP(ws)
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    results = []
    try:
        cdp.goto(LIST, wait=8)
        print("URL:", cdp.ev("location.href"))

        # 首次读取
        d = json.loads(cdp.ev(JS_LIST) or "{}")
        print(f"首屏岗位: {d.get('n')} 个")
        seen = {}
        for it in d.get("items") or []:
            seen[it["text"]] = it

        # 滚动加载
        for i in range(15):
            cdp.ev("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)
            dd = json.loads(cdp.ev(JS_LIST) or "{}")
            before = len(seen)
            for it in dd.get("items") or []:
                seen[it["text"]] = it
            print(f"  轮{i+1}: 累计 {len(seen)} 个（+{len(seen)-before}）")
            if len(seen) == before and i >= 3:
                break

        items = list(seen.values())
        print(f"\n共 {len(items)} 个岗位，按关键词筛 AI/交付相关：")
        KEEP = ("交付", "实施", "解决方案", "售前", "客户成功", "项目经理",
                "AI", "ai", "大模型", "Agent", "智能", "算法", "架构")
        cand = [x for x in items if any(k in x["text"] for k in KEEP)]
        print(f"命中 {len(cand)} 个")
        for x in cand:
            print(f"   {x['text'][:44]:44s} @({x['x']},{x['y']})")

        json.dump({"all": items, "candidates": cand},
                  open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n已写入 {OUT}")

    finally:
        cdp.close()
        proc.terminate()
        time.sleep(1)
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    main()
