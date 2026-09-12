# -*- coding: utf-8 -*-
"""离线验证发送写路径：mock_chat.html 复刻 BOSS DOM 结构，跑通 Sender.send_one。

覆盖：
  1. 面板稳定性校验（mock 故意让 .chat-position-content 延迟 900ms 更新，
     复刻 BOSS 真实行为；验证不会读到上一个会话的岗位名）
  2. 完整写路径：DOM 定位输入框 -> 真实点击聚焦 -> clear_field -> 逐字输入
  3. 输入长度校验、发送按钮点击、发送后输入框清空
全程本地，不接触 BOSS。
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from input_primitives import real_click  # noqa: E402
import send_paced  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9338
PAGE = "file:///" + os.path.join(HERE, "mock_chat.html").replace("\\", "/")


class LocalCDP:
    """与 send_paced.RelayCDP 同约定：send() 返回已剥信封的结果。"""

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

    def val(self, expr, timeout=60):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        if r.get("exceptionDetails"):
            return None
        return r.get("result", {}).get("value")

    def ev(self, expr):
        return self.val(expr)


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
    profile = tempfile.mkdtemp(prefix="cdp-send-")
    proc = subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
         "--disable-fre", "--window-size=1200,900", PAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        cdp = LocalCDP(wait_devtools())
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        time.sleep(1.5)
        for _ in range(20):
            if cdp.ev("!!document.getElementById('chat-input')"):
                break
            time.sleep(0.4)

        sender = send_paced.Sender(cdp, dry_run=True, skip_open=True)

        # ---------- 测试 1：面板滞后时的稳定性校验 ----------
        hr("测试 1：面板更新滞后（900ms）时的稳定性校验")
        print("初始状态:", cdp.ev("JSON.stringify({conv:document.querySelector('.chat-conversation').innerText,"
                                 "pos:document.querySelector('.chat-position-content').innerText})"))
        cdp.ev("document.querySelectorAll('.friend-content-warp')[0].click()")
        immediate = cdp.ev("JSON.stringify({conv:document.querySelector('.chat-conversation').innerText,"
                           "pos:document.querySelector('.chat-position-content').innerText})")
        print("切换后立即读:", immediate)
        t0 = time.time()
        job, st = sender.await_panel("杭州雾楼台", need=3, timeout_s=14)
        dt = time.time() - t0
        print(f"await_panel 耗时 {dt:.1f}s -> 岗位={job!r}")
        print(f"会话头部={st.get('conv')!r}")
        panel_ok = job is not None and "FDE前向部署工程师" in job and "12-18K" not in job
        print(f">>> 拿到正确、稳定且已剥离薪资的岗位名: {'PASS' if panel_ok else 'FAIL'}")

        cdp.ev("document.querySelectorAll('.friend-content-warp')[1].click()")
        time.sleep(1.6)
        print("\n切回:", cdp.ev("document.querySelector('.chat-conversation').innerText"))

        # ---------- 测试 2：完整写路径（dry-run，不点发送）----------
        hr("测试 2：完整写路径 dry-run（定位输入框 -> 清空 -> 逐字输入）")
        cdp.ev("window.__clear()")
        target = {"eid": "eidTEST", "brand": "云智创心科技", "hr": "王**",
                  "jobName": "电商短视频行业 FDE 负责人", "desc": "需要RAG检索和知识库经验"}
        # 注意：dry-run 不写入聊天框（2026-09-11 误发事故后的硬门禁），
        # 所以这里改为验证"dry-run 未写入"这一行为本身。
        sender.dry_run = True
        cdp.ev("document.getElementById('chat-input').innerHTML=''")
        cdp.ev("window.__clear()")
        t0 = time.time()
        ok, note = sender.send_one(target)
        dt = time.time() - t0
        print(f"send_one(dry-run) -> ok={ok} note={note} 耗时 {dt:.1f}s")
        val = cdp.ev("window.__val()")
        print(f"dry-run 后输入框内容长度: {len(val)} 字（应为 0）")
        # contenteditable 清空后可能残留 1 个换行，允许长度 <=1
        write_ok = ok and len(val.strip()) == 0 and "未写入" in note
        print(f">>> dry-run 不写入聊天框: {'PASS' if write_ok else 'FAIL'}")

        # 再单独验证真实写入路径（不点发送）
        cdp.ev("window.__clear()")
        sender.dry_run = False
        st_now = sender.read_state()
        ir = st_now.get("inputRect")
        from input_primitives import clear_field, insert_text, real_click
        from send_paced import build_message, clean_job
        real_click(cdp, ir["x"], ir["y"])
        time.sleep(0.3)
        clear_field(cdp)
        msg = build_message(clean_job("电商短视频行业 FDE 负责人 18-30K"), target["desc"])
        insert_text(cdp, msg)
        time.sleep(0.6)
        val2 = cdp.ev("window.__val()")
        print(f"真实写入长度: {len(val2)} 期望: {len(msg)}")
        write_ok2 = val2 == msg
        print(f">>> 写入完整文案: {'PASS' if write_ok2 else 'FAIL'}")
        print(f">>> 文案未混入薪资: {'PASS' if '18-30K」这个岗位' not in val2 else 'FAIL'}")
        # 写完清空，避免残留
        clear_field(cdp)

        log = cdp.ev("window.__log()")
        n_keydown = len([e for e in log if e["t"] == "keydown"])
        n_input = len([e for e in log if e["t"] == "input"])
        all_trusted = all(e["trusted"] for e in log)
        print(f"事件: keydown={n_keydown} input={n_input} 全部trusted={all_trusted}")
        print(f">>> 写入走真实事件: {'PASS' if all_trusted else 'FAIL'}")

        # ---------- 测试 3：真实点击发送 ----------
        hr("测试 3：真实点击发送（dry_run=False）")
        sender.dry_run = False
        cdp.ev("window.__clear()")
        st_now = sender.read_state()
        print(f"发送前按钮状态: btnDisabled={st_now.get('btnDisabled')} "
              f"inputLen={st_now.get('inputLen')}")
        ok_s, note_s = sender.click_button("发送")
        print(f"点击发送: ok={ok_s} {note_s}")
        time.sleep(1.2)
        sent = cdp.ev("window.__sent()")
        left = cdp.ev("window.__val()")
        print(f"发送后输入框剩余: {len(left)} 字")
        print(f"页面记录的已发送内容前 60 字:\n  {sent[:60]!r}")
        send_ok = ("已发送" in (sent or "")) and len(left.strip()) == 0
        print(f">>> 发送成功且输入框清空: {'PASS' if send_ok else 'FAIL'}")

        log3 = cdp.ev("window.__log()")
        ce = [e for e in log3 if e["t"] == "click"]
        click_trusted = bool(ce) and all(e["trusted"] for e in ce)
        print(f">>> 发送按钮点击 isTrusted: {'PASS' if click_trusted else 'FAIL'}")

        hr("总结")
        print(f"  面板滞后时拿到正确岗位名 : {'PASS' if panel_ok else 'FAIL'}")
        print(f"  dry-run 不写入聊天框     : {'PASS' if write_ok else 'FAIL'}")
        print(f"  写入完整文案             : {'PASS' if write_ok2 else 'FAIL'}")
        print(f"  写入走真实事件           : {'PASS' if all_trusted else 'FAIL'}")
        print(f"  全部事件 isTrusted       : {'PASS' if (all_trusted and click_trusted) else 'FAIL'}")
        print(f"  发送成功且输入框清空     : {'PASS' if send_ok else 'FAIL'}")
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
