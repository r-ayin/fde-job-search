# -*- coding: utf-8 -*-
"""生成一张模拟 BOSS 岗位卡列表的测试图，用于验证 OCR 精度。"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1100, 760
img = Image.new("RGB", (W, H), "#f5f6f8")
d = ImageDraw.Draw(img)

def font(size, bold=False):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

F_TITLE = font(22, True)
F_SAL   = font(20, True)
F_TAG   = font(14)
F_BTN   = font(17, True)

# 模拟若干岗位卡
jobs = [
    ("FDE（AI 交付工程师）", "15-25K", "杭州 3-5年 本科", "立即沟通", "南通五棵葱文化传媒"),
    ("前沿部署工程师（FDE）", "18-30K·13薪", "杭州 1-3年 本科", "立即沟通", "云智创心科技"),
    ("FDE前向部署工程师", "12-18K·13薪", "杭州 经验不限", "继续沟通", "杭州雾楼台"),
    ("FDE工程师（客户成功方向）", "15-25K", "杭州 3-5年 本科", "立即沟通", "北京天润融通"),
    ("前沿部署工程师（AI Agent）", "16-28K·14薪", "杭州 1-3年 硕士", "立即沟通", "箴理科技"),
]
y = 24
for title, sal, meta, btn, comp in jobs:
    d.rounded_rectangle([20, y, W-20, y+128], radius=10, fill="white", outline="#e6e7eb")
    d.text((44, y+20), comp + " · 招聘者", font=F_TAG, fill="#9aa0a6")
    d.text((44, y+46), title, font=F_TITLE, fill="#222")
    d.text((W-220, y+44), sal, font=F_SAL, fill="#fe5746")
    d.text((44, y+82), meta, font=F_TAG, fill="#61666d")
    d.rounded_rectangle([W-160, y+74, W-44, y+112], radius=6, fill="#00bebd")
    tb = d.textbbox((0, 0), btn, font=F_BTN)
    d.text((W-102-(tb[2]-tb[0])/2, y+82), btn, font=F_BTN, fill="white")
    y += 144

img.save("test_card.png")
print("saved test_card.png", img.size)
