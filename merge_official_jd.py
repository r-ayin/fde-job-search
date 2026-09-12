# -*- coding: utf-8 -*-
"""合并三个官网 JD 来源，筛出 AI/交付相关岗位，判定是否 FDE 类。

输入：
  official_jd.json        MokaHR 11 家（215 条）
  beisen_jd.json          北森 6 家（86 条）
  official_misc_jd.json   其他官网（557 条）

输出：
  official_jd_all.json    合并去重全量
  official_jd_fde.json    筛出的 AI/交付相关岗位（带 FDE 判定）
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "vision"))

from fde_classify import is_fde  # noqa: E402

SOURCES = ["official_jd.json", "beisen_jd.json", "official_misc_jd.json"]

# 岗位名必须命中（AI 交付/解决方案向）
ROLE_KEEP = (r"FDE|前沿部署|前线部署|前向部署|交付|实施|解决方案|售前|"
             r"客户成功|技术支持|项目经理|大模型|Agent|智能体|AI应用|AI产品|"
             r"算法|机器学习|部署|架构师|咨询")
# 明确排除
ROLE_DROP = (r"实习生|实习|兼职|校招|27届|2027届|保安|保洁|司机|"
             r"会计|出纳|人事|行政|法务|前台|销售代表|电销|地推")
# 语言/海外
ROLE_LANG = (r"海外|出海|国际业务|英语|英文|English|外派|驻外|日韩|欧美|东南亚")


def sal_lo(s):
    m = re.search(r"(\d+)-(\d+)\s*[Kk]", s or "")
    if m:
        return int(m.group(1))
    return None


def main():
    all_recs = {}
    for fn in SOURCES:
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            print(f"  跳过 {fn}")
            continue
        d = json.load(open(p, encoding="utf-8"))
        for x in d:
            uid = x.get("uid")
            if not uid:
                uid = f"{x.get('company')}:{x.get('title')}"
                x["uid"] = uid
            if uid not in all_recs:
                all_recs[uid] = x
        print(f"  {fn:28s} {len(d):4d} 条")

    all_jd = list(all_recs.values())
    print(f"\n合并去重: {len(all_jd)} 条")

    kept, dropped = [], {"role": 0, "drop": 0, "lang": 0, "nojd": 0, "dup": 0}
    for x in all_jd:
        title = x.get("title") or ""
        jd = x.get("jd") or ""
        if len(jd) < 50:
            dropped["nojd"] += 1
            continue
        if re.search(ROLE_DROP, title, re.I):
            dropped["drop"] += 1
            continue
        if re.search(ROLE_LANG, title, re.I) or re.search(ROLE_LANG, jd[:400], re.I):
            dropped["lang"] += 1
            continue
        if not re.search(ROLE_KEEP, title, re.I):
            dropped["role"] += 1
            continue
        kept.append(x)

    # FDE 判定
    for x in kept:
        v, s, why = is_fde(x.get("jd"), x.get("title"))
        x["fde_verdict"] = {True: "FDE", False: "非FDE", None: "边界"}[v]
        x["fde_score"] = s
        x["fde_reason"] = why

    # 排序：FDE 判定优先，再按分数
    order = {"FDE": 0, "边界": 1, "非FDE": 2}
    kept.sort(key=lambda x: (order[x["fde_verdict"]], -x["fde_score"]))

    json.dump(all_jd, open(os.path.join(HERE, "official_jd_all.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(kept, open(os.path.join(HERE, "official_jd_fde.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\n{'=' * 90}")
    print(f"筛选结果: {len(kept)} 条 (原始 {len(all_jd)})")
    print(f"排除: {dropped}")
    print(f"{'=' * 90}")

    from collections import Counter
    print("\nFDE 判定分布:", dict(Counter(x["fde_verdict"] for x in kept)))
    print("\n按公司:")
    for k, v in Counter(x.get("company") for x in kept).most_common():
        print(f"  {v:4d}  {k}")

    print(f"\n{'─' * 90}")
    print("FDE / 边界 岗位（前 45）")
    print(f"{'─' * 90}")
    n = 0
    for x in kept:
        if x["fde_verdict"] == "非FDE":
            continue
        n += 1
        if n > 45:
            break
        print(f"{n:3d}. [{x['fde_verdict']:4s}{x['fde_score']:3d}] {x.get('company')[:18]:18s} | "
              f"{(x.get('title') or '')[:40]:40s} | JD {len(x.get('jd') or '')}字")

    return kept


if __name__ == "__main__":
    main()
