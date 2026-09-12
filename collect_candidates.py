# -*- coding: utf-8 -*-
"""通过搜索接口批量收集岗位候选列表（多关键词 + 多页）。"""
import json
import urllib.request
import time
import os
import urllib.parse

SESSION = "cb-tab-3"

KEYWORDS = [
    'fde', '前沿部署', '前线部署', '前向部署',
    'AI解决方案', 'AI智能体', '大模型', 'AI产品经理',
    'AI应用工程师', 'AI交付', '解决方案工程师', 'AI实施',
    'agent', 'AI落地', '智能体开发',
]

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

JS_FETCH_PAGE = """(async () => {
  var url = %s;
  try {
    var r = await fetch(url, {credentials:'include'});
    var j = await r.json();
    var zd = j.zpData || {};
    var list = (zd.jobList || []);
    var rows = [];
    for (var i = 0; i < list.length; i++) {
      var x = list[i];
      rows.push([x.encryptJobId||'', x.jobName||'', x.brandName||'', x.salaryDesc||'',
                 x.bossName||'', x.bossTitle||'', x.encryptBossId||'', x.securityId||'',
                 (x.jobLabels||[]).join('/'), x.cityName||'', x.areaDistrict||''].join('~'));
    }
    return JSON.stringify({ total: zd.totalCount, hasMore: zd.hasMore, n: rows.length, rows: rows });
  } catch(e) { return JSON.stringify({ err: String(e).slice(0,100) }); }
})()"""


def fetch_page(kw, page, size=30):
    url = ('/wapi/zpgeek/search/joblist.json?scene=1&query=' + urllib.parse.quote(kw) +
           '&city=101210100&page=' + str(page) + '&pageSize=' + str(size))
    raw = val(JS_FETCH_PAGE % json.dumps(url), timeout=60)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


if __name__ == '__main__':
    # 已有 eid（去重用）
    existing = set()
    for f in ['jd_final.json', 'jd_search_final.json', 'jd_missing.json', 'chatlist_full.json']:
        try:
            for x in json.load(open(f, encoding='utf-8')):
                e = x.get('encryptJobId') or x.get('eid')
                if e: existing.add(e)
        except Exception:
            pass
    print(f"已有 eid: {len(existing)}", flush=True)

    outfile = 'candidates.json'
    cands = json.load(open(outfile, encoding='utf-8')) if os.path.exists(outfile) else {}
    # cands: eid -> record

    for kw in KEYWORDS:
        pages = 2
        for p in range(1, pages + 1):
            d = fetch_page(kw, p)
            if not d or d.get('err'):
                print(f"[{kw} p{p}] 失败: {str(d)[:80]}", flush=True)
                continue
            rows = d.get('rows') or []
            new = 0
            for row in rows:
                parts = row.split('~')
                if len(parts) < 11: continue
                eid = parts[0]
                if not eid or eid in existing or eid in cands: continue
                cands[eid] = {
                    'eid': eid, 'jobName': parts[1], 'brandName': parts[2], 'salary': parts[3],
                    'bossName': parts[4], 'bossTitle': parts[5], 'encryptBossId': parts[6],
                    'securityId': parts[7], 'labels': parts[8], 'city': parts[9], 'area': parts[10],
                    'kw': kw,
                }
                new += 1
            print(f"[{kw} p{p}] total={d.get('total')} 拿到{len(rows)} 新增{new} 累计{len(cands)}", flush=True)
            time.sleep(6.0)
        json.dump(cands, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if len(cands) >= 140:
            print(f"已收集 {len(cands)}，足够", flush=True)
            break

    json.dump(cands, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n最终候选: {len(cands)}", flush=True)
