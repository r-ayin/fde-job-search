# -*- coding: utf-8 -*-
"""实时检查：加载消息页并读会话列表（1 次页面加载，不发消息）。

用于账号恢复后确认：
  1. 是否能正常进入消息页（不跳验证页）
  2. 会话列表能否读到
  3. 页面是否出现风控信号
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from dom_tools import _eval  # noqa: E402
from pacing import is_risk_signal  # noqa: E402
from send_paced import RelayCDP  # noqa: E402

CHAT_URL = "https://www.zhipin.com/web/geek/chat"

PROBE = r"""
(() => {
  const t = (document.body.innerText || '');
  const items = [...document.querySelectorAll('.friend-content-warp')];
  const convs = items.slice(0, 8).map(w => (w.innerText || '').replace(/\n+/g, ' / ').trim());
  return JSON.stringify({
    url: location.href,
    title: document.title,
    bodyHead: t.slice(0, 500),
    verifyEl: !!document.querySelector('.geetest_panel, .verify-wrap, [class*=geetest]'),
    convCount: items.length,
    convs: convs,
    hasInput: !!document.getElementById('chat-input'),
    hasSendBtn: [...document.querySelectorAll('div,button')].some(x => /^\s*发送\s*$/.test(x.innerText || '')),
    convHeader: (document.querySelector('.chat-conversation') || {}).innerText || null,
    positionPanel: (document.querySelector('.chat-position-content') || {}).innerText || null
  });
})()
"""


def main():
    cdp = RelayCDP()
    print("=" * 70)
    print("实时检查：消息页")
    print("=" * 70)
    print(f"导航到 {CHAT_URL} ...")
    cdp.send("Page.navigate", {"url": CHAT_URL})

    d = None
    for i in range(16):
        time.sleep(1.2)
        raw = _eval(cdp, PROBE)
        if not raw:
            continue
        d = json.loads(raw)
        # 等到列表出现，或检测到风控/验证
        if d.get("convCount") or d.get("verifyEl") or is_risk_signal(d.get("url"), d.get("bodyHead")):
            break
    if not d:
        print("❌ 读取失败")
        return

    print(f"\nURL      : {d.get('url')}")
    print(f"标题     : {d.get('title')}")
    print(f"验证元素 : {d.get('verifyEl')}")
    print(f"会话数   : {d.get('convCount')}")
    print(f"输入框   : {d.get('hasInput')}")
    print(f"发送按钮 : {d.get('hasSendBtn')}")
    print(f"会话头部 : {d.get('convHeader')}")
    print(f"岗位面板 : {d.get('positionPanel')}")

    if d.get("convs"):
        print("\n--- 会话列表前 8 条 ---")
        for i, c in enumerate(d["convs"], 1):
            print(f"  {i}. {c}")

    risk = is_risk_signal(d.get("url"), d.get("bodyHead"))
    print("\n" + "=" * 70)
    if risk:
        print(f"⛔ 风控信号：{risk}")
        print("   账号仍受限，停止一切写操作。")
    elif d.get("verifyEl"):
        print("⛔ 页面出现验证元素，账号仍在校验中")
    elif not d.get("convCount"):
        print("⚠️  未读到会话列表（可能页面结构变化或加载慢），无风控信号")
    else:
        print(f"✅ 消息页正常，读到 {d['convCount']} 个会话，无风控信号")
        print("   账号可正常访问数据。下一步可跑 --dry-run 验证写路径。")
    print("=" * 70)


if __name__ == "__main__":
    main()
