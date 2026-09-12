# -*- coding: utf-8 -*-
"""端到端联调：截图 -> OCR 定位 -> 真实点击 -> 事件校验。

全程使用独立浏览器实例加载本地 selftest.html，不接触 BOSS、不经过 relay。
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from input_primitives import type_text  # noqa: E402
from vision import PageVision  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9334
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

    def ev(self, expr):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    def close(self):
        self.ws.close()


def wait_devtools(timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                for t in json.load(r):
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("devtools not ready")


def hr(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def main():
    profile = tempfile.mkdtemp(prefix="cdp-e2e-")
    proc = subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
         "--disable-fre", "--window-size=1000,900", PAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        cdp = CDP(wait_devtools())
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        time.sleep(1.5)
        for _ in range(20):
            if cdp.ev("!!document.getElementById('btn')"):
                break
            time.sleep(0.4)

        pv = PageVision(cdp)
        print("[info] devicePixelRatio =", pv.dpr())

        # ---------- 1. 视觉读取 ----------
        hr("1. 视觉读取：截图 + OCR 全页文本")
        shot = os.path.join(HERE, "e2e_shot.png")
        blocks, dpr, img = pv.scan(save=shot)
        print(f"截图 {img.size} (dpr={dpr})，识别到 {len(blocks)} 个文本块：")
        for b in blocks:
            print(f"   {b}")
        print("\n--- 拼回的阅读顺序文本 ---")
        print(pv.read_text())
        print(f"\n截图已保存: {shot}")

        # ---------- 2. OCR 定位按钮并真实点击 ----------
        hr("2. OCR 定位「立即沟通」-> 真实坐标点击")
        cdp.ev("window.__clear()")
        ok, note = pv.click_text("立即沟通")
        print(f"定位+点击结果: ok={ok} note={note}")
        time.sleep(0.4)
        log = cdp.ev("window.__log()")
        print(f"捕获 {len(log)} 个事件：")
        for e in log:
            print(f"   {e['t']:<13} trusted={str(e['trusted']):<5} target=#{e['target']}")
        click_ev = [e for e in log if e["t"] == "click"]
        good = bool(click_ev) and click_ev[0]["trusted"] and click_ev[0]["target"] == "btn"
        print(f"\n>>> 真实点击命中按钮且 trusted: {good}")

        # ---------- 3. 视觉定位输入框 + 逐字输入 ----------
        hr("3. 视觉定位输入区 -> 点击聚焦 -> 逐字输入中文")
        cdp.ev("document.getElementById('ta').scrollIntoView({block:'center'})")
        time.sleep(0.4)
        cdp.ev("window.__clear()")
        ok, note = pv.click_text("初始文本")
        print(f"定位输入区: ok={ok} note={note}")
        focused = cdp.ev("document.activeElement && document.activeElement.id")
        print(f"点击后 activeElement = {focused!r}")
        cdp.ev("document.getElementById('ta').innerHTML=''")
        cdp.ev("window.__clear()")
        TEXT = "您好，看了岗位描述，我的电商AI客服落地经验应该比较契合。"
        t0 = time.time()
        type_text(cdp, TEXT)
        dt = time.time() - t0
        time.sleep(0.3)
        val = cdp.ev("window.__val()")
        print(f"输入 {len(TEXT)} 字，耗时 {dt:.2f}s ({dt / len(TEXT) * 1000:.0f}ms/字)")
        print(f"结果匹配: {val == TEXT}")
        print(f"实际内容: {val!r}")
        log3 = cdp.ev("window.__log()")
        n_kd = len([e for e in log3 if e["t"] == "keydown"])
        n_in = len([e for e in log3 if e["t"] == "input"])
        print(f"keydown={n_kd} input={n_in} 全部trusted={all(e['trusted'] for e in log3)}")

        hr("汇总")
        print(f"  视觉读取        : {len(blocks)} 块识别成功")
        print(f"  真实坐标点击    : {'PASS' if good else 'FAIL'}")
        print(f"  逐字中文输入    : {'PASS' if val == TEXT else 'FAIL'}")
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
