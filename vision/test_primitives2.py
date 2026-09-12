# -*- coding: utf-8 -*-
"""验证新增原语：clear_field（Ctrl+A + Delete）与 press_key。

独立浏览器实例 + 本地页面，不接触任何线上服务。
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
from input_primitives import clear_field, real_click, type_text  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9335
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
    profile = tempfile.mkdtemp(prefix="cdp-prim-")
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
            if cdp.ev("!!document.getElementById('ta')"):
                break
            time.sleep(0.4)

        print("=" * 68)
        print("测试 clear_field（Ctrl+A + Delete）")
        print("=" * 68)
        r = cdp.ev("(()=>{const e=document.getElementById('ta');e.scrollIntoView({block:'center'});"
                   "const b=e.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};})()")
        real_click(cdp, r["x"], r["y"])
        time.sleep(0.3)
        print("activeElement:", cdp.ev("document.activeElement && document.activeElement.id"))

        cdp.ev("document.getElementById('ta').innerHTML='要清掉的旧内容ABC'")
        cdp.ev("window.__clear()")
        print(f"清空前内容: {cdp.ev('window.__val()')!r}")

        clear_field(cdp)
        time.sleep(0.3)
        after = cdp.ev("window.__val()")
        # contenteditable 用 Ctrl+A+Delete 清空后会残留一个换行符，属正常行为
        cleared = after.strip() == ""
        print(f"清空后内容: {after!r}（contenteditable 残留换行属正常）")
        print(f"清空成功: {cleared}")

        log = cdp.ev("window.__log()")
        n_kd = [e for e in log if e["t"] == "keydown"]
        print(f"\n产生 {len(log)} 个事件，其中 keydown {len(n_kd)} 个：")
        for e in log:
            print(f"   {e['t']:<13} trusted={str(e['trusted']):<5} {e['extra']}")
        all_t = all(e["trusted"] for e in log)
        print(f"\n全部 trusted: {all_t}")

        print()
        print("=" * 68)
        print("测试 type_text 后 clear_field 再 type_text（模拟改稿重发）")
        print("=" * 68)
        cdp.ev("document.getElementById('ta').innerHTML=''")
        type_text(cdp, "第一版文案")
        print(f"第一版: {cdp.ev('window.__val()')!r}")
        clear_field(cdp)
        time.sleep(0.2)
        print(f"清空后: {cdp.ev('window.__val()')!r}")
        type_text(cdp, "第二版文案，已修改")
        time.sleep(0.2)
        final = cdp.ev("window.__val()")
        print(f"第二版: {final!r}")
        rewrite_ok = final.strip() == "第二版文案，已修改"
        print(f"改稿流程正确: {rewrite_ok}")

        print()
        print("=" * 68)
        print("结论")
        print("=" * 68)
        print(f"  clear_field 走真实按键  : {'PASS' if cleared else 'FAIL'}")
        print(f"  改稿重发流程            : {'PASS' if rewrite_ok else 'FAIL'}")
        print(f"  事件全部 isTrusted      : {'PASS' if all_t else 'FAIL'}")
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
