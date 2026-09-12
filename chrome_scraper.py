# -*- coding: utf-8 -*-
"""系统 Chrome + CDP 通用抓取器（可渲染 JS）。

用途：抓取需要 JS 渲染的招聘站点（IAB 会崩主进程，故走系统 Chrome）。

用法：
  python chrome_scraper.py --probe <url>        探测页面结构
  python chrome_scraper.py --eval <url> <js>    在页面上执行 JS
"""
import argparse
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
PORT = 9444
PROFILE = os.path.join(tempfile.gettempdir(), "cdp-scraper-profile")


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.ids = itertools.count(1)

    def send(self, method, params=None, timeout=60):
        i = next(self.ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        self.ws.settimeout(timeout)
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == i:
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error']}")
                return r.get("result", {})

    def ev(self, expr, await_promise=False, timeout=60):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True,
            "awaitPromise": await_promise}, timeout=timeout)
        if r.get("exceptionDetails"):
            return None
        return r.get("result", {}).get("value")

    def goto(self, url, wait=4.0):
        self.send("Page.navigate", {"url": url})
        time.sleep(wait)
        for _ in range(20):
            st = self.ev("document.readyState")
            if st == "complete":
                break
            time.sleep(0.6)
        return self.ev("location.href")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def launch_chrome():
    """启动独立 Chrome 实例（隔离 profile，不影响用户日常 Chrome）。"""
    args = [CHROME, f"--remote-debugging-port={PORT}",
            f"--user-data-dir={PROFILE}", "--remote-allow-origins=*",
            "--no-first-run", "--no-default-browser-check", "--disable-fre",
            "--window-size=1400,1000", "about:blank"]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                for t in json.load(r):
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        return proc, t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Chrome 未就绪")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", help="探测页面结构")
    ap.add_argument("--eval", nargs=2, metavar=("URL", "JS"), help="执行 JS")
    ap.add_argument("--text", help="抓取页面纯文本")
    ap.add_argument("--keep", action="store_true", help="结束后不关 Chrome")
    args = ap.parse_args()

    proc, ws = launch_chrome()
    cdp = CDP(ws)
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    try:
        if args.probe:
            cdp.goto(args.probe, wait=5)
            print(f"URL: {cdp.ev('location.href')}")
            print(f"title: {cdp.ev('document.title')}")
            info = cdp.ev(r"""JSON.stringify({
              text: (document.body.innerText||'').slice(0,1500),
              iframes: [...document.querySelectorAll('iframe')].map(f=>f.src).slice(0,5),
              links: [...document.querySelectorAll('a')].map(a=>({t:(a.innerText||'').trim().slice(0,30), h:a.href}))
                       .filter(x=>x.t && /招聘|职位|加入|job|career|社会/i.test(x.t)).slice(0,15)
            })""")
            d = json.loads(info or "{}")
            print(f"\n--- 正文前 1500 字 ---\n{d.get('text')}")
            print(f"\n--- iframe ---\n{d.get('iframes')}")
            print(f"\n--- 招聘相关链接 ---")
            for l in d.get("links") or []:
                print(f"   {l['t'][:30]:30s} -> {l['h'][:90]}")

        elif args.eval:
            url, js = args.eval
            cdp.goto(url, wait=5)
            print(f"URL: {cdp.ev('location.href')}")
            v = cdp.ev(js, await_promise=True)
            print(v)

        elif args.text:
            cdp.goto(args.text, wait=5)
            print(f"URL: {cdp.ev('location.href')}")
            print(cdp.ev("(document.body.innerText||'').slice(0,3000)"))
    finally:
        if not args.keep:
            cdp.close()
            proc.terminate()
            time.sleep(1)
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
