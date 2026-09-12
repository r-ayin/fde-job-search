# -*- coding: utf-8 -*-
"""排除对语言有要求的公司/岗位（纯本地处理，零网络）。

用户要求：排除其中对语言有要求的。

判断规则（从强到弱）：
  A. 真外企（母国为欧美日韩等非中文地区）→ 排除
     理由：外企招聘普遍要求英语，尤其口语
  B. 岗位名含明确语言/外派信号 → 排除该岗位（公司若还有其他岗位则保留）
     信号：英语/English/外派/驻外/overseas/海外+技服/出差新加坡等
  C. 中资背景（港台注册但实际中文办公）→ 保留
     如：浙江商汤（中资）、浙江子不语（杭州本土跨境电商标杆）
  D. 母国待核的 → 单独列出，让用户判断

输出：
  master_no_lang.json       排除语言要求后的清单
  master_lang_excluded.json 被排除明细（含原因，可随时恢复）
"""
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# 中资背景，虽港台注册但中文办公 → 保留
CHINESE_BACKED = [
    "浙江商汤科技开发",          # 中资 AI 公司，港资口径
    "浙江子不语电子商务",        # 杭州本土跨境电商上市公司
    "高济实业",                  # 中资医药连锁
]

# 语言/外派信号（岗位级）
LANG_PATTERNS = [
    r"英语", r"英文", r"English", r"外派", r"驻外", r"overseas", r"Overseas",
    # 「海外」开头的岗位一律剔除：海外岗通常要求外语或长期外派
    # （曾漏掉大华的「海外资深解决方案工程师」，故改为宽匹配）
    r"海外", r"出海", r"国际业务", r"国际销售", r"International",
    r"出差新加坡", r"出差美国", r"出差日本", r"出国", r"雅思", r"托福", r"双语",
    r"日韩", r"欧美", r"东南亚", r"中东", r"拉美", r"非洲",
]


def has_lang_require(text):
    t = text or ""
    return [p for p in LANG_PATTERNS if re.search(p, t)]


def is_chinese_backed(comp):
    return any(k in (comp or "") for k in CHINESE_BACKED)


def main():
    m = json.load(open(os.path.join(HERE, "master_companies.json"), encoding="utf-8"))
    fo = json.load(open(os.path.join(HERE, "research_foreign.json"), encoding="utf-8"))

    # 外企公司名集合 + 母国映射
    foreign_map = {}
    for x in fo:
        c = (x.get("company") or "").strip()
        if c:
            foreign_map[c] = x.get("country") or "未知"

    keep, excluded = [], []

    for x in m:
        comp = x.get("company") or ""
        roles = x.get("relevant_roles") or []
        reasons = []

        # A) 真外企
        is_foreign = ("外企" in (x.get("sources") or [])) or (comp in foreign_map)
        if is_foreign and not is_chinese_backed(comp):
            country = foreign_map.get(comp, "未知")
            reasons.append(f"外企（{country}），通常要求英语")

        # B) 岗位级语言要求
        role_lang = []
        clean_roles = []
        for r in roles:
            hit = has_lang_require(r)
            if hit:
                role_lang.append(f"{r[:30]}({','.join(hit[:2])})")
            else:
                clean_roles.append(r)
        if role_lang:
            reasons.append(f"岗位含语言要求: {'; '.join(role_lang[:2])}")

        if reasons:
            # 只排除该岗位；若公司是外企则整家排除
            if is_foreign and not is_chinese_backed(comp):
                excluded.append({**x, "exclude_reason": "；".join(reasons),
                                 "exclude_scope": "整家公司"})
            else:
                # 国内公司：剔除有语言要求的岗位，保留其余
                if clean_roles:
                    keep.append({**x, "relevant_roles": clean_roles,
                                 "lang_removed": role_lang,
                                 "note": f"已剔除需语言的岗位: {'; '.join(role_lang[:2])}"})
                else:
                    excluded.append({**x, "exclude_reason": "；".join(reasons),
                                     "exclude_scope": "该公司仅有语言要求岗位"})
        else:
            keep.append(x)

    json.dump(keep, open(os.path.join(HERE, "master_no_lang.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(excluded, open(os.path.join(HERE, "master_lang_excluded.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)

    print("=" * 84)
    print(f"原清单: {len(m)} 家")
    print(f"排除后: {len(keep)} 家（可投）")
    print(f"被排除: {len(excluded)} 家")
    print("=" * 84)

    print("\n排除原因分布:")
    for r, n in Counter(
        ("外企（语言要求）" if "外企" in e["exclude_reason"] else "岗位含语言要求")
        for e in excluded
    ).most_common():
        print(f"  {n:4d}  {r}")

    print(f"\n保留的中资背景（港台注册但中文办公）:")
    for k in CHINESE_BACKED:
        f = [x for x in keep if k in (x.get("company") or "")]
        if f:
            print(f"  ✅ {f[0]['company']}")

    print(f"\n排除后未联系过的: {len([x for x in keep if not x.get('already_contacted')])}")
    print(f"\n未联系 + 匹配分≥8（优先池）:")
    hi = [x for x in keep if not x.get("already_contacted") and (x.get("ai_score") or 0) >= 8]
    for i, x in enumerate(hi, 1):
        print(f"  {i:2d}. [{x['ai_score']:2d}] {x['company'][:30]:30s} | {(x.get('sector') or '')[:30]}")


if __name__ == "__main__":
    main()
