# -*- coding: utf-8 -*-
"""诊断指定目标详情页的沟通按钮（只读 + 记录，不点击）。

用法: python diag_target.py <jobNameKeyword>
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from dom_tools import find_by_text  # noqa: E402
from send_paced import RelayCDP  # noqa: E402


def main():
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    cdp = RelayCDP()
    targets = json.load(open("t_rest2.json", encoding="utf-8"))
    hits = [x for x in targets if kw in (x.get("jobName") or "")]
    if not hits:
        print(f"未找到含「{kw}」的目标")
        return
    t = hits[0]
    print(f"目标: {t['brand']} | {t['jobName']}")
    cdp.ensure_focus()
    cdp.send("Page.navigate",
             {"url": f"https://www.zhipin.com/job_detail/{t['eid']}.html"})
    for _ in range(16):
        time.sleep(1.2)
        if cdp.val("!!document.querySelector('.job-sec-text')"):
            break
    time.sleep(2)
    print(f"URL: {cdp.val('location.href')[-46:]}")
    print(f"hasFocus: {cdp.val('document.hasFocus()')} "
          f"vis: {cdp.val('document.visibilityState')}")
    print(f"find_by_text(立即沟通): {find_by_text(cdp, '立即沟通')}")
    print(f"find_by_text(继续沟通): {find_by_text(cdp, '继续沟通')}")

    r = cdp.val("""(()=>{
      const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
      const out = [];
      for (const e of document.querySelectorAll('a,div,button,span')) {
        const t = norm(e.innerText);
        if (t.length < 14 && t.indexOf('沟通') >= 0) {
          const b = e.getBoundingClientRect();
          out.push({tag: e.tagName, cls: (e.className||'').toString().slice(0,34),
                    txt: t, w: Math.round(b.width), h: Math.round(b.height)});
        }
      }
      return JSON.stringify(out.slice(0, 8));
    })()""")
    print("\n页面上含「沟通」的元素:")
    for x in json.loads(r or "[]"):
        print(f"   {x}")

    # 页面顶部提示
    tip = cdp.val("""(()=>{const t=document.body.innerText||'';
      const i=t.indexOf('沟通'); 
      return i<0 ? '' : t.slice(Math.max(0,i-80), i+80).replace(/\\n+/g,' | ');})()""")
    print(f"\n页面里「沟通」附近文本:\n   {tip}")


if __name__ == "__main__":
    main()
