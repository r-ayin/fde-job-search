# -*- coding: utf-8 -*-
"""抓取 FDE 候选岗位的 JD 正文（真实导航 + 轮询等待 eid 一致）。"""
import json
import os
import time
import urllib.request

SESSION = "cb-tab-3"


def cmd(method, params=None, timeout=60):
    body = json.dumps({"method": method, "params": params or {}, "sessionId": SESSION}).encode()
    req = urllib.request.Request("http://127.0.0.1:18793/cmd", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def val(expr, timeout=60):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, timeout)
    i = r.get("result", {})
    if i.get("exceptionDetails"):
        return None
    return i.get("result", {}).get("value")


EXTRACT = """
(() => {
  const g = s => document.querySelector(s);
  const txt = el => el ? (el.innerText || el.textContent || '').replace(/\\s+/g,' ').trim() : '';
  return JSON.stringify({
    url: location.href,
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

if __name__ == '__main__':
    todo = json.load(open('fde_todo.json', encoding='utf-8'))
    outfile = 'fde_jd.json'
    res = json.load(open(outfile, encoding='utf-8')) if os.path.exists(outfile) else []
    done = {x['eid'] for x in res if x.get('ok')}
    print(f"待抓 {len(todo)}，已完成 {len(done)}", flush=True)

    for i, t in enumerate(todo):
        eid = t['eid']
        if eid in done:
            continue
        d = None
        try:
            cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
            for _ in range(14):
                time.sleep(1.2)
                raw = val(EXTRACT)
                if not raw:
                    continue
                d = json.loads(raw)
                if d.get('ok') and eid in (d.get('url') or '') and d.get('title'):
                    break
        except Exception as e:
            d = {'ok': False, 'err': str(e)[:80]}
        if not d:
            d = {'ok': False}
        d['eid'] = eid
        d['listName'] = t.get('jobName')
        d['listBrand'] = t.get('brandName')
        d['listSalary'] = t.get('salary')
        d['bossName'] = t.get('bossName')
        d['bossTitle'] = t.get('bossTitle')
        res.append(d)
        print(f"[{i+1}/{len(todo)}] {'OK ' if d.get('ok') else 'FAIL'} {d.get('company') or t.get('brandName')} | {d.get('title') or t.get('jobName')} | desc={len(d.get('desc') or '')}", flush=True)
        json.dump(res, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        time.sleep(4)

    print(f"完成 {len(res)}，有正文 {sum(1 for x in res if x.get('ok'))}", flush=True)
