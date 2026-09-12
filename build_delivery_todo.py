# -*- coding: utf-8 -*-
"""构建「交付/实施/部署」投递清单（纯本地处理，零网络）。

用户要求：778 个交付/实施/部署岗位，2026-09-14（下周一）09:30 开始投。

清洗规则：
  1. 标题必须含 交付/实施/部署（这是用户指定的 778 条口径）
  2. 排除实习/兼职/应届/校招/临时
  3. 排除阿里系公司（用户明确要求不发）
  4. 排除已联系过的公司
  5. 排除薪资过低（月薪下限 < 10K）
  6. 排除明显非技术岗（销售/客服/运营/培训/门店/健康/美业等）
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from send_paced import is_ali, is_anonymized  # noqa: E402

ARCHIVE = "non_fde_archive.json"
OUT = "delivery_todo.json"

# 标题必须含其一
MUST = r"交付|实施|部署"
# 排除：模型/推理部署类（这是算法工程岗，不是 FDE 交付）
EXCLUDE_ML = (r"模型部署|推理部署|算法部署|量化部署|端侧部署|sim2real|仿真到现实|"
              r"部署推理|部署优化|部署适配|训练与部署|部署基础设施|部署服务|"
              r"部署科学家|云化部署|云端推理|部署开发|MLOps|推理引擎")
# 排除：非技术交付（人力资源/配送/门店/大健康等）
EXCLUDE_DELIVERY = (r"人力资源|人事|配送|门店|连锁|SPA|大健康|健康交付|医美|"
                    r"体验|见习|交付运营|云交付服务采购|采购专家")
# 排除：非正式用工
EXCLUDE_EMPLOY = r"实习|兼职|应届|校招|管培|临时|日结|小时工|暑|寒假"
# 排除：非技术岗
EXCLUDE_ROLE = (r"销售|客服|运营|培训|讲师|门店|美业|健康|医美|SPA|餐饮|酒店|"
                r"采购|招聘|人事|行政|财务|会计|法务|主播|直播|短视频|内容|"
                r"文案|编辑|设计|美工|视频|市场|商务|渠道|地推|电销|房产|"
                r"保险|金融|贷款|理财|快递|物流配送|司机|保安|保洁")


def parse_salary(s):
    """返回月薪千元区间 (lo, hi)；无法解析返回 (None, None)。"""
    s = (s or "").strip()
    m = re.search(r"(\d+)-(\d+)\s*[Kk]", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)-(\d+)\s*元/天", s)
    if m:
        return (int(m.group(1)) * 21.75 / 1000, int(m.group(2)) * 21.75 / 1000)
    m = re.search(r"(\d+)-(\d+)\s*元/(月|時|时)", s)
    if m:
        lo, hi = int(m.group(1)) / 1000, int(m.group(2)) / 1000
        if m.group(3) in ("時", "时"):
            return lo * 174, hi * 174
        return lo, hi
    m = re.search(r"(\d+)-(\d+)\s*元", s)
    if m:
        return int(m.group(1)) / 1000, int(m.group(2)) / 1000
    return None, None


def main():
    jobs = json.load(open(ARCHIVE, encoding="utf-8"))
    print(f"存档岗位: {len(jobs)}")

    # 已联系公司
    contacted = set()
    for f in ["sent_2026-09-11.json", "send_results_v4.json", "send_targets.json",
              "fde_jobs_only.json", "send_new_fde.json"]:
        try:
            d = json.load(open(f, encoding="utf-8"))
            for x in (d if isinstance(d, list) else d.values()):
                b = (x.get("brand") or x.get("company") or "").strip()
                if b:
                    contacted.add(b)
        except Exception:
            pass
    try:
        for r in json.load(open("collect_chats.json", encoding="utf-8")):
            who = r.get("who") or ""
            m = re.search(r"([\u4e00-\u9fff]{2,}?(?:科技|传媒|集团|软件|信息|智能|网络|"
                          r"技术|电子|数据|咨询|教育|生物|医药|半导体|装备|工业|数字|"
                          r"云计算|股份|控股|通信|系统|服务|有限))", who)
            if m:
                contacted.add(m.group(1))
    except Exception:
        pass
    print(f"已联系公司基准: {len(contacted)}")

    kept, dropped = [], {"role": 0, "employ": 0, "salary": 0, "ali": 0, "contacted": 0}

    for j in jobs:
        name = (j.get("jobName") or "").strip()
        comp = (j.get("company") or "").strip()
        sal = j.get("salary") or ""
        if not re.search(MUST, name):
            continue
        if re.search(EXCLUDE_EMPLOY, name):
            dropped["employ"] += 1
            continue
        if re.search(EXCLUDE_ML, name, re.I):
            dropped["ml"] = dropped.get("ml", 0) + 1
            continue
        if re.search(EXCLUDE_DELIVERY, name):
            dropped["nont"] = dropped.get("nont", 0) + 1
            continue
        if re.search(EXCLUDE_ROLE, name):
            dropped["role"] += 1
            continue
        if is_ali(comp) or is_ali(name):
            dropped["ali"] += 1
            continue
        if comp and any(comp in c or c in comp for c in contacted if len(c) >= 3):
            dropped["contacted"] += 1
            continue
        lo, hi = parse_salary(sal)
        if lo is None or lo < 8:
            dropped["salary"] += 1
            continue
        kept.append({**j, "salary_low": lo, "salary_high": hi})

    # 只要 AI 相关（用户 2026-09-11 指定）：剔除传统软件实施岗
    AI_MARK = (r"AI|ai|智能|大模型|模型|Agent|agent|算法|机器学习|深度学习|"
               r"数字化|数智|RAG|LLM|知识图谱|视觉|语音|自然语言|机器人|自动化")
    TRAD_MARK = (r"ERP|WMS|MES|OA系统|CRM|HR系统|财务系统|进销存|用友|金蝶|"
                 r"管家婆|SAP|Oracle|钉钉|泛微|企业微信")
    ai_kept, ai_drop = [], 0
    for k in kept:
        n = (k.get("jobName") or "")
        if re.search(TRAD_MARK, n, re.I) and not re.search(AI_MARK, n):
            ai_drop += 1
            continue
        if not re.search(AI_MARK, n):
            ai_drop += 1
            continue
        ai_kept.append(k)
    kept = ai_kept
    dropped["non_ai"] = ai_drop

    # 去重（公司+岗位）
    seen, uniq = set(), []
    for k in kept:
        key = (k.get("company"), k.get("jobName"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(k)

    # 排序：薪资高的优先
    uniq.sort(key=lambda x: -x["salary_low"])

    json.dump(uniq, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n{'=' * 84}")
    print(f"投递清单: {len(uniq)} 条  -> {OUT}")
    print(f"排除: {dropped}")
    print(f"{'=' * 84}")
    for i, x in enumerate(uniq[:40], 1):
        print(f"{i:3d}. {x.get('company')[:24]:24s} | {x.get('jobName')[:40]:40s} | {x.get('salary')}")
    if len(uniq) > 40:
        print(f"  ... 其余 {len(uniq) - 40} 条见文件")


if __name__ == "__main__":
    main()
