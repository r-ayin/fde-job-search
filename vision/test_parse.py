# -*- coding: utf-8 -*-
"""用合成岗位卡图验证 boss_vision 的解析逻辑（不接触任何线上服务）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision import ocr_image  # noqa: E402
from boss_vision import parse_job_cards, dedupe, _rows  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
img_path = os.path.join(HERE, "test_card.png")

blocks = ocr_image(img_path)
print(f"OCR 识别 {len(blocks)} 块\n")

print("--- 按行聚合 ---")
for r in _rows(blocks):
    print(f"  y={r['cy']:6.1f}  {r['text']}")

cards = parse_job_cards(blocks)
print(f"\n--- 解析出 {len(cards)} 张岗位卡 ---")
for i, c in enumerate(cards, 1):
    print(f"\n[{i}] 岗位: {c.get('title')}")
    print(f"    公司: {c.get('company')}")
    print(f"    薪资: {c.get('salary')}")
    print(f"    元信息: {c.get('meta')}")
    print(f"    按钮: {c.get('button')}  @y={c['button_y']:.0f}")

print("\n--- 去重后 ---")
for c in dedupe(cards):
    print(f"  {c.get('company')} | {c.get('title')} | {c.get('salary')}")

expected_titles = ["FDE（AI 交付工程师）", "前沿部署工程师（FDE）", "FDE前向部署工程师",
                   "FDE工程师（客户成功方向）", "前沿部署工程师（AI Agent）"]
got = [c.get("title") for c in cards]
print(f"\n期望 {len(expected_titles)} 张卡，实得 {len(got)} 张 -> {'PASS' if len(got) == len(expected_titles) else 'FAIL'}")
n_salary = sum(1 for c in cards if c.get("salary"))
n_company = sum(1 for c in cards if c.get("company"))
print(f"薪资字段齐全: {n_salary}/{len(cards)}   公司字段齐全: {n_company}/{len(cards)}")
