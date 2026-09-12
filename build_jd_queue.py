# -*- coding: utf-8 -*-
"""准备公司岗位的 JD 抓取清单：去重、排优先级、排除实习岗。

优先级（高→低）：
  1. 岗位名含 FDE/前沿部署/前线部署 → 最对口
  2. 含 交付/实施/解决方案/售前
  3. 含 AI/大模型/Agent
  4. 薪资落在 15-25K（用户期望区间）加分
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "jd_todo_company.json")
OUT = os.path.join(HERE, "jd_queue.json")

FDE = r"FDE|前沿部署|前线部署|前向部署|forward deploy"
DELIVER = r"交付|实施|解决方案|售前|客户成功|技术支持|项目经理|部署"
AI = r"AI|ai|大模型|模型|Agent|agent|智能体|算法|机器学习|数智|智能化|RAG|LLM"


def score(j):
    n = j.get("jobName") or ""
    s = 0
    if re.search(FDE, n, re.I):
        s += 10
    if re.search(r"交付|实施", n):
        s += 5
    if re.search(r"解决方案|售前|客户成功", n):
        s += 4
    if re.search(r"项目(交付)?经理", n):
        s += 3
    if re.search(AI, n):
        s += 4
    lo = j.get("salary_low")
    if lo:
        if 15 <= lo <= 28:
            s += 3
        elif lo > 40:
            s -= 2          # 纯算法专家岗，门槛高
    # 明确排除
    if re.search(r"实习|兼职|校招|27届|管培", n):
        s -= 20
    if re.search(r"算法工程师|算法专家|算法负责人", n) and not re.search(r"交付|实施|解决方案", n):
        s -= 3
    # 日薪岗（实习）
    if re.search(r"元/天", j.get("salary") or ""):
        s -= 20
    return s


def main():
    todo = json.load(open(SRC, encoding="utf-8"))

    # 去重（eid）
    seen, uniq = set(), []
    for j in todo:
        e = j.get("eid")
        if not e or e in seen:
            continue
        seen.add(e)
        uniq.append(j)
    print(f"原始 {len(todo)} 条 → 按 eid 去重后 {len(uniq)} 条")

    for j in uniq:
        if j.get("salary_low") is None:
            m = re.search(r"(\d+)-(\d+)\s*[Kk]", j.get("salary") or "")
            if m:
                j["salary_low"] = int(m.group(1))
        j["priority"] = score(j)

    # 剔除实习/日薪岗
    keep = [j for j in uniq if j["priority"] > -10]
    drop = [j for j in uniq if j["priority"] <= -10]
    print(f"剔除实习/日薪岗 {len(drop)} 条 → 保留 {len(keep)} 条")

    keep.sort(key=lambda x: (-x["priority"], -(x.get("salary_low") or 0)))
    json.dump(keep, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print()
    print("=" * 92)
    print(f"JD 抓取队列：{len(keep)} 个岗位（按优先级排序）")
    print("=" * 92)
    for i, j in enumerate(keep[:40], 1):
        print(f"{i:3d}. [{j['priority']:3d}] {j['company'][:22]:22s} | "
              f"{j['jobName'][:40]:40s} | {j['salary']}")
    if len(keep) > 40:
        print(f"  ... 其余 {len(keep) - 40} 条见 {os.path.basename(OUT)}")

    # 按公司统计
    from collections import Counter
    c = Counter(j["company"] for j in keep)
    print(f"\n涉及 {len(c)} 家公司")
    print("公司岗位数 Top 10:", dict(c.most_common(10)))


if __name__ == "__main__":
    main()
