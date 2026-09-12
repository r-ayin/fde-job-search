# -*- coding: utf-8 -*-
"""从 AI 交付类岗位中选出最匹配的 Top 30（纯本地，零网络）。

用户要求：2026-09-14（下周一）09:30 投一次，30 条。

排序依据（与用户定位「AI 应用落地 + 电商垂直 + toB 交付」对齐）：
  +5  岗位名含 AI/大模型/Agent/智能体/智能化 + 交付/实施/解决方案
  +3  含 交付
  +3  含 实施
  +2  含 解决方案/顾问/专家
  +2  含 电商/跨境
  -6  算法岗（视觉/感知/CV/NPU/编译器/推理/训练）
  -5  硬件部署（机器人/AGV/仓储/无人机/智能家居/暖通/产线）
  -5  培训/课程/导师/老师
  -4  内容生成（AIGC/漫剧/艺人）
  +2  薪资 15-35K（用户期望区间）
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

SRC = "delivery_todo.json"
OUT = "delivery_top30.json"

ALGO = r"视觉算法|感知|CV算法|NPU|编译器|推理|模型训练|算法工程师|端侧|具身|世界模型|调优"
HARDWARE = (r"机器人|AGV|仓储|物流|无人机|智能家居|全屋智能|暖通|产线|非标自动化|"
            r"巡检|IoT|智能硬件|园区|PLC|调试")
TRAIN = r"导师|老师|课程|培训|讲师|教练"
CONTENT = r"AIGC|漫剧|艺人|短视频|内容"
TRAD = r"ERP|WMS|MES|CRM|金蝶|用友|SAP|进销存"


def score(x):
    n = x.get("jobName") or ""
    comp = x.get("company") or ""
    s = 0
    blob = n + " " + comp
    if re.search(r"AI|ai|大模型|Agent|agent|智能体|智能化|数智", n) and \
       re.search(r"交付|实施|解决方案|顾问", n):
        s += 5
    if re.search(r"交付", n):
        s += 3
    if re.search(r"实施", n):
        s += 3
    if re.search(r"解决方案|顾问|专家", n):
        s += 2
    if re.search(r"电商|跨境|零售|商家", blob):
        s += 2
    if re.search(ALGO, n, re.I):
        s -= 6
    if re.search(HARDWARE, n, re.I):
        s -= 5
    if re.search(TRAIN, n, re.I):
        s -= 5
    if re.search(CONTENT, n, re.I):
        s -= 4
    if re.search(TRAD, n, re.I) and not re.search(r"AI|ai|大模型", n):
        s -= 4
    lo = x.get("salary_low") or 0
    if 15 <= lo <= 35:
        s += 2
    return s


def main():
    jobs = json.load(open(SRC, encoding="utf-8"))
    print(f"候选: {len(jobs)} 条\n")

    for x in jobs:
        x["match_score"] = score(x)

    ranked = sorted(jobs, key=lambda z: (-z["match_score"], -(z.get("salary_low") or 0)))
    top = ranked[:30]

    print("=" * 96)
    print("Top 30 投递清单（按匹配度排序）")
    print("=" * 96)
    for i, x in enumerate(top, 1):
        print(f"{i:2d}. [{x['match_score']:+2d}] {x.get('company')[:22]:22s} | "
              f"{x.get('jobName')[:40]:40s} | {x.get('salary')}")

    print()
    print(f"低于 0 分被淘汰的: {len([x for x in jobs if x['match_score'] < 0])} 条")

    json.dump(top, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n已写入 {OUT}（{len(top)} 条）")

    # 同时保存剩余，供后续使用
    rest = [x for x in ranked if x not in top]
    json.dump(rest, open("delivery_rest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"剩余 {len(rest)} 条写入 delivery_rest.json")


if __name__ == "__main__":
    main()
