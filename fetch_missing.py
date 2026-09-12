# -*- coding: utf-8 -*-
import json, urllib.request, time

def cmd(method, params=None, session="cb-tab-3", timeout=90):
    body=json.dumps({"method":method,"params":params or {},"sessionId":session}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
def val(expr):
    r=cmd("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True})
    i=r.get("result",{})
    if i.get("exceptionDetails"): return None
    return i.get("result",{}).get("value")

EXTRACT = """
(() => {
  const g = s => document.querySelector(s);
  const txt = el => el ? (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim() : '';
  return JSON.stringify({
    ok: !!g('.job-sec-text'),
    title: txt(g('.name h1') || g('h1')),
    salary: txt(g('.salary')),
    company: txt(g('.sider-company .company-info') || g('.sider-company .name')),
    desc: txt(g('.job-sec-text'))
  });
})()
"""

missing = ['424bd56707e720790nJz3dq6E1tT', '66aa6fe11ac47b450nN539q0FVFX']
out = []
for eid in missing:
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    d = None
    for _ in range(15):
        time.sleep(1.2)
        raw = val(EXTRACT)
        if raw:
            d = json.loads(raw)
            if d.get('ok') and d.get('title'): break
    if d: d['eid'] = eid
    out.append(d or {'eid': eid, 'ok': False})
    print(f"{eid} -> {d.get('company') if d else '?'} | {d.get('title') if d else '?'} | desc={len(d.get('desc') or '') if d else 0}", flush=True)

json.dump(out, open('jd_missing.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("done")
