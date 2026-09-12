# -*- coding: utf-8 -*-
"""重新收集 FDE 候选（用 \t 分隔，避免 securityId 含 ~ 导致错位）。"""
import json, urllib.request, urllib.parse, time, os

SESSION="cb-tab-3"
def cmd(method, params=None, timeout=60):
    body=json.dumps({"method":method,"params":params or {},"sessionId":SESSION}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
def val(expr, timeout=60):
    r=cmd("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=timeout)
    i=r.get("result",{})
    if i.get("exceptionDetails"): return None
    return i.get("result",{}).get("value")

# 直接用 JSON 返回，不用字符串拼接
JS = """(async () => {
  try {
    var r = await fetch(%s, {credentials:'include'});
    var j = await r.json();
    if (j.code !== 0) return JSON.stringify({code:j.code, msg:j.message});
    var zd = j.zpData || {};
    var list = zd.jobList || [];
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var x = list[i];
      out.push({
        eid: x.encryptJobId || '',
        jobName: x.jobName || '',
        brandName: x.brandName || '',
        salary: x.salaryDesc || '',
        bossName: x.bossName || '',
        bossTitle: x.bossTitle || '',
        encryptBossId: x.encryptBossId || '',
        securityId: x.securityId || '',
        labels: (x.jobLabels || []).join('/'),
        city: x.cityName || '',
        area: x.areaDistrict || ''
      });
    }
    return JSON.stringify({ total: zd.totalCount, hasMore: zd.hasMore, jobs: out });
  } catch(e) { return JSON.stringify({ err: String(e).slice(0,100) }); }
})()"""

FDE_MARK = ['fde', '前沿部署', '前线部署', '前向部署', 'forward deployed']

def fetch(kw, page):
    url = ('/wapi/zpgeek/search/joblist.json?scene=1&query=' + urllib.parse.quote(kw) +
           '&city=101210100&page=' + str(page) + '&pageSize=30')
    raw = val(JS % json.dumps(url), timeout=60)
    if not raw: return None
    try: return json.loads(raw)
    except Exception: return None

existing=set()
for f in ['jd_final.json','jd_search_final.json','chatlist_full.json','send_results_v4.json','send_results_v5.json']:
    try:
        for x in json.load(open(f,encoding='utf-8')):
            e=x.get('encryptJobId') or x.get('eid')
            if e: existing.add(e)
    except Exception: pass
print(f"已有 eid: {len(existing)}", flush=True)

outfile='fde_candidates2.json'
cands = json.load(open(outfile,encoding='utf-8')) if os.path.exists(outfile) else {}
for kw in ['fde','前沿部署','前线部署','前向部署','FDE工程师']:
    for page in range(1,4):
        d=fetch(kw,page)
        if not d or d.get('err') or d.get('code'):
            print(f"[{kw} p{page}] {str(d)[:60]}", flush=True); time.sleep(30); continue
        added=0
        for x in d.get('jobs') or []:
            eid=x['eid']; jn=x['jobName']
            if not eid or eid in existing or eid in cands: continue
            if not any(m in jn.lower() for m in FDE_MARK): continue
            x['kw']=kw
            cands[eid]=x
            added+=1
        print(f"[{kw} p{page}] total={d.get('total')} 新增{added} 累计{len(cands)}", flush=True)
        json.dump(cands, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
        if not d.get('hasMore'): break
        time.sleep(20)
json.dump(cands, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
n_sec = sum(1 for v in cands.values() if v.get('securityId'))
print(f"\nFDE 候选: {len(cands)}，其中有 securityId: {n_sec}", flush=True)
