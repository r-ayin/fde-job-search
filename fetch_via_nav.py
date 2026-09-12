import json, urllib.request, time, sys

def cmd(method, params=None, session="cb-tab-1", timeout=90):
    body=json.dumps({"method":method,"params":params or {},"sessionId":session}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, timeout=90):
    r = cmd("Runtime.evaluate", {"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=timeout)
    inner = r.get("result",{})
    if inner.get("exceptionDetails"):
        return None
    return inner.get("result",{}).get("value")

EXTRACT = """
(() => {
  const g = s => document.querySelector(s);
  const txt = el => el ? (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim() : '';
  return JSON.stringify({
    ok: !!g('.job-sec-text'),
    title: txt(g('.name h1') || g('h1')),
    salary: txt(g('.salary')),
    exp: txt(g('.job-primary .text') || g('.info-primary p')),
    desc: txt(g('.job-sec-text')),
    tags: [...document.querySelectorAll('.job-keyword-list li')].map(e=>txt(e)).filter(Boolean),
    company: txt(g('.sider-company .name') || g('.company-info .name')),
    industry: txt(g('.sider-company .company-tag-list, .company-info .company-tag-list'))
  });
})()
"""

todo = json.load(open('jobs_todo.json', encoding='utf-8'))
done_ids = set()
try:
    prev = json.load(open('jd_nav.json', encoding='utf-8'))
    done_ids = {x['encryptJobId'] for x in prev if x.get('ok')}
    results = prev
except Exception:
    results = []

remaining = [x for x in todo if x['encryptJobId'] not in done_ids]
print(f"待抓 {len(remaining)}（已完成 {len(done_ids)}）", flush=True)

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end = int(sys.argv[2]) if len(sys.argv) > 2 else len(remaining)

for i, item in enumerate(remaining[start:end], start):
    eid = item['encryptJobId']
    try:
        cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
        time.sleep(6)
        raw = val(EXTRACT)
        d = json.loads(raw) if raw else {"ok": False}
        d.update({k: item.get(k) for k in ('encryptJobId','name','brandName','jobName','locationName')})
        results.append(d)
        print(f"[{i+1}/{len(remaining)}] {'OK ' if d.get('ok') else 'FAIL'} {item.get('brandName')} | {item.get('jobName')} | desc={len(d.get('desc') or '')}", flush=True)
    except Exception as e:
        print(f"[{i+1}] ERR {e}", flush=True)
        results.append({"encryptJobId": eid, "brandName": item.get('brandName'), "jobName": item.get('jobName'), "ok": False})
    if (i+1) % 5 == 0:
        json.dump(results, open('jd_nav.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)

json.dump(results, open('jd_nav.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
ok = sum(1 for x in results if x.get('ok'))
print(f"完成：{len(results)} 条，有正文 {ok}", flush=True)
