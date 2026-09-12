# -*- coding: utf-8 -*-
"""在独立浏览器实例上验证 CDP 输入原语（不经过 relay，不接触 BOSS）。

验证目标：
  1. Input.dispatchMouseEvent 产生的 click 事件 isTrusted 是否为 True
     （对比 JS element.click() 的 False）
  2. 逐字符 Input.dispatchKeyEvent 能否正确输入中文，事件是否 trusted
  3. Input.insertText 的行为与耗时对比
"""
import itertools
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9333
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "file:///" + os.path.join(HERE, "selftest.html").replace("\\", "/")


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.ids = itertools.count(1)

    def send(self, method, params=None):
        i = next(self.ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == i:
                if "error" in resp:
                    raise RuntimeError(f"{method}: {resp['error']}")
                return resp.get("result", {})

    def ev(self, expr, await_promise=True):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": await_promise})
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:400])
        return r.get("result", {}).get("value")

    def close(self):
        self.ws.close()


def wait_devtools(timeout=25):
    """等 DevTools HTTP 端点起来，返回 page 的 ws 地址。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                targets = json.load(r)
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("devtools endpoint not ready")


def hr(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main():
    profile = tempfile.mkdtemp(prefix="cdp-selftest-")
    args = [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
            "--remote-allow-origins=*",
            "--no-first-run", "--no-default-browser-check", "--disable-fre",
            "--window-size=1000,900", PAGE]
    print("[launch]", " ".join(args[:3]), "...")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = wait_devtools()
        print("[devtools]", ws_url)
        cdp = CDP(ws_url)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        time.sleep(1.5)

        # 确保页面就绪
        for _ in range(20):
            if cdp.ev("!!document.getElementById('btn')"):
                break
            time.sleep(0.4)
        print("[ready] title =", cdp.ev("document.title"), "| dpr =", cdp.ev("window.__dpr()"))

        # ---------- 测试 1：真实坐标点击 ----------
        hr("测试 1：Input.dispatchMouseEvent 真实坐标点击")
        r = cdp.ev("window.__btnRect()")
        # 若窗口尺寸导致按钮在视口外，先滚动到可见
        cdp.ev("document.getElementById('btn').scrollIntoView({block:'center'})")
        time.sleep(0.3)
        r = cdp.ev("window.__btnRect()")
        print("按钮中心 (CSS px):", r)
        cdp.ev("window.__clear()")
        cdp.send("Input.dispatchMouseEvent",
                 {"type": "mouseMoved", "x": r["x"], "y": r["y"], "button": "none", "buttons": 0})
        time.sleep(0.05)
        cdp.send("Input.dispatchMouseEvent",
                 {"type": "mousePressed", "x": r["x"], "y": r["y"],
                  "button": "left", "buttons": 1, "clickCount": 1})
        time.sleep(0.05)
        cdp.send("Input.dispatchMouseEvent",
                 {"type": "mouseReleased", "x": r["x"], "y": r["y"],
                  "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(0.4)
        log1 = cdp.ev("window.__log()")
        print(f"捕获 {len(log1)} 个事件：")
        for e in log1:
            print(f"   {e['t']:<13} trusted={str(e['trusted']):<5} target=#{e['target']} {e['extra']}")
        click_ev = [e for e in log1 if e["t"] == "click"]
        print("\n>>> 结论：dispatchMouseEvent 的 click isTrusted =",
              click_ev[0]["trusted"] if click_ev else "未捕获到 click")

        # ---------- 测试 1b：JS element.click() 对照 ----------
        hr("测试 1b（对照）：JS element.click()")
        cdp.ev("window.__clear()")
        cdp.ev("document.getElementById('btn').click()")
        time.sleep(0.3)
        log1b = cdp.ev("window.__log()")
        for e in log1b:
            print(f"   {e['t']:<13} trusted={str(e['trusted']):<5} target=#{e['target']}")
        click_ev = [e for e in log1b if e["t"] == "click"]
        print("\n>>> 结论：element.click() 的 click isTrusted =",
              click_ev[0]["trusted"] if click_ev else "未捕获到 click")

        # ---------- 测试 2：逐字符输入中文 ----------
        hr("测试 2：逐字符 Input.dispatchKeyEvent 输入中文")
        cdp.ev("document.getElementById('ta').focus()")
        cdp.ev("document.getElementById('ta').innerHTML=''")
        cdp.ev("window.__clear()")
        TEXT = "你好，我想聊聊这个岗位"
        t0 = time.time()
        for ch in TEXT:
            cdp.send("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch,
                                                "unmodifiedText": ch, "key": ch})
            cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": ch})
        dt = time.time() - t0
        time.sleep(0.4)
        val2 = cdp.ev("window.__val()")
        log2 = cdp.ev("window.__log()")
        n_input = len([e for e in log2 if e["t"] == "input"])
        n_keydown = len([e for e in log2 if e["t"] == "keydown"])
        all_trusted = all(e["trusted"] for e in log2 if e["t"] in ("input", "keydown"))
        print(f"输入目标：{TEXT!r}")
        print(f"实际结果：{val2!r}")
        print(f"匹配：{val2 == TEXT}")
        print(f"耗时：{dt:.2f}s（{len(TEXT)} 字，{dt/max(len(TEXT),1)*1000:.0f}ms/字）")
        print(f"input 事件 {n_input} 个 / keydown {n_keydown} 个 / 全部 trusted = {all_trusted}")
        print("事件样本（前 8 条）：")
        for e in log2[:8]:
            print(f"   {e['t']:<13} trusted={str(e['trusted']):<5} {e['extra']}")

        # ---------- 测试 3：insertText 对照 ----------
        hr("测试 3（对照）：Input.insertText 一次性插入")
        cdp.ev("document.getElementById('ta').focus()")
        cdp.ev("document.getElementById('ta').innerHTML=''")
        cdp.ev("window.__clear()")
        t0 = time.time()
        cdp.send("Input.insertText", {"text": TEXT})
        dt = time.time() - t0
        time.sleep(0.4)
        val3 = cdp.ev("window.__val()")
        log3 = cdp.ev("window.__log()")
        print(f"实际结果：{val3!r}  匹配：{val3 == TEXT}")
        print(f"耗时：{dt:.2f}s")
        print(f"事件：{[e['t'] for e in log3]}  全部 trusted = {all(e['trusted'] for e in log3)}")

        cdp.close()
    finally:
        proc.terminate()
        time.sleep(1)
        try:
            proc.kill()
        except Exception:
            pass
        print("\n[browser closed]")


if __name__ == "__main__":
    main()
