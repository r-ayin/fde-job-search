# -*- coding: utf-8 -*-
"""用带 securityId 的接口抓取完整 JD（低频，避免风控）。"""
import json
import os
import time
import urllib.parse
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


# 返回 JSON，提取关键字段
JS = """(async () => {
  var url = %s;
  try {
    var r = await fetch(url, {credentials:'include'});
    var j = await r.json();
    if (j.code !== 0) return JSON.stringify({code:j.code, msg:j.message});
    var zd = j.zpData || {};
    var ji = zd.jobInfo || zd.job || zd;
    var out = {
      jobName: ji.jobName || '',
      brandName: ji.brandName || '',
      salary: ji.salaryDesc || '',
      city: ji.cityName || ji.locationName || '',
      exp: ji.experienceName || ji.jobExperience || '',
      degree: ji.degreeName || ji.jobDegree || '',
      desc: ji.jobDescription || ji.description || ji.postDescription || '',
      skills: (ji.skills || []).join('/'),
      welfare: (ji.welfareList || []).join('/'),
      brandIndustry: ji.brandIndustry || '',
      brandScale: ji.brandScaleName || '',
      brandStage: ji.brandStageName || ''
    };
    return JSON.stringify(out);
  } catch(e) { return JSON.stringify({err: String(e).slice(0,100)}); }
})()"""

if __name__ == '__main__':
    todo = json.load(open('fde_todo2.json', encoding='utf-8'))
    outfile = 'fde_jd2.json'
    res = json.load(open(outfile, encoding='utf-8')) if os.path.exists(outfile) else []
    done = {x['eid'] for x in res if x.get('desc')}
    print(f"待抓 {len(todo)}，已完成 {len(done)}", flush=True)

    for i, t in enumerate(todo):
        eid = t['eid']
        if eid in done:
            continue
        sec = t.get('securityId') or ''
        url = ('/wapi/zpgeek/job/detail.json?encryptJobId=' + eid +
               '&securityId=' + urllib.parse.quote(sec) + '&lid=&scene=1')
        d = None
        try:
            raw = val(JS % json.dumps(url), timeout=60)
            d = json.loads(raw) if raw else None
        except Exception as e:
            d = {'err': str(e)[:80]}
        if not d:
            d = {'err': 'no_response'}
        d['eid'] = eid
        d['listJob'] = t.get('jobName')
        d['listBrand'] = t.get('brandName')
        d['listSalary'] = t.get('salary')
        d['bossName'] = t.get('bossName')
        d['bossTitle'] = t.get('bossTitle')
        d['encryptBossId'] = t.get('encryptBossId')
        res.append(d)
        ok = bool(d.get('desc'))
        print(f"[{i+1}/{len(todo)}] {'OK ' if ok else 'FAIL'} {d.get('brandName') or t.get('brandName')} | {d.get('jobName') or t.get('jobName')} | desc={len(d.get('desc') or '')} {d.get('msg') or d.get('err') or ''}", flush=True)
        json.dump(res, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        time.sleep(7)

    print(f"完成 {len(res)}，有正文 {sum(1 for x in res if x.get('desc'))}", flush=True)
