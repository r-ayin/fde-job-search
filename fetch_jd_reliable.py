# -*- coding: utf-8 -*-
"""可靠抓取 JD：导航后轮询等待页面内容与目标 eid 一致，数据以详情页为权威。"""
import json, urllib.request, time, os, sys

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
    url: location.href,
    ok: !!g('.job-sec-text'),
    title: txt(g('.name h1') || g('h1')),
    salary: txt(g('.salary')),
    company: txt(g('.sider-company .company-info') || g('.sider-company .name') || g('.company-info .name')),
    desc: txt(g('.job-sec-text')),
    tags: [...document.querySelectorAll('.job-keyword-list li')].map(e=>txt(e)).filter(Boolean),
    expEdu: txt(g('.job-primary .text') || g('.info-primary p'))
  });
})()
"""

cards = json.load(open('search_cards.json', encoding='utf-8'))
todo = [c for c in cards if '元/天' not in (c.get('salary') or '')]
print(f"待抓 {len(todo)} 个", flush=True)

results = []
outfile = 'jd_search_final.json'
if os.path.exists(outfile):
    results = json.load(open(outfile, encoding='utf-8'))
done = {x['eid'] for x in results if x.get('ok') and x.get('title')}

for i, c in enumerate(todo):
    eid = c['eid']
    if eid in done:
        continue
    try:
        cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
        # 轮询等待：URL 含目标 eid 且正文出现
        d = None
        for attempt in range(15):
            time.sleep(1.2)
            raw = val(EXTRACT)
            if not raw: continue
            d = json.loads(raw)
            if d.get('ok') and eid in (d.get('url') or '') and d.get('title'):
                break
        if not d:
            d = {'ok': False}
        d['eid'] = eid
        results.append(d)
        print(f"[{i+1}/{len(todo)}] {'OK ' if d.get('ok') else 'FAIL'} {d.get('company','?')} | {d.get('title','?')[:30]} | {d.get('salary','')} | desc={len(d.get('desc') or '')}", flush=True)
    except Exception as e:
        print(f"[{i+1}] ERR {str(e)[:80]}", flush=True)
        results.append({'eid': eid, 'ok': False})
    if (i+1) % 5 == 0:
        json.dump(results, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)

json.dump(results, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"完成 {len(results)} 条，有正文 {sum(1 for x in results if x.get('ok'))}", flush=True)
