# -*- coding: utf-8 -*-
"""FDE 岗位匹配度评分器

评分维度与权重（总分 100）：
  1. 岗位方向匹配（30）— FDE/交付/解决方案 为核心方向
  2. 能力要求匹配（25）— JD 要求 vs 用户确认能力（MCP/Docker/Agent/RAG/LLM）
  3. 行业匹配（15）— 电商行业经验可迁移
  4. 薪资匹配（15）— 用户期望 15-25K
  5. 经验门槛（10）— 用户约 2.5 年 AI 经验，5-10年要求会扣分
  6. 排除项扣分（-30）— 硬性要求用户完全没有的（Java微服务/前端/特定行业深度）
"""
import json, re

# 用户确认能力关键词（有把握）
STRONG_KW = ['mcp', 'docker', 'agent', '智能体', 'rag', '检索', '向量', 'prompt', '提示词',
             '大模型', 'llm', '微调', 'sft', '部署', '交付', '解决方案', '电商', 'toB', 'tob',
             '客户', '方案', 'poc', '工作流', '记忆', '知识库', '评测', '标注']
# 用户明确短板
WEAK_KW = ['spring boot', 'spring cloud', '微服务架构', 'vue', 'react', 'typescript',
           'kubernetes', 'k8s', 'java', 'golang', 'go语言', 'c#', '全栈开发']

def score_card(card, jd_text=None):
    blob = ((card.get('name') or '') + ' ' + ' '.join(card.get('tags') or []) + ' ' +
            (jd_text or '')).lower()
    name = (card.get('name') or '').lower()
    s = 0
    reasons = []

    # 1. 岗位方向（30）
    if 'fde' in name or '前沿部署' in name or '前线部署' in name or '前向部署' in name:
        s += 30; reasons.append('+30 核心FDE岗位')
    elif any(k in name for k in ['交付', '实施', '解决方案', '部署']):
        s += 22; reasons.append('+22 交付/解决方案方向')
    elif any(k in name for k in ['产品经理', '项目经理', '运营', '顾问']):
        s += 12; reasons.append('+12 产品/项目方向')
    elif any(k in name for k in ['销售', '商务', '大客户']):
        s += 4; reasons.append('+4 偏销售')
    else:
        s += 8; reasons.append('+8 其他')

    # 2. 能力要求匹配（25）
    hits = [k for k in STRONG_KW if k in blob]
    n = min(len(hits), 6)
    s += n * 4
    reasons.append(f'+{n*4} 能力命中{len(hits)}项({",".join(hits[:6])})')

    # 3. 行业（15）
    if '电商' in blob or '品牌' in blob or '跨境' in blob:
        s += 15; reasons.append('+15 电商行业匹配')
    elif '零售' in blob:
        s += 8; reasons.append('+8 零售相关')

    # 4. 薪资（15）
    sal = card.get('salary') or ''
    m = re.match(r'(\d+)-(\d+)K', sal)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo >= 15 and hi <= 30: s += 15; reasons.append('+15 薪资区间匹配')
        elif hi >= 15: s += 10; reasons.append('+10 薪资部分匹配')
        else: s += 3; reasons.append('+3 薪资偏低')
    elif '元/天' in sal:
        s += 2; reasons.append('+2 实习/日结')

    # 5. 经验门槛（10）
    tags = ' '.join(card.get('tags') or [])
    if '经验不限' in tags or '1-3年' in tags or '1年以内' in tags:
        s += 10; reasons.append('+10 经验门槛合适')
    elif '3-5年' in tags:
        s += 6; reasons.append('+6 经验门槛略高')
    elif '5-10年' in tags:
        s += 1; reasons.append('+1 经验门槛高')

    # 6. 排除项
    weak_hits = [k for k in WEAK_KW if k in blob]
    if weak_hits:
        s -= len(weak_hits) * 6
        reasons.append(f'-{len(weak_hits)*6} 短板({",".join(weak_hits[:4])})')

    return s, reasons

if __name__ == '__main__':
    cards = json.load(open('search_cards.json', encoding='utf-8'))
    jd_map = {}
    try:
        for x in json.load(open('jd_final.json', encoding='utf-8')):
            if x.get('desc'): jd_map[x['encryptJobId']] = x['desc']
    except Exception: pass

    results = []
    for c in cards:
        sc, rs = score_card(c, jd_map.get(c['eid']))
        results.append({**c, 'score': sc, 'reasons': rs})
    results.sort(key=lambda x: -x['score'])

    print(f"{'分':>4} {'岗位':<34} {'薪资':>14} {'公司':<16} 理由")
    print('-' * 130)
    for r in results:
        print(f"{r['score']:>4} {r['name'][:32]:<34} {r['salary'][:12]:>14} {r['company'][:14]:<16} {'; '.join(r['reasons'][:4])}")
    json.dump(results, open('search_scored.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
