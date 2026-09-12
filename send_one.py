# -*- coding: utf-8 -*-
"""向单个岗位发送沟通消息：详情页点立即沟通 → 聊天页写入 → 发送。"""
import json, urllib.request, time, sys

SESSION = "cb-tab-3"

def cmd(method, params=None, timeout=90):
    body=json.dumps({"method":method,"params":params or {},"sessionId":SESSION}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, timeout=90):
    r = cmd("Runtime.evaluate", {"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=timeout)
    inner = r.get("result",{})
    if inner.get("exceptionDetails"):
        return "EXC:" + str(inner.get("exceptionDetails"))[:200]
    return inner.get("result",{}).get("value")

def send(eid, message, dry=False):
    print(f"--- 岗位 {eid}", flush=True)
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    # 等详情页就绪
    for _ in range(15):
        time.sleep(1.2)
        if val("!!document.querySelector('.job-sec-text')") is True:
            break
    print("  详情页就绪:", val("document.title"), flush=True)

    # 点立即沟通
    r = val("""(()=>{
      const b=document.querySelector('a.btn-startchat') || [...document.querySelectorAll('a')].find(e=>/立即沟通|继续沟通/.test((e.innerText||'').trim()));
      if(!b) return 'NOT_FOUND';
      b.click(); return 'clicked:'+b.className;
    })()""")
    print("  点击沟通:", r, flush=True)
    time.sleep(5)

    # 等聊天页
    for _ in range(15):
        if '/web/geek/chat' in (val("location.href") or ''):
            break
        time.sleep(1.2)
    print("  当前页:", val("location.href"), flush=True)

    # 等输入框
    for _ in range(15):
        if val("!!document.getElementById('chat-input')") is True:
            break
        time.sleep(1.2)

    if dry:
        print("  [DRY RUN] 不发送", flush=True)
        return True

    # 清空 + 聚焦
    val("(()=>{const el=document.getElementById('chat-input');if(!el)return 'NO';el.focus();el.innerHTML='';return 'ok';})()")
    time.sleep(0.5)
    # CDP 原生输入
    cmd("Input.insertText", {"text": message})
    time.sleep(1)
    typed = val("document.getElementById('chat-input').innerText.length")
    print("  已写入字数:", typed, flush=True)
    btn = val("(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\s*发送\s*$/.test(x.innerText||''));return b?b.className:'none';})()")
    print("  发送按钮:", btn, flush=True)
    if 'disabled' in str(btn):
        print("  !! 按钮禁用，取消发送", flush=True)
        return False
    # 发送
    val("(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\s*发送\s*$/.test(x.innerText||''));if(!b)return 'NO';b.click();return 'sent';})()")
    time.sleep(4)
    left = val("document.getElementById('chat-input').innerText")
    print("  发送后输入框剩余:", repr(left), flush=True)
    conv = val("(document.querySelector('.chat-conversation')||{}).innerText")
    ok = message[:20] in (conv or '')
    print("  消息已在会话中:", ok, flush=True)
    return ok

if __name__ == '__main__':
    eid = sys.argv[1]
    msg = open(sys.argv[2], encoding='utf-8').read()
    dry = '--dry' in sys.argv
    send(eid, msg, dry=dry)
