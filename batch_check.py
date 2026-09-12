# -*- coding: utf-8 -*-
import json, urllib.request, sys, time

def cmd(method, params=None, session="cb-tab-3", timeout=60):
    body=json.dumps({"method":method,"params":params or {},"sessionId":session}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

TEMPLATE = """(async () => {
  var scroller = document.querySelector('.user-list-content');
  var step = Math.max(150, scroller.clientHeight - 80);
  var brands = %s;
  var out = [];
  for (var b = 0; b < brands.length; b++) {
    var brand = brands[b];
    var clicked = false;
    for (var pos = 0; pos <= scroller.scrollHeight + step; pos += step) {
      scroller.scrollTop = pos;
      await new Promise(function(r){setTimeout(r,250);});
      var items = document.querySelectorAll('.friend-content-warp');
      for (var i = 0; i < items.length; i++) {
        if ((items[i].innerText||'').indexOf(brand) >= 0) {
          (items[i].querySelector('.friend-content')||items[i].firstElementChild||items[i]).click();
          clicked = true; break;
        }
      }
      if (clicked) break;
    }
    if (!clicked) { out.push(brand + ' :: NOT_FOUND'); continue; }
    await new Promise(function(r){setTimeout(r,5000);});
    var pc = document.querySelector('.chat-position-content');
    var cv = document.querySelector('.chat-conversation');
    var t = cv ? cv.innerText : '';
    var i = t.indexOf(String.fromCharCode(12300)), j = t.indexOf(String.fromCharCode(12301));
    var pj = pc ? pc.innerText.split(String.fromCharCode(10))[0] : '?';
    var mj = (i>=0&&j>i) ? t.substring(i+1,j) : '?';
    out.push(brand + ' :: ' + (pj === mj ? 'MATCH' : 'DIFF') + ' :: panel=' + pj + ' :: msg=' + mj);
  }
  return out.join(String.fromCharCode(10));
})()"""

def check(brands):
    js = TEMPLATE % json.dumps(brands, ensure_ascii=False)
    r = cmd("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True}, timeout=80)
    i = r.get("result", {})
    if i.get("exceptionDetails"):
        return "EXC"
    return i.get("result", {}).get("value")

suspects = ['海天瑞声','皆大欢喜','一扇门科技有限公司','得力集团','浙江预策科技有限...','杭州铭予科技有限公司',
            '帆软软件','筑龙股份','浙江响农','数秦科技','鲸灵智能','杭州产链数字科技','横店资本','三花控股集团',
            '商米','博采网络','杭州孚德','越盈电子','动势科技','杭州扬杨得熠文化创意','捷科智诚','缦德润','润和软件']

results = []
B = 3
for k in range(0, len(suspects), B):
    chunk = suspects[k:k+B]
    v = check(chunk)
    print(f"--- 批次 {k//B+1} ---", flush=True)
    print(v if v else "(空)", flush=True)
    if v and v != 'EXC':
        results.append(v)
    time.sleep(1)

open('suspect_check.txt','w',encoding='utf-8').write('\n'.join(results))
print()
print("已保存 suspect_check.txt")
