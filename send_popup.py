# -*- coding: utf-8 -*-
"""在聊天弹窗中发送自定义消息。"""
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

def fill_and_send(message):
    # 聚焦 textarea
    r = val("(()=>{const t=document.querySelector('textarea.input-area');if(!t)return 'NO_TEXTAREA';t.focus();t.value='';return 'ok';})()")
    print("  focus:", r, flush=True)
    if r != 'ok': return False
    time.sleep(0.4)
    cmd("Input.insertText", {"text": message})
    time.sleep(1)
    got = val("(()=>{const t=document.querySelector('textarea.input-area');return t?t.value.length:0;})()")
    print("  写入字数:", got, flush=True)
    cls = val("(()=>{const b=document.querySelector('div.send-message');return b?b.className:'none';})()")
    print("  发送按钮:", cls, flush=True)
    if 'disable' in str(cls):
        print("  !! 按钮仍禁用", flush=True)
        return False
    r2 = val("(()=>{const b=document.querySelector('div.send-message');if(!b)return 'NO';b.click();return 'sent';})()")
    print("  点击发送:", r2, flush=True)
    time.sleep(4)
    left = val("(()=>{const t=document.querySelector('textarea.input-area');return t?t.value:'';})()")
    print("  发送后输入框:", repr(left)[:60], flush=True)
    return True

if __name__ == '__main__':
    msg = open(sys.argv[1], encoding='utf-8').read()
    ok = fill_and_send(msg)
    print("结果:", ok)
