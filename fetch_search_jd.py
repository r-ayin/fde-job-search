# -*- coding: utf-8 -*-
import json, urllib.request, time, sys

def cmd(method, params=None, session="cb-tab-3", timeout=90):
    body=json.dumps({"method":method,"params":params or {},"sessionId":session}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, session="cb-tab-3", timeout=90):
    r = cmd("Runtime.evaluate", {"expression":expr,"returnByValue":True,"awaitPromise":True}, session=session, timeout=timeout)
    inner = r.get("result",{})
    if inner.get("exceptionDetails"): return None
    return inner.get("result",{}).get("value")

EXTRACT = """
(() => {
  const g = s => document.querySelector(s);
  const txt = el => el ? (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim() : '';
  return JSON.stringify({
    ok: !!g('.job-sec-text'),
    title: txt(g('.name h1') || g('h1')),
    salary: txt(g('.salary')),
    desc: txt(g('.job-sec-text')),
    tags: [...document.querySelectorAll('.job-keyword-list li')].map(e=>txt(e)).filter(Boolean)
  });
})()
"""

cards = json.load(open('search_scored.json', encoding='utf-8'))
# 只抓前 N 个高分（排除实习/日结）
cand = [c for c in cards if '元/天' not in (c.get('salary') or '')][:20]
print(f"抓取 {len(cand)} 个岗位 JD", flush=True)

results = []
for i, c in enumerate(cand):
    eid = c['eid']
    try:
        cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
        time.sleep(6)
        raw = val(EXTRACT)
        d = json.loads(raw) if raw else {"ok": False}
        d.update({'eid': eid, 'name': c.get('name'), 'company': c.get('company'), 'salary': c.get('salary'), 'searchTags': c.get('tags')})
        results.append(d)
        print(f"[{i+1}/{len(cand)}] {'OK ' if d.get('ok') else 'FAIL'} {c.get('company')} | {c.get('name')[:30]} | desc={len(d.get('desc') or '')}", flush=True)
    except Exception as e:
        print(f"[{i+1}] ERR {e}", flush=True)
        results.append({'eid': eid, 'name': c.get('name'), 'company': c.get('company'), 'ok': False})
    if (i+1) % 5 == 0:
        json.dump(results, open('search_jd.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)

json.dump(results, open('search_jd.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("完成，有正文:", sum(1 for x in results if x.get('ok')), flush=True)
