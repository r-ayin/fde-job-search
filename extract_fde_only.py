# -*- coding: utf-8 -*-
"""提取「明确 FDE」岗位（纯本地处理，零网络）。

用户口径：只针对明确 FDE 的岗位，其他先保存。

明确 FDE 的判定（双重）：
  1. 岗位标题含 FDE / 前沿部署 / 前线部署 / 前向部署 / forward deployed
  2. 且 JD 判定（若有正文）不是非 FDE
其余岗位保留在 fde_all.json（原始存档），不删除。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from dom_tools import decode_pua_salary  # noqa: E402

# 标题必须命中其一
FDE_MARKS = ["fde", "前沿部署", "前线部署", "前向部署", "forward deployed"]
# 标题命中但实际不是 FDE 岗的排除项（实习/兼职/销售/运营等）
EXCLUDE = ["实习生", "实习", "兼职", "销售", "运营", "客服", "标注", "评测",
           "质检", "培训", "讲师", "商务", "渠道", "地推", "美工", "设计",
           "视频", "剪辑", "新媒体", "产品经理", "客户经理", "商务方向",
           "HR", "人事", "财务", "行政", "采购", "助理", "文员"]


def parse_salary(s):
    s = (s or "").strip()
    if not s or "面议" in s:
        return None
    m = re.search(r"(\d+)-(\d+)\s*元\s*/\s*天", s)
    if m:
        return (int(m.group(1)) * 21.75 / 1000, int(m.group(2)) * 21.75 / 1000)
    m = re.search(r"(\d+)-(\d+)\s*[Kk]", s)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = re.search(r"(\d+)-(\d+)\s*元\s*/\s*(月|時|时)", s)
    if m:
        v = int(m.group(1)) / 1000, int(m.group(2)) / 1000
        if m.group(3) in ("時", "时"):
            return (v[0] * 174, v[1] * 174)
        return v
    return None


def main():
    path = "fde_all.json"
    if not os.path.exists(path):
        st = json.load(open("fde_collect_state.json", encoding="utf-8"))
        jobs = list(st["jobs"].values())
    else:
        jobs = json.load(open(path, encoding="utf-8"))
    print(f"原始采集岗位: {len(jobs)}")

    fde, not_fde = [], []
    for j in jobs:
        name = (j.get("jobName") or "").strip()
        low = name.lower()
        sal = decode_pua_salary(j.get("salary") or "")
        if not any(k in low for k in FDE_MARKS):
            not_fde.append({**j, "salary": sal, "reason": "标题无 FDE 标识"})
            continue
        if any(k in name for k in EXCLUDE):
            not_fde.append({**j, "salary": sal, "reason": "标题命中排除词"})
            continue
        rng = parse_salary(sal)
        fde.append({**j, "salary": sal,
                    "salary_low": rng[0] if rng else None,
                    "salary_high": rng[1] if rng else None})

    # 去重（公司 + 岗位）
    seen, uniq = set(), []
    for j in fde:
        k = (j.get("company"), j.get("jobName"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(j)

    # 排序：薪资高的优先，可解析薪资的排前面
    def rank(x):
        lo, hi = x.get("salary_low"), x.get("salary_high")
        if lo is None:
            return (2, 0, 0)
        if lo >= 15:
            return (0, -lo, 0)
        return (1, -lo, 0)

    uniq.sort(key=rank)

    json.dump(uniq, open("fde_jobs_only.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(not_fde, open("non_fde_archive.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\n{'=' * 84}")
    print(f"明确 FDE 岗位: {len(uniq)}  （已写入 fde_jobs_only.json）")
    print(f"其余岗位已存档: {len(not_fde)}  （non_fde_archive.json，未删除）")
    print(f"{'=' * 84}")

    # 薪资分布
    lo15 = [x for x in uniq if x.get("salary_low") is not None and x["salary_low"] >= 15]
    print(f"\n其中薪资下限 ≥15K 的: {len(lo15)} 个")
    print(f"\n{'─' * 84}")
    print("薪资 ≥15K 的明确 FDE 岗位")
    print(f"{'─' * 84}")
    for i, x in enumerate(lo15, 1):
        print(f"{i:3d}. {x.get('company')} | {x.get('jobName')} | {x.get('salary')}")

    print(f"\n{'─' * 84}")
    print("薪资 <15K 或面议的明确 FDE 岗位（前 30）")
    print(f"{'─' * 84}")
    for i, x in enumerate([y for y in uniq if y not in lo15][:30], 1):
        print(f"{i:3d}. {x.get('company')} | {x.get('jobName')} | {x.get('salary')}")


if __name__ == "__main__":
    main()
