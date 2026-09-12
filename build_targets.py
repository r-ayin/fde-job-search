# -*- coding: utf-8 -*-
"""构建发送目标集：会话列表待发 + 搜索页高分未联系。"""
import json, re

# 合并全部 JD 来源
jd = {}
for f in ['jd_final.json','jd_search_final.json','jd_missing.json']:
    try:
        for x in json.load(open(f, encoding='utf-8')):
            if x.get('desc') and x.get('eid', x.get('encryptJobId')):
                eid = x.get('encryptJobId') or x.get('eid')
                jd[eid] = x
    except Exception as e:
        print('skip', f, e)
print('JD 库:', len(jd))

chat = json.load(open('chatlist_full.json', encoding='utf-8'))

# --- 目标 1：会话列表中仅有默认招呼语的（需发定制消息）
REJECT_KW = ['不合适','不是很匹配','不匹配','抱歉','不好意思']
targets = []
skipped = []
for c in chat:
    last = c.get('lastText') or ''
    if '您好，看到' in last:      # 已发过定制消息
        continue
    if any(k in last for k in REJECT_KW):
        skipped.append({**c, 'skip_reason': 'HR已明确拒绝'})
        continue
    eid = c.get('encryptJobId')
    d = jd.get(eid, {})
    targets.append({
        'source': 'chat',
        'eid': eid,
        'brand': c.get('brand') or d.get('brandName'),
        'hr': c.get('name'),
        'jobName': d.get('title') or d.get('jobName') or '',
        'salary': d.get('salary') or '',
        'desc': d.get('desc') or '',
        'lastText': last,
    })

# --- 目标 2：搜索页高分（≥60）且未在会话中
chat_eids = {c.get('encryptJobId') for c in chat}
try:
    scored = json.load(open('search_scored_v2.json', encoding='utf-8'))
    for s in scored:
        if s['score'] < 60: continue
        sal = s.get('salary') or ''
        m = re.search(r'(\d+)-(\d+)K', sal)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi < 10 or lo > 60: continue
        if '元/月' in sal or '元/天' in sal: continue
        if '销售' in (s.get('name') or ''): continue
        eid = s['eid']
        if eid in chat_eids: continue
        d = jd.get(eid, {})
        targets.append({
            'source': 'search',
            'eid': eid,
            'brand': s.get('company'),
            'hr': None,
            'jobName': s.get('name'),
            'salary': sal,
            'desc': d.get('desc') or '',
            'score': s['score'],
        })
except Exception as e:
    print('search err', e)

json.dump(targets, open('send_targets.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(skipped, open('send_skipped.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('待发目标:', len(targets), '| 跳过:', len(skipped))
print('  chat 来源:', sum(1 for t in targets if t['source']=='chat'))
print('  search 来源:', sum(1 for t in targets if t['source']=='search'))
print('  有JD:', sum(1 for t in targets if t['desc']))
