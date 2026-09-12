# -*- coding: utf-8 -*-
"""从已采集岗位池中，找出 259 家目标公司的所有 AI 相关岗位。

策略：先用本地已有的 5000+ 岗位数据做零成本匹配，
把「公司 + 岗位 + eid」配对好，再决定抓哪些 JD。

输出：
  company_jobs.json   公司 -> 岗位列表（含 eid，可抓 JD）
  need_search.json    未匹配到岗位的公司（需 BOSS 搜索补充）
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def norm(s):
    return re.sub(r"[\s（）()【】\[\]、,，.。·/\\\-_|&+]", "", (s or "")).lower()


# AI 交付/解决方案相关（用户目标岗）
ROLE_KEEP = (r"FDE|前沿部署|前线部署|前向部署|交付|实施|解决方案|售前|"
             r"客户成功|技术支持|项目经理|AI应用|AI产品|大模型|Agent|智能体|"
             r"算法|机器学习|部署|落地|架构师|咨询顾问")
# 明确排除
ROLE_DROP = (r"实习生|实习|兼职|销售|电销|地推|客服专员|运营专员|前台|"
             r"美工|设计|文案|编辑|主播|直播|保安|保洁|司机|人事|财务|行政")
# 语言/海外
ROLE_LANG = (r"海外|出海|国际业务|英语|英文|English|外派|驻外|日韩|欧美|东南亚")


def sal_lo(s):
    m = re.search(r"(\d+)-(\d+)\s*[Kk]", s or "")
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)-(\d+)\s*元/天", s or "")
    if m:
        return int(m.group(1)) * 21.75 / 1000
    return None


def main():
    # 目标公司
    targets = json.load(open(os.path.join(HERE, "master_no_lang.json"), encoding="utf-8"))
    print(f"目标公司: {len(targets)} 家")

    # 岗位池（含 eid，用于抓 JD）
    pool = []
    for f in ["fde_all.json", "non_fde_archive.json", "search_new.json",
              "candidates_new.json", "delivery_todo.json", "fde_jobs_only.json"]:
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
            items = d.values() if isinstance(d, dict) else d
            for x in items:
                if not isinstance(x, dict):
                    continue
                eid = x.get("eid") or x.get("encryptJobId")
                comp = x.get("company") or x.get("brand") or x.get("brandName")
                name = x.get("jobName") or x.get("title")
                if eid and comp and name:
                    pool.append({"eid": eid, "company": comp, "jobName": name,
                                 "salary": x.get("salary") or "",
                                 "salary_low": sal_lo(x.get("salary") or "")})
        except Exception:
            pass
    # 去重
    seen, uniq = set(), []
    for x in pool:
        if x["eid"] in seen:
            continue
        seen.add(x["eid"])
        uniq.append(x)
    pool = uniq
    print(f"岗位池: {len(pool)} 个岗位")

    # 建公司索引
    by_company = {}
    for x in pool:
        by_company.setdefault(norm(x["company"]), []).append(x)

    result, need_search = {}, []
    for t in targets:
        comp = t["company"]
        n = norm(comp)
        jobs = by_company.get(n, [])
        # 包含匹配兜底
        if not jobs:
            for pn, pv in by_company.items():
                if pn and n and (pn in n or n in pn) and min(len(pn), len(n)) >= 5:
                    jobs = pv
                    break
        # 过滤岗位
        keep = []
        for j in jobs:
            nm = j["jobName"]
            if re.search(ROLE_DROP, nm, re.I):
                continue
            if re.search(ROLE_LANG, nm, re.I):
                continue
            if not re.search(ROLE_KEEP, nm, re.I):
                continue
            keep.append(j)
        if keep:
            result[comp] = {
                "company": comp,
                "ai_score": t.get("ai_score"),
                "sector": t.get("sector"),
                "sources": t.get("sources"),
                "jobs": keep,
            }
        else:
            need_search.append(comp)

    json.dump(list(result.values()), open(os.path.join(HERE, "company_jobs.json"), "w",
                                          encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(need_search, open(os.path.join(HERE, "need_search.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, indent=1)

    n_jobs = sum(len(v["jobs"]) for v in result.values())
    print()
    print("=" * 84)
    print(f"✅ 有 AI 相关岗位的公司: {len(result)} 家，共 {n_jobs} 个岗位")
    print(f"❌ 需 BOSS 搜索补充的公司: {len(need_search)} 家")
    print("=" * 84)

    # 按公司展示
    ranked = sorted(result.values(), key=lambda z: -(z.get("ai_score") or 0))
    for v in ranked[:20]:
        print(f"\n■ {v['company']}（{v.get('ai_score')}分 / {v.get('sector') or '—'}）")
        for j in v["jobs"][:6]:
            print(f"    {j['jobName'][:44]:44s} | {j['salary']}")

    return result, need_search


if __name__ == "__main__":
    main()
