# -*- coding: utf-8 -*-
"""完整发送流程：导航详情页 → 点立即沟通 → 弹窗写入 → 发送。"""
import json, urllib.request, time, sys

SESSION = "cb-tab-3"

def cmd(method, params=None, timeout=90):
    body=json.dumps({"method":method,"params":params or {},"sessionId":SESSION}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, timeout=90):
    r = cmd("Runtime.evaluate", {"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=timeout)
    inner = r.get("result",{})
    if inner.get("exceptionDetails"): return "EXC:"+str(inner.get("exceptionDetails"))[:200]
    return inner.get("result",{}).get("value")

def send(eid, message, label=""):
    print(f"=== {label} ({eid})", flush=True)
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    for _ in range(15):
        time.sleep(1.2)
        if val("!!document.querySelector('.job-sec-text')") is True: break
    print("  详情页:", (val("document.title") or '')[:60], flush=True)

    # 点立即沟通/继续沟通
    r = val("""(()=>{
      const b=document.querySelector('a.btn-startchat') || [...document.querySelectorAll('a,div')].find(e=>/立即沟通|继续沟通/.test((e.innerText||'').trim()) && (e.innerText||'').trim().length<12);
      if(!b) return 'NOT_FOUND';
      b.click(); return 'clicked';
    })()""")
    print("  点击沟通:", r, flush=True)
    time.sleep(5)

    # 等弹窗 textarea
    ok=False
    for _ in range(15):
        if val("!!document.querySelector('textarea.input-area')") is True:
            ok=True; break
        time.sleep(1.2)
    if not ok:
        print("  !! 未出现聊天弹窗", flush=True); return False

    # 写入
    val("(()=>{const t=document.querySelector('textarea.input-area');t.focus();t.value='';return 'ok';})()")
    time.sleep(0.4)
    cmd("Input.insertText", {"text": message})
    time.sleep(1)
    n = val("(()=>{const t=document.querySelector('textarea.input-area');return t?t.value.length:0;})()")
    cls = val("(()=>{const b=document.querySelector('div.send-message');return b?b.className:'none';})()")
    print(f"  写入 {n} 字 | 按钮: {cls}", flush=True)
    if 'disable' in str(cls):
        print("  !! 按钮禁用，跳过", flush=True); return False

    # 发送
    val("(()=>{const b=document.querySelector('div.send-message');b.click();return 'sent';})()")
    time.sleep(4)
    left = val("(()=>{const t=document.querySelector('textarea.input-area');return t?t.value:'';})()")
    print("  发送后输入框:", repr(left)[:40], flush=True)
    sent_ok = (left == '')
    print("  结果:", "✅ 已发送" if sent_ok else "❌ 未确认", flush=True)
    return sent_ok

if __name__ == '__main__':
    eid, msgfile, label = sys.argv[1], sys.argv[2], sys.argv[3]
    msg = open(msgfile, encoding='utf-8').read().strip()
    send(eid, msg, label)
