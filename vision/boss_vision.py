# -*- coding: utf-8 -*-
"""岗位列表视觉读取：用截图 + OCR 替代 joblist.json 接口调用。

原方案每翻一页要调一次 /wapi/zpgeek/search/joblist.json，服务端完全可见。
视觉方案只滚动页面 + 截图，服务端只看到正常的页面浏览。

卡片结构（BOSS 搜索结果页）：
    公司名 · 招聘者        <- 小字灰色
    岗位名称               <- 标题
    薪资                   <- 右侧红色
    城市 经验 学历          <- 小字
    [立即沟通 / 继续沟通]   <- 按钮
"""
import re

# 薪资：15-25K / 18-30K·13薪 / 200-300元/天
RE_SALARY = re.compile(r"(\d+\s*-\s*\d+\s*[Kk]|\d+\s*-\s*\d+\s*元|面议)")
# 按钮文案
BTN_TEXTS = {"立即沟通", "继续沟通", "已沟通"}
# 元信息行：城市 + 经验 + 学历
RE_META = re.compile(r"(经验|应届|\d+\s*-\s*\d+年|不限)")


def _rows(blocks, tol=14):
    """把文本块按 y 聚成行（同一行的块 y 中心差在 tol 内）。"""
    rows = []
    for b in sorted(blocks, key=lambda b: b.cy):
        for r in rows:
            if abs(r["cy"] - b.cy) <= tol:
                r["items"].append(b)
                r["cy"] = sum(x.cy for x in r["items"]) / len(r["items"])
                break
        else:
            rows.append({"cy": b.cy, "items": [b]})
    rows.sort(key=lambda r: r["cy"])
    for r in rows:
        r["items"].sort(key=lambda b: b.x0)
        r["text"] = " ".join(b.text for b in r["items"])
    return rows


def parse_job_cards(blocks):
    """从 OCR 块解析出岗位卡片列表。

    几何分区法：按钮（立即沟通/继续沟通）总是位于卡片底部，且与"城市·经验·学历"
    同一行。因此以相邻两个按钮的 y 为界，把块切成一张张卡片；在每个区间内再按
    内容特征分类。这样避免了"按行拼接后误判"的问题。
    """
    btns = sorted([b for b in blocks if b.text.strip() in BTN_TEXTS], key=lambda b: b.cy)
    cards = []
    for k, btn in enumerate(btns):
        lo = btns[k - 1].cy if k > 0 else float("-inf")
        hi = btn.cy
        region = [b for b in blocks
                  if lo < b.cy <= hi and b.text.strip() not in BTN_TEXTS]
        card = {"button": btn.text.strip(), "button_y": btn.cy,
                "button_blocks": [btn], "button_x": btn.cx}
        for b in region:
            t = b.text.strip()
            m = RE_SALARY.search(t)
            if m and not card.get("salary"):
                card["salary"] = m.group(1)
                continue
            if "·招聘" in t and not card.get("company"):
                card["company"] = t.split("·")[0].strip()
                continue
            if RE_META.search(t) and not card.get("meta"):
                card["meta"] = t
                continue
            if _looks_like_title(t) and not card.get("title"):
                card["title"] = t
        cards.append(card)
    cards.sort(key=lambda c: c["button_y"])
    return cards


def _looks_like_title(t):
    """粗判是否岗位标题：有中文/字母，且不是元信息/公司行/薪资。"""
    if not t or len(t) < 2 or len(t) > 40:
        return False
    if "招聘" in t:
        return False
    if RE_SALARY.search(t):
        return False
    if RE_META.search(t) and len(t) < 20:
        return False
    if re.match(r"^[\d\s\-.,%Kk元/]+$", t):
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", t))


def dedupe(cards):
    """按 (title, company) 去重，保留首次出现。"""
    seen, out = set(), []
    for c in cards:
        key = (c.get("title"), c.get("company"))
        if key == (None, None) or key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


class JobListReader:
    """滚动搜索页并逐屏 OCR，累积岗位卡片。"""

    def __init__(self, pv, scroll_x=None, scroll_y=None):
        self.pv = pv
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self.seen = []

    def scan_once(self, save=None):
        blocks, dpr, img = self.pv.scan(save=save)
        return parse_job_cards(blocks), img

    def collect(self, screens=4, scroll_dy=700, settle=1.2, save_dir=None,
                on_screen=None):
        """连续滚动采集多屏。返回去重后的岗位列表。"""
        from input_primitives import human_scroll
        import time
        import os

        all_cards = []
        for s in range(screens):
            shot = None
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
                shot = os.path.join(save_dir, f"screen_{s:02d}.png")
            cards, img = self.scan_once(save=shot)
            all_cards.extend(cards)
            if on_screen:
                on_screen(s, cards, img)
            if s < screens - 1:
                x = self.scroll_x if self.scroll_x is not None else img.size[0] / self.pv.dpr() / 2
                y = self.scroll_y if self.scroll_y is not None else img.size[1] / self.pv.dpr() / 2
                human_scroll(self.pv.cdp, x, y, -scroll_dy)
                time.sleep(settle)
        self.seen = dedupe(all_cards)
        return self.seen
