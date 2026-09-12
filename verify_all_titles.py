# -*- coding: utf-8 -*-
"""逐个打开已发会话对应的岗位页，取真实岗位名，与消息中引用比对。"""
import json, urllib.request, time, os

SESSION = "cb-tab-3"

def cmd(method, params=None, timeout=60):
    body=json.dumps({"method":method,"params":params or {},"sessionId":SESSION}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, t=60):
    r=cmd("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=t)
    i=r.get("result",{})
    if i.get("exceptionDetails"): return None
    return i.get("result",{}).get("value")

rows = [x.split('~') for x in open('auth_sent.txt',encoding='utf-8').read().split('|SEP|') if x.strip()]
rows = [r for r in rows if len(r) >= 4]

outfile = 'verify_titles.json'
res = json.load(open(outfile,encoding='utf-8')) if os.path.exists(outfile) else []
done = {x['eid'] for x in res if x.get('realTitle')}

for i, r in enumerate(rows):
    brand, hr, eid, quoted = r[0], r[1], r[2], r[3]
    if eid in done: continue
    title = None
    try:
        cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
        for _ in range(10):
            time.sleep(1.2)
            u = val("location.href") or ''
            if eid in u:
                t = val("(document.querySelector('.name h1')||document.querySelector('h1')||{}).innerText")
                if t:
                    title = t.strip(); break
    except Exception as e:
        pass
    norm = lambda s: (s or '').replace('&amp;','&').replace('&middot;','·').replace('&nbsp;',' ').strip()
    res.append({'brand':brand,'hr':hr,'eid':eid,'realTitle':title,'quoted':quoted,
                'match': bool(title and norm(title)==norm(quoted))})
    mark = 'OK ' if res[-1]['match'] else 'DIFF'
    print(f"[{i+1}/{len(rows)}] {mark} {brand} | real={title} | msg={quoted}", flush=True)
    json.dump(res, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    time.sleep(2.5)

mism = [x for x in res if not x.get('match')]
print(f"\n完成：核对 {len(res)} 条，错配 {len(mism)}", flush=True)
