# -*- coding: utf-8 -*-
"""FDE 岗位匹配度评分 v2 —— 必须基于 JD 正文"""
import json, re

STRONG_KW = ['mcp','docker','agent','智能体','rag','检索','向量','prompt','提示词','大模型','llm',
             '微调','sft','部署','交付','解决方案','电商','tob','客户','方案','poc','工作流',
             '记忆','知识库','评测','标注','api','知识图谱','自动化','数据分析']
WEAK_KW = ['spring boot','spring cloud','微服务架构','vue','react','typescript','kubernetes',
           'k8s','java','golang','go语言','c#','全栈开发','安卓','ios']

def score(card):
    desc = (card.get('desc') or '').lower()
    name = (card.get('title') or card.get('listName') or '').lower()
    tags = ' '.join(card.get('listTags') or [])
    blob = desc + ' ' + name
    s, reasons = 0, []

    # 1) 岗位方向 30
    if any(k in name for k in ['fde','前沿部署','前线部署','前向部署']):
        s += 30; reasons.append('+30 核心FDE')
    elif any(k in name for k in ['交付','实施','解决方案','部署']):
        s += 22; reasons.append('+22 交付/解决方案')
    elif any(k in name for k in ['产品经理','项目经理','运营','顾问']):
        s += 12; reasons.append('+12 产品/项目')
    elif any(k in name for k in ['销售','商务','大客户']):
        s += 4; reasons.append('+4 偏销售')
    else:
        s += 8; reasons.append('+8 其他')

    # 2) 能力匹配 25（基于 JD 正文）
    hits = sorted(set(k for k in STRONG_KW if k in desc))
    n = min(len(hits), 6)
    s += n * 4
    reasons.append(f'+{n*4} 能力命中({",".join(hits[:6])})')

    # 3) 行业 15
    if any(k in desc for k in ['电商','品牌','跨境','零售电商']):
        s += 15; reasons.append('+15 电商行业')
    elif '零售' in desc:
        s += 8; reasons.append('+8 零售')

    # 4) 薪资 15
    sal = card.get('salary') or card.get('listSalary') or ''
    m = re.match(r'(\d+)-(\d+)K', sal)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo >= 15 and hi <= 30: s += 15; reasons.append('+15 薪资匹配')
        elif hi >= 15: s += 10; reasons.append('+10 薪资部分匹配')
        else: s += 3; reasons.append('+3 薪资偏低')

    # 5) 经验门槛 10
    if any(k in tags for k in ['经验不限','1-3年','1年以内','在校']):
        s += 10; reasons.append('+10 经验合适')
    elif '3-5年' in tags:
        s += 6; reasons.append('+6 经验略高')
    elif '5-10年' in tags:
        s += 1; reasons.append('+1 经验高')

    # 6) 短板扣分
    weak = sorted(set(k for k in WEAK_KW if k in desc))
    if weak:
        s -= len(weak) * 6
        reasons.append(f'-{len(weak)*6} 短板({",".join(weak[:4])})')

    return s, reasons

if __name__ == '__main__':
    jd = json.load(open('jd_search_final.json', encoding='utf-8'))
    results = []
    for c in jd:
        if not c.get('ok'): continue
        sc, rs = score(c)
        results.append({
            'eid': c['eid'], 'name': c.get('title') or c.get('listName'),
            'company': c.get('company'), 'salary': c.get('salary') or c.get('listSalary'),
            'area': c.get('area'), 'score': sc, 'reasons': rs,
            'descLen': len(c.get('desc') or '')
        })
    results.sort(key=lambda x: -x['score'])

    print(f"{'分':>4} {'岗位':<30} {'薪资':>12} {'公司':<18} 理由")
    print('-' * 140)
    for r in results:
        print(f"{r['score']:>4} {(r['name'] or '')[:28]:<30} {(r['salary'] or '')[:10]:>12} {(r['company'] or '')[:16]:<18} {'; '.join(r['reasons'][:4])}")
    json.dump(results, open('search_scored_v2.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    print("≥60:", sum(1 for r in results if r['score']>=60), "| 45-59:", sum(1 for r in results if 45<=r['score']<60), "| 30-44:", sum(1 for r in results if 30<=r['score']<45), "| <30:", sum(1 for r in results if r['score']<30))
