# -*- coding: utf-8 -*-
"""只收集 FDE 岗位（岗位名必须含 FDE/前沿部署/前线部署/前向部署）。低频防风控。"""
import json, urllib.request, urllib.parse, time, os

SESSION = "cb-tab-3"
def cmd(method, params=None, timeout=60):
    body=json.dumps({"method":method,"params":params or {},"sessionId":SESSION}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
def val(expr, timeout=60):
    r=cmd("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=timeout)
    i=r.get("result",{})
    if i.get("exceptionDetails"): return None
    return i.get("result",{}).get("value")

JS = """(async () => {
  try {
    var r = await fetch(%s, {credentials:'include'});
    var j = await r.json();
    if (j.code !== 0) return JSON.stringify({code:j.code, msg:j.message});
    var zd = j.zpData || {};
    var rows = [];
    var list = zd.jobList || [];
    for (var i = 0; i < list.length; i++) {
      var x = list[i];
      rows.push([x.encryptJobId||'', x.jobName||'', x.brandName||'', x.salaryDesc||'',
                 x.bossName||'', x.bossTitle||'', x.encryptBossId||'', x.securityId||'',
                 (x.jobLabels||[]).join('/'), x.cityName||'', x.areaDistrict||''].join('~'));
    }
    return JSON.stringify({ total: zd.totalCount, hasMore: zd.hasMore, rows: rows });
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

existing = set()
for f in ['jd_final.json','jd_search_final.json','jd_missing.json','chatlist_full.json',
          'send_results_v4.json','send_results_v5.json','fde_candidates.json']:
    try:
        for x in json.load(open(f,encoding='utf-8')):
            e = x.get('encryptJobId') or x.get('eid')
            if e: existing.add(e)
    except Exception: pass
print(f"已有 eid: {len(existing)}", flush=True)

outfile='fde_candidates.json'
cands = json.load(open(outfile,encoding='utf-8')) if os.path.exists(outfile) else {}
if isinstance(cands, list):
    cands = {x['eid']: x for x in cands}
TARGET = 115

for kw in ['fde', '前沿部署', '前线部署', '前向部署', 'FDE工程师']:
    if len(cands) >= TARGET: break
    for page in range(1, 10):
        if len(cands) >= TARGET: break
        d = fetch(kw, page)
        if not d or d.get('err') or d.get('code'):
            print(f"[{kw} p{page}] 异常: {str(d)[:60]}", flush=True)
            time.sleep(15); continue
        added = 0
        for row in d.get('rows') or []:
            p = row.split('~')
            if len(p) < 11: continue
            eid, jn = p[0], p[1]
            if not eid or eid in existing or eid in cands: continue
            if not any(m in jn.lower() for m in FDE_MARK): continue
            cands[eid] = {'eid':eid,'jobName':jn,'brandName':p[2],'salary':p[3],'bossName':p[4],
                          'bossTitle':p[5],'encryptBossId':p[6],'securityId':p[7],
                          'labels':p[8],'city':p[9],'area':p[10],'kw':kw}
            added += 1
        print(f"[{kw} p{page}] total={d.get('total')} 新增{added} 累计{len(cands)}", flush=True)
        json.dump(cands, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
        if added == 0 and not d.get('hasMore'): break
        time.sleep(7)

json.dump(cands, open(outfile,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"\nFDE 候选: {len(cands)}", flush=True)
