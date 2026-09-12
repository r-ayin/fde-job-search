# -*- coding: utf-8 -*-
"""CDP 输入原语：真实坐标点击 + 文本输入。

替代原先的 `element.click()`（isTrusted=False）与一次性 DOM 改写。
都用浏览器进程级输入通道，产生 isTrusted=True 的真实事件链。

已在本地自测页验证：
  - dispatchMouseEvent -> pointerdown/mousedown/pointerup/mouseup/click，全部 trusted
  - 逐字符 dispatchKeyEvent -> 每字 keydown/beforeinput/input/keyup，中文正确
"""
import random
import time

# 人类打字速度参考：中文聊天输入大约 3-8 字/秒
DEFAULT_MIN_DELAY = 0.045
DEFAULT_MAX_DELAY = 0.14


def real_click(cdp, x, y, settle=0.08, pre_move=True):
    """在 CSS 像素坐标 (x, y) 发真实鼠标事件链。

    比 element.click() 多出的关键点：先 pointer/mouse 移动到位，再按下抬起，
    事件 isTrusted=True，且带完整的 pointerdown->mousedown->pointerup->mouseup->click 序列。
    """
    if pre_move:
        # 分两步移动，模拟真实指针轨迹
        cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y, "button": "none", "buttons": 0})
        time.sleep(0.03)
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": x, "y": y, "button": "none", "buttons": 0})
    time.sleep(settle)
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": x, "y": y,
        "button": "left", "buttons": 1, "clickCount": 1})
    time.sleep(random.uniform(0.04, 0.10))  # 按下到抬起的自然停顿
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": x, "y": y,
        "button": "left", "buttons": 0, "clickCount": 1})


def insert_text(cdp, text):
    """一次性插入整段文本（含换行），走文本插入通道。

    ⚠️ 必须用它来写入含换行的消息正文，不要用 type_text。
    原因（2026-09-11 实际事故）：BOSS 聊天输入框是「按 Enter 发送」模式。
    type_text 逐字符派发时，消息里的 \\n 若作为真实 Enter 键发出，
    会在输入过程中把已输入内容**分段发送给 HR**。
    实测误发后果：一条 4 段文案被拆成 8 条消息发出。

    insertText 不产生按键事件，因此换行安全；事件本身仍是 isTrusted=True。
    """
    cdp.send("Input.insertText", {"text": text})


def type_text(cdp, text, min_delay=DEFAULT_MIN_DELAY, max_delay=DEFAULT_MAX_DELAY,
              newline_as_enter=False):
    """逐字符输入，每个字符产生 keydown/keyup 事件。

    ⚠️ 危险：text 中若含 \\n，且目标输入框是「Enter 发送」模式，
    会边输入边发送（newline_as_enter=False 时 Enter 仍会被派发，只是带文本）。
    写聊天消息正文请改用 insert_text。

    与 Input.insertText 的区别：insertText 一次性插入整段，只产生
    beforeinput+input 两个事件、零 keydown；这里逐字派发键盘事件。
    仅适用于**不含换行**的短文本（如搜索框关键词）。
    """
    if "\n" in text:
        raise ValueError(
            "type_text 收到含换行的文本。写聊天消息请用 insert_text，"
            "否则 BOSS 会按 Enter 分段发送。若确需逐字输入换行，"
            "请显式传 newline_as_enter=True 并自行确认目标输入框不会触发发送。")
    for ch in text:
        if ch == "\n":
            if newline_as_enter:
                cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Enter", "code": "Enter",
                    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
                cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Enter", "code": "Enter",
                    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
            else:
                cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": "\r", "unmodifiedText": "\r", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
                cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Enter", "code": "Enter",
                    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
        else:
            cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "text": ch, "unmodifiedText": ch, "key": ch})
            cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": ch})
        time.sleep(random.uniform(min_delay, max_delay))


def human_scroll(cdp, x, y, total_dy, steps=None, min_delay=0.02, max_delay=0.07):
    """平滑滚动：拆成多步小位移，避免一次性大跳。"""
    if steps is None:
        steps = max(3, int(abs(total_dy) / 120))
    for _ in range(steps):
        cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": x, "y": y,
            "deltaX": 0, "deltaY": total_dy / steps})
        time.sleep(random.uniform(min_delay, max_delay))


def press_key(cdp, key, code=None, keycode=None, modifiers=0):
    """派发一次按键（含修饰键）。modifiers: Alt=1, Ctrl=2, Meta=4, Shift=8。"""
    params = {"type": "keyDown", "key": key, "modifiers": modifiers}
    if code:
        params["code"] = code
    if keycode:
        params["windowsVirtualKeyCode"] = keycode
        params["nativeVirtualKeyCode"] = keycode
    cdp.send("Input.dispatchKeyEvent", params)
    up = dict(params)
    up["type"] = "keyUp"
    cdp.send("Input.dispatchKeyEvent", up)


def clear_field(cdp):
    """用 Ctrl+A + Delete 清空输入框。

    替代 `el.innerHTML=''`——那是直接改 DOM，会留下脚本痕迹；
    这里走真实按键，事件 isTrusted=True。
    """
    press_key(cdp, "a", code="KeyA", keycode=65, modifiers=2)
    time.sleep(random.uniform(0.05, 0.12))
    press_key(cdp, "Delete", code="Delete", keycode=46)
    time.sleep(random.uniform(0.05, 0.12))
