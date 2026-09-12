# -*- coding: utf-8 -*-
"""合并 4 路调研结果，去重、评分、排除已联系公司。

输入：
  research_media.json       36氪/铅笔道报道的杭州 AI 公司（58 条）
  research_foreign.json     杭州外企（78 条）
  research_specialized.json 专精特新/小巨人（138 条）
  research_bigtech.json     知名企业杭州 AI 岗位（69 条）

输出：
  master_companies.json     合并去重后的总表（含评分与推荐优先级）
  master_priority.md        人工可读的优先投递清单
"""
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# 阿里系：用户明确不投
ALI = ['阿里', '阿里巴巴', 'alibaba', '淘天', '淘宝', '天猫', '蚂蚁', '支付宝',
       '钉钉', '夸克', '饿了么', '高德', '阿里云', '菜鸟', '飞猪', '1688',
       '闲鱼', '盒马', 'ICBU', 'Accio', '阿里国际', '本地生活']

# 求职者画像（用于匹配评分）
POS_STRONG = ['fde', '前沿部署', '前线部署', '前向部署', 'forward deploy']
POS_DELIVER = ['交付', '实施', '解决方案', '落地', '客户成功', '部署', '售前']
POS_AI = ['AI', 'ai', '大模型', '模型', 'Agent', 'agent', '智能体', '算法',
          '机器学习', '智能化', '数智', 'RAG', 'LLM', '知识图谱', '自动化']
POS_ECOMM = ['电商', '跨境', '零售', '商家', '店铺', '导购', '营销']


def norm(s):
    return re.sub(r"[\s（）()【】\[\]、,，.。·/\\\-_|]" , "", (s or "")).lower()


def is_ali(text):
    t = (text or "").lower()
    return any(k.lower() in t for k in ALI)


def score_roles(roles, why_fit=""):
    """按岗位关键词打分。"""
    blob = " ".join(roles or []) + " " + (why_fit or "")
    s = 0
    if any(k in blob.lower() for k in POS_STRONG):
        s += 5
    if any(k in blob for k in POS_DELIVER):
        s += 3
    if any(k in blob for k in POS_AI):
        s += 2
    if any(k in blob for k in POS_ECOMM):
        s += 3
    return s


def main():
    srcs = [
        ("媒体(36氪/铅笔道)", "research_media.json"),
        ("外企", "research_foreign.json"),
        ("专精特新/小巨人", "research_specialized.json"),
        ("知名企业", "research_bigtech.json"),
    ]

    # 已联系公司（用于去重提示）
    contacted = set()
    from glob import glob
    for f in glob(os.path.join(HERE, "*.json")):
        if os.path.basename(f).startswith("research_") or \
           os.path.basename(f).startswith("master") or \
           os.path.basename(f).startswith("_research"):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
            items = d.values() if isinstance(d, dict) else (d if isinstance(d, list) else [])
            for x in items:
                if isinstance(x, dict):
                    c = x.get("company") or x.get("brand") or x.get("brandName")
                    if c:
                        contacted.add(c.strip())
        except Exception:
            pass
    norm_contacted = {norm(c): c for c in contacted if c}
    print(f"已接触公司基准: {len(contacted)}")

    merged = {}
    stats = Counter()

    for label, fn in srcs:
        path = os.path.join(HERE, fn)
        if not os.path.exists(path):
            print(f"  跳过 {fn}（不存在）")
            continue
        data = json.load(open(path, encoding="utf-8"))
        print(f"  {label:20s} {len(data):4d} 条")
        for x in data:
            comp = (x.get("company") or "").strip()
            if not comp:
                continue
            key = norm(comp)
            if not key:
                continue
            roles = x.get("relevant_roles") or []
            if isinstance(roles, str):
                roles = [roles]
            entry = merged.setdefault(key, {
                "company": comp,
                "sources": [],
                "sectors": [],
                "roles": [],
                "urls": [],
                "evidence": [],
                "notes": [],
                "ali": False,
                "excluded": False,
                "raw": [],
            })
            entry["sources"].append(label)
            entry["raw"].append(x)
            sec = x.get("sector") or x.get("industry") or ""
            if sec:
                entry["sectors"].append(sec)
            entry["roles"].extend([r for r in roles if r])
            for k in ("career_url",):
                if x.get(k):
                    entry["urls"].append(x[k])
            if x.get("evidence_url"):
                entry["evidence"].append(x["evidence_url"])
            for k in ("why_fit", "funding", "hangzhou_site", "list_type",
                      "role_type", "ai_relevance", "hangzhou"):
                if x.get(k):
                    entry["notes"].append(f"{k}={x[k]}")
            if is_ali(comp):
                entry["ali"] = True
            if x.get("excluded"):
                entry["excluded"] = True
            stats[label] += 1

    # 评分与标记
    out = []
    for key, e in merged.items():
        roles = list(dict.fromkeys(e["roles"]))
        why = " ".join(e["notes"])
        sc = score_roles(roles, why)
        # 已联系提示
        already = key in norm_contacted
        out.append({
            "company": e["company"],
            "sources": list(dict.fromkeys(e["sources"])),
            "sector": " / ".join(dict.fromkeys([s for s in e["sectors"] if s]))[:120],
            "relevant_roles": roles[:12],
            "career_url": e["urls"][0] if e["urls"] else "",
            "evidence_url": e["evidence"][0] if e["evidence"] else "",
            "ai_score": sc,
            "is_ali": e["ali"],
            "excluded": e["excluded"],
            "already_contacted": already,
            "notes": " | ".join(dict.fromkeys(e["notes"]))[:300],
        })

    # 排除阿里系
    keep = [x for x in out if not x["is_ali"]]
    ali = [x for x in out if x["is_ali"]]

    # 排序：分数高 → 未联系优先
    keep.sort(key=lambda x: (-x["ai_score"], x["already_contacted"]))

    json.dump(keep, open(os.path.join(HERE, "master_companies.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(ali, open(os.path.join(HERE, "master_ali.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print()
    print("=" * 84)
    print(f"合并结果：{len(out)} 家（去重后）")
    print(f"  阿里系（已剔除）: {len(ali)}")
    print(f"  可投公司        : {len(keep)}")
    print(f"    其中未联系过  : {len([x for x in keep if not x['already_contacted']])}")
    print("=" * 84)

    print("\n按来源分布（原始条目）:")
    for k, v in stats.items():
        print(f"  {v:4d}  {k}")

    print("\n按 AI 匹配分分布:")
    for rng, label in [((12, 99), "高（FDE/AI交付核心）"), ((8, 11), "中高"),
                       ((5, 7), "中"), ((0, 4), "低")]:
        n = len([x for x in keep if rng[0] <= x["ai_score"] <= rng[1]])
        print(f"  {n:4d}  {label} ({rng[0]}-{rng[1]}分)")

    return keep


if __name__ == "__main__":
    main()
