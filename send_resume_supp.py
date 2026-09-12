# -*- coding: utf-8 -*-
"""给缺简历链接的老会话补发简历网页。"""
import json, urllib.request, time

SESSION = "cb-tab-3"
MSG = "补充一下我的个人简历网页，复制到浏览器可以打开：\nhttps://example.com/resume/"

def cmd(method, params=None, timeout=60):
    body=json.dumps({"method":method,"params":params or {},"sessionId":SESSION}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, t=60):
    r=cmd("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=t)
    i=r.get("result",{})
    if i.get("exceptionDetails"): return None
    return i.get("result",{}).get("value")

JS_FIND = """(async function(){
  var scroller = document.querySelector('.user-list-content');
  if (!scroller) return 'NO_SCROLLER';
  var brand = %s;
  var step = Math.max(150, scroller.clientHeight - 80);
  for (var pos = 0; pos <= scroller.scrollHeight + step; pos += step) {
    scroller.scrollTop = pos;
    await new Promise(function(r){setTimeout(r,250);});
    var items = document.querySelectorAll('.friend-content-warp');
    for (var i = 0; i < items.length; i++) {
      if ((items[i].innerText||'').indexOf(brand) >= 0) {
        (items[i].querySelector('.friend-content')||items[i].firstElementChild||items[i]).click();
        return 'clicked';
      }
    }
  }
  return 'not_found';
})()"""

JS_STATE = """JSON.stringify((function(){
  var cv = document.querySelector('.chat-conversation');
  var el = document.getElementById('chat-input');
  var b = [].slice.call(document.querySelectorAll('div,button')).filter(function(x){return /^\s*\u53d1\u9001\s*$/.test(x.innerText||'');})[0];
  return { conv: cv ? cv.innerText.split(String.fromCharCode(10)).filter(Boolean).slice(0,4).join(' / ') : null,
           len: el ? (el.innerText||'').length : -1, btn: b ? b.className : null };
})())"""

targets = ['共达地', '箴理科技', '北京天润融通', '杭州雾楼台', '云智创心', '南通五棵葱文化传媒']
out = []
for brand in targets:
    r = val(JS_FIND % json.dumps(brand, ensure_ascii=False), t=90)
    if r != 'clicked':
        print(f"FAIL {brand} | {r}", flush=True); out.append({'brand':brand,'ok':False,'note':r}); continue
    # 等面板就绪
    ok=False
    for _ in range(12):
        time.sleep(1.0)
        st = json.loads(val(JS_STATE) or '{}')
        if brand in (st.get('conv') or ''): ok=True; break
    if not ok:
        print(f"FAIL {brand} | panel_not_ready", flush=True); out.append({'brand':brand,'ok':False,'note':'panel_not_ready'}); continue
    # 写入
    wrote=False
    for _ in range(8):
        val("(function(){var el=document.getElementById('chat-input');if(!el)return 0;el.focus();el.innerHTML='';return 1;})()")
        time.sleep(0.4)
        cmd("Input.insertText", {"text": MSG})
        time.sleep(1.0)
        st = json.loads(val(JS_STATE) or '{}')
        if (st.get('len') or 0) >= 20 and 'disabled' not in str(st.get('btn')): wrote=True; break
        time.sleep(1.0)
    if not wrote:
        print(f"FAIL {brand} | write_failed", flush=True); out.append({'brand':brand,'ok':False,'note':'write_failed'}); continue
    val("(function(){var b=[].slice.call(document.querySelectorAll('div,button')).filter(function(x){return /^\s*\u53d1\u9001\s*$/.test(x.innerText||'');})[0];b.click();return 1;})()")
    time.sleep(3)
    st = json.loads(val(JS_STATE) or '{}')
    ok2 = (st.get('len') or 0) == 0
    print(f"{'OK ' if ok2 else 'FAIL'} {brand} | 补发简历链接", flush=True)
    out.append({'brand':brand,'ok':ok2,'note':'sent' if ok2 else 'not_cleared'})
    time.sleep(6)
json.dump(out, open('resume_supp_results.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("成功:", sum(1 for x in out if x['ok']), "/", len(out))
