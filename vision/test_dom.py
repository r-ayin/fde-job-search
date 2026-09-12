# -*- coding: utf-8 -*-
"""验证 DOM 读数据方案的三个主张（全部本地，不联网）：

  1. 读 DOM 期间网络请求数 = 0（用 CDP Network 域实测，不靠推断）
  2. DOM 定位 + 真实坐标点击保留 isTrusted=True
  3. DOM 读到的字段与页面渲染内容一致
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
from dom_tools import find_by_text, read_job_cards  # noqa: E402
from input_primitives import real_click  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9336
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "file:///" + os.path.join(HERE, "mock_search.html").replace("\\", "/")


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.ids = itertools.count(1)
        self.network_events = []
        self.collect = False

    def send(self, method, params=None):
        i = next(self.ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("method", "").startswith("Network."):
                if self.collect:
                    self.network_events.append(resp)
                continue
            if resp.get("id") == i:
                if "error" in resp:
                    raise RuntimeError(f"{method}: {resp['error']}")
                return resp.get("result", {})

    def drain(self, seconds=1.0):
        """把待处理的 CDP 事件读出来（含 Network）。"""
        self.ws.settimeout(seconds)
        try:
            while True:
                resp = json.loads(self.ws.recv())
                if resp.get("method", "").startswith("Network."):
                    self.network_events.append(resp)
        except Exception:
            pass
        finally:
            self.ws.settimeout(30)

    def ev(self, expr):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")


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


def main():
    trusted = False
    nok = salary_ok = zero_network = False
    profile = tempfile.mkdtemp(prefix="cdp-dom-")
    proc = subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
         "--disable-fre", "--window-size=1100,900", PAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        cdp = CDP(wait_devtools())
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        time.sleep(1.5)
        for _ in range(20):
            if cdp.ev("!!document.querySelector('li.job-card-box')"):
                break
            time.sleep(0.4)

        # ---------- 测试 1：读 DOM 期间的网络请求数 ----------
        print("=" * 70)
        print("测试 1：DOM 读数据期间产生多少网络请求（CDP Network 域实测）")
        print("=" * 70)
        cdp.send("Network.enable")
        cdp.collect = True
        time.sleep(0.4)
        cdp.drain(0.8)
        print(f"基线已收网络事件: {len(cdp.network_events)}（页面加载本身产生的）")

        cdp.network_events.clear()
        t0 = time.time()
        data = read_job_cards(cdp)
        dt = time.time() - t0
        cdp.drain(1.2)
        reqs = [e for e in cdp.network_events if e.get("method") == "Network.requestWillBeSent"]
        print(f"读卡片耗时 {dt * 1000:.0f}ms，期间网络请求数 = {len(reqs)}")
        for r in reqs[:5]:
            print("   ->", r["params"]["request"]["url"][:80])
        zero_network = len(reqs) == 0
        print(f">>> 读 DOM 零网络请求: {'PASS' if zero_network else 'FAIL'}")

        cdp.network_events.clear()
        cdp.send("Page.captureScreenshot", {"format": "png"})
        cdp.drain(0.8)
        shot_reqs = [e for e in cdp.network_events if e.get("method") == "Network.requestWillBeSent"]
        print(f"\n对比：截图操作产生网络请求 = {len(shot_reqs)}")
        print("（截图本身也不发请求，但 OCR 前提是页面已加载——那次加载才是可见的代价）")

        # ---------- 测试 2：DOM 读到的数据 ----------
        print()
        print("=" * 70)
        print("测试 2：DOM 读到的岗位卡数据（零请求）")
        print("=" * 70)
        print(f"URL: {data.get('url')}")
        print(f"卡片数: {data.get('n')}  hasNoMore={data.get('hasNoMore')}")
        for c in data.get("cards", []):
            print(f"\n  eid      = {c['eid']}")
            print(f"  岗位     = {c['jobName']}")
            print(f"  薪资     = {c['salary']}")
            print(f"  公司     = {c['company']}")
            print(f"  标签     = {c['tags']}")
            print(f"  城市     = {c['location']}")
            print(f"  点击坐标 = ({c['x']:.0f}, {c['y']:.0f})")
        nok = data.get("n") == 3
        salary_ok = all(c["salary"] for c in data.get("cards", []))
        print(f"\n>>> 卡片数正确(3): {'PASS' if nok else 'FAIL'}")
        print(f">>> 薪资均为明文: {'PASS' if salary_ok else 'FAIL'}")

        # ---------- 测试 3：DOM 定位 + 真实点击 ----------
        print()
        print("=" * 70)
        print("测试 3：DOM 定位元素 -> 真实坐标点击（保 isTrusted）")
        print("=" * 70)
        cdp.ev("window.__clear()")
        loc = find_by_text(cdp, "继续沟通")
        print(f"DOM 定位到: {loc}")
        if loc:
            real_click(cdp, loc["x"], loc["y"])
            time.sleep(0.4)
            log = cdp.ev("window.__log()")
            print(f"\n捕获 {len(log)} 个事件：")
            for e in log:
                print(f"   {e['t']:<13} trusted={str(e['trusted']):<5} target={e['target']}")
            click_ev = [e for e in log if e["t"] == "click"]
            trusted = bool(click_ev) and click_ev[0]["trusted"]
            print(f"\n>>> DOM 定位 + 真实点击 isTrusted: {'PASS' if trusted else 'FAIL'}")

            cdp.ev("window.__clear()")
            cdp.ev("""(()=>{const b=[...document.querySelectorAll('button.btn-chat')]
                       .find(x=>x.innerText.trim()==='继续沟通'); b.click();})()""")
            time.sleep(0.3)
            log2 = cdp.ev("window.__log()")
            ce2 = [e for e in log2 if e["t"] == "click"]
            print(f"    对照 element.click() isTrusted = {ce2[0]['trusted'] if ce2 else 'N/A'}")

        print()
        print("=" * 70)
        print("总结")
        print("=" * 70)
        print(f"  读 DOM 零网络请求   : {'PASS' if zero_network else 'FAIL'}")
        print(f"  DOM 数据完整且明文  : {'PASS' if (nok and salary_ok) else 'FAIL'}")
        print(f"  DOM 定位 + 真实点击 : {'PASS' if trusted else 'FAIL'}")
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
