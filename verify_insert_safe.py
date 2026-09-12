# -*- coding: utf-8 -*-
"""验证 insert_text 写多行正文不会触发发送（只写入+清空，绝不点发送）。

这是 2026-09-11 误发事故的核心验证：
  - 旧方案逐字符派发 Enter -> 边输入边发送（一条文案变 8 条）
  - 新方案 Input.insertText -> 不产生按键事件，换行安全

安全检查：脚本结束时强制清空输入框，且全程不调用任何发送操作。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from input_primitives import clear_field, insert_text, real_click  # noqa: E402
from send_paced import RelayCDP, build_message  # noqa: E402

READ = r"""
(() => {
  const el = document.getElementById('chat-input');
  const t = el ? (el.innerText || '') : null;
  return JSON.stringify({
    len: t === null ? -1 : t.length,
    text: t,
    conv: (document.querySelector('.chat-conversation') || {}).innerText || null,
    // 输入框下方是否出现"送达"标记（说明发出去了）
    hasSentMark: (document.body.innerText || '').indexOf('送达') >= 0,
    url: location.href
  });
})()
"""


def st(cdp):
    raw = cdp.val(READ)
    return json.loads(raw) if raw else {}


def main():
    cdp = RelayCDP()

    d = st(cdp)
    print("=" * 70)
    print("写前状态")
    print("=" * 70)
    print(f"  会话: {d.get('conv')}")
    print(f"  输入框长度: {d.get('len')}")
    if d.get("len"):
        print("  ⚠️ 输入框非空，先清空")
        r = cdp.val("(()=>{const e=document.getElementById('chat-input');"
                    "if(!e)return null;const b=e.getBoundingClientRect();"
                    "return JSON.stringify({x:b.x+b.width/2,y:b.y+b.height/2});})()")
        if r:
            xy = json.loads(r)
            real_click(cdp, xy["x"], xy["y"])
            time.sleep(0.3)
            clear_field(cdp)
            time.sleep(0.4)
            print(f"  清空后长度: {st(cdp).get('len')}")

    # 构造一条含多段换行的真实文案
    msg = build_message("AI智能体专家-技术", "需要RAG检索和知识库经验，接受出差")
    print(f"\n待写入文案: {len(msg)} 字，含 {msg.count(chr(10))} 个换行")
    print("--- 内容预览（前 5 行）---")
    for line in msg.split("\n")[:5]:
        print(f"    {line[:70]}")

    # 定位输入框
    r = cdp.val("(()=>{const e=document.getElementById('chat-input');if(!e)return null;"
                "const b=e.getBoundingClientRect();"
                "return JSON.stringify({x:b.x+b.width/2,y:b.y+b.height/2});})()")
    if not r:
        print("❌ 未找到输入框")
        return
    xy = json.loads(r)
    real_click(cdp, xy["x"], xy["y"])
    time.sleep(0.4)
    print(f"\n已聚焦: {cdp.val('document.activeElement && document.activeElement.id')}")

    # 核心验证：insert_text 写入含换行的长文本
    print("\n" + "=" * 70)
    print("写入测试（insert_text，含多段换行）")
    print("=" * 70)
    t0 = time.time()
    insert_text(cdp, msg)
    dt = time.time() - t0
    time.sleep(0.8)
    d2 = st(cdp)
    got = d2.get("len") or 0
    print(f"  耗时: {dt:.2f}s")
    print(f"  期望长度: {len(msg)}")
    print(f"  实际长度: {got}")
    print(f"  长度一致: {got == len(msg)}")
    print(f"  内容一致: {d2.get('text') == msg}")

    # 关键：确认没有触发发送
    print(f"\n  会话头部（未变说明没切走）: {d2.get('conv')}")
    print(f"  页面含「送达」标记: {d2.get('hasSentMark')}（仅表示历史消息里有，不代表本次发出）")

    # 再验证：换行是否保留在输入框内
    n_lines = (d2.get("text") or "").count("\n")
    print(f"  输入框内换行数: {n_lines} / 文案换行数: {msg.count(chr(10))}")

    # 强制清空，绝不留内容
    print("\n" + "=" * 70)
    print("强制清空输入框")
    print("=" * 70)
    clear_field(cdp)
    time.sleep(0.5)
    d3 = st(cdp)
    print(f"  清空后长度: {d3.get('len')} -> {repr((d3.get('text') or '')[:40])}")

    print("\n" + "=" * 70)
    ok = (got == len(msg)) and d2.get("text") == msg and (d3.get("len") or 0) <= 1
    print(f"结论：insert_text 写入多行安全 = {'PASS' if ok else 'FAIL'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
