# -*- coding: utf-8 -*-
"""视觉层：截图 -> OCR -> 文本匹配定位 -> 真实坐标点击。

用途：把原先靠 DOM 选择器 + 接口调用的读取，换成纯视觉读取。
服务端看不到任何 API 请求，只有正常的页面渲染与鼠标键盘事件。

坐标换算（关键）：
  Page.captureScreenshot 返回的是设备像素图，Input.dispatchMouseEvent 收的是 CSS 像素。
  两者相差一个 devicePixelRatio，所以 css_x = img_x / dpr。
"""
import base64
import io
import re
import time

from PIL import Image

_engine = None


def get_engine():
    """懒加载 OCR 引擎（首次约 1.5s，之后复用）。"""
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR
        _engine = RapidOCR()
    return _engine


class TextBlock:
    __slots__ = ("text", "score", "x0", "y0", "x1", "y1")

    def __init__(self, text, score, x0, y0, x1, y1):
        self.text, self.score = text, float(score)
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2

    def __repr__(self):
        return f"<TextBlock {self.text!r} score={self.score:.3f} @({self.cx:.0f},{self.cy:.0f})>"


def ocr_image(image):
    """对 PIL.Image 或路径跑 OCR，返回 TextBlock 列表。"""
    res = get_engine()(image)
    txts, boxes, scores = getattr(res, "txts", None), getattr(res, "boxes", None), getattr(res, "scores", None)
    if txts is None:
        return []
    out = []
    for t, b, s in zip(txts, boxes, scores):
        xs = [float(p[0]) for p in b]
        ys = [float(p[1]) for p in b]
        out.append(TextBlock(t, s, min(xs), min(ys), max(xs), max(ys)))
    return out


class PageVision:
    """基于 CDP 连接的页面视觉操作。cdp 需实现 send(method, params)。"""

    def __init__(self, cdp, debug=False):
        self.cdp = cdp
        self.debug = debug
        self._dpr = None

    # ---------- 基础能力 ----------

    def dpr(self, refresh=False):
        if self._dpr is None or refresh:
            v = self.cdp.send("Runtime.evaluate", {
                "expression": "window.devicePixelRatio", "returnByValue": True})
            self._dpr = float(v.get("result", {}).get("value") or 1.0)
        return self._dpr

    def screenshot(self, path=None):
        """截取当前视口，返回 PIL.Image。"""
        r = self.cdp.send("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(r["data"])
        img = Image.open(io.BytesIO(data)).convert("RGB")
        if path:
            img.save(path)
        return img

    def scan(self, image=None, save=None):
        """截图并 OCR，返回 (blocks, dpr, image)。"""
        img = image if image is not None else self.screenshot(path=save)
        return ocr_image(img), self.dpr(), img

    # ---------- 定位 ----------

    @staticmethod
    def find(blocks, pattern, min_score=0.5, exact=False):
        """按文本找块。pattern 可为正则或普通子串；返回置信度最高的匹配。"""
        rx = re.compile(pattern if exact else re.escape(pattern))
        hits = [b for b in blocks if b.score >= min_score and rx.search(b.text)]
        if not hits:
            return None
        return max(hits, key=lambda b: b.score)

    @staticmethod
    def find_all(blocks, pattern, min_score=0.5):
        rx = re.compile(re.escape(pattern))
        return [b for b in blocks if b.score >= min_score and rx.search(b.text)]

    def locate(self, pattern, blocks=None, min_score=0.5, save=None):
        """定位文本中心，返回 CSS 像素坐标 (x, y)；找不到返回 None。"""
        if blocks is None:
            blocks, dpr, _ = self.scan(save=save)
        else:
            dpr = self.dpr()
        b = self.find(blocks, pattern, min_score=min_score)
        if b is None:
            return None
        return (b.cx / dpr, b.cy / dpr), b

    # ---------- 操作 ----------

    def click_text(self, pattern, min_score=0.5, save=None, settle=0.12):
        """OCR 定位文本 -> 真实坐标点击。返回是否成功。"""
        from input_primitives import real_click
        loc = self.locate(pattern, min_score=min_score, save=save)
        if loc is None:
            return False, f"not_found:{pattern}"
        (x, y), block = loc
        real_click(self.cdp, x, y)
        time.sleep(settle)
        return True, f"clicked:{block.text}@({x:.0f},{y:.0f})"

    def read_text(self, save=None):
        """读全页文本（按 y 再按 x 排序，拼成阅读顺序）。"""
        blocks, _, _ = self.scan(save=save)
        rows = {}
        for b in blocks:
            key = round(b.cy / 18)
            rows.setdefault(key, []).append(b)
        lines = []
        for key in sorted(rows):
            lines.append(" ".join(b.text for b in sorted(rows[key], key=lambda x: x.cx)))
        return "\n".join(lines)
