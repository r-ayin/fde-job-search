# -*- coding: utf-8 -*-
"""搜集三：筛选新岗位候选（纯本地，零网络）。

从 search_new.json 里筛出符合求职方向的岗位：
  - 岗位名与 FDE / 前沿部署 / AI 交付落地相关
  - 排除运营、销售、标注、评测、实习、兼职等
  - 薪资落在合理区间
  - 排除已联系过的公司
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from dom_tools import decode_pua_salary  # noqa: E402

# 正面关键词（岗位名命中即保留）
POS = ["fde", "前沿部署", "前线部署", "前向部署", "forward deploy",
       "交付工程师", "实施工程师", "部署工程师", "解决方案", "解决方案架构",
       "应用工程师", "ai工程", "大模型", "agent", "智能体", "ai产品", "ai应用",
       "ai落地", "技术专家", "落地工程师", "客户成功"]
# 负面关键词（命中即排除）
NEG = ["运营", "销售", "商务", "市场", "主播", "直播", "客服", "美工", "设计",
       "标注", "评测", "质检", "审核", "数据录入", "文员", "助理", "实习生",
       "实习", "兼职", "地推", "电销", "渠道", "招聘", "hr", "人事", "财务",
       "行政", "采购", "客服专员", "咨询顾问", "培训师", "讲师", "文案", "编辑",
       "视频", "剪辑", "新媒体", "投放", "增长", "电商运营", "店长", "外贸业务",
       "测试工程师", "运维", "前端开发", "后端开发", "java", "c++", "算法工程师"]


def parse_salary(s):
    """把薪资字符串解析为月薪区间 (low, high) 千元；无法解析返回 None。"""
    s = (s or "").strip()
    if not s or "面议" in s:
        return None
    # 元/天 -> 月薪（按 21.75 天）
    m = re.search(r"(\d+)-(\d+)\s*元/天", s)
    if m:
        return (int(m.group(1)) * 21.75 / 1000, int(m.group(2)) * 21.75 / 1000)
    m = re.search(r"(\d+)-(\d+)\s*[Kk]", s)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = re.search(r"(\d+)-\s*(\d+)\s*元/月", s)
    if m:
        return (int(m.group(1)) / 1000, int(m.group(2)) / 1000)
    return None


def main():
    jobs = json.load(open("search_new.json", encoding="utf-8"))
    print(f"原始岗位: {len(jobs)}")

    # 已联系公司（历史发送 + 会话）
    contacted = set()
    for f in ["sent_2026-09-11.json", "send_results_v4.json", "send_targets.json"]:
        try:
            d = json.load(open(f, encoding="utf-8"))
            for x in (d if isinstance(d, list) else d.values()):
                b = (x.get("brand") or x.get("company") or "").strip()
                if b:
                    contacted.add(b)
        except Exception:
            pass
    # 会话列表里的公司（已打过招呼）
    try:
        for r in json.load(open("collect_chats.json", encoding="utf-8")):
            who = r.get("who") or ""
            m = re.search(r"[\u4e00-\u9fff]{2,}(?:网络)?(?:科技|传媒|集团|软件|信息|智能|公司|技术|电子|教育)?", who)
            if m:
                contacted.add(m.group(0))
    except Exception:
        pass
    print(f"已联系/已有会话公司: {len(contacted)}")

    kept, dropped = [], {"neg": 0, "salary": 0, "contacted": 0, "pos": 0}
    for j in jobs:
        name = (j.get("jobName") or "").strip()
        comp = (j.get("company") or "").strip()
        sal = decode_pua_salary(j.get("salary") or j.get("salaryRaw") or "")
        low = name.lower()

        # 必须命中正面词
        if not any(k in low for k in POS):
            dropped["pos"] += 1
            continue
        # 命中负面词则排除
        if any(k in low for k in NEG):
            dropped["neg"] += 1
            continue
        # 薪资区间
        rng = parse_salary(sal)
        if rng is None:
            dropped["salary"] += 1
            continue
        lo, hi = rng
        if hi < 10 or lo > 45:
            dropped["salary"] += 1
            continue
        # 已联系
        if any(comp and (comp in c or c in comp) for c in contacted):
            dropped["contacted"] += 1
            continue

        kept.append({**j, "salary": sal, "salary_low": lo, "salary_high": hi})

    # 去重（公司+岗位）
    seen, uniq = set(), []
    for k in kept:
        key = (k.get("company"), k.get("jobName"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(k)

    print(f"\n筛选结果: 保留 {len(uniq)} | 排除 {dropped}")

    # 按薪资接近用户期望（15-25K）排序
    def rank(x):
        lo, hi = x["salary_low"], x["salary_high"]
        # 与 15-25K 区间的贴合度：完全落在区间内最优
        if lo >= 15 and hi <= 30:
            return 0
        if hi < 15:
            return 2
        return 1

    uniq.sort(key=lambda x: (rank(x), -x["salary_low"]))
    json.dump(uniq, open("candidates_new.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\n{'=' * 88}")
    print("新岗位候选（按匹配优先级排序）")
    print(f"{'=' * 88}")
    for i, x in enumerate(uniq[:50], 1):
        print(f"{i:3d}. {x.get('company')} | {x.get('jobName')} | {x.get('salary')}")
    print(f"\n共 {len(uniq)} 条，已写入 candidates_new.json")


if __name__ == "__main__":
    main()
