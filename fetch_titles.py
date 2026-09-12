# -*- coding: utf-8 -*-
import json, urllib.request, time

def cmd(method, params=None, session="cb-tab-3", timeout=60):
    body=json.dumps({"method":method,"params":params or {},"sessionId":session}).encode()
    req=urllib.request.Request("http://127.0.0.1:18793/cmd",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def val(expr, t=60):
    r=cmd("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True}, timeout=t)
    i=r.get("result",{})
    if i.get("exceptionDetails"): return None
    return i.get("result",{}).get("value")

targets = [
    ('皆大欢喜','李乘风','5fe469858b4a501503d50tu1E1RR','FDE顾问（制造业方向）'),
    ('梓晨','凌**','31c3a1778a17f43a0nN72tW4FFJV','FDE（前沿部署工程师）'),
    ('数秦科技','黄**','55677630b617bd3c0nN62t69EFFR','AI智能应用（FDE）工程师-上市公司-包三餐'),
    ('缦德润','沈**','10820ce9042f02400nN709-9FldS','AI需求分析师（fde方向）外包岗位'),
    ('润和软件','江**','ba350f06c11a891a0nV43tm-GFFQ','AI需求分析师（fde方向）外包岗位'),
]
out=[]
for brand, hr, eid, quoted in targets:
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    title=None
    for _ in range(12):
        time.sleep(1.3)
        u = val("location.href") or ''
        if eid in u:
            t = val("(document.querySelector('.name h1')||document.querySelector('h1')||{}).innerText")
            if t:
                title = t.strip(); break
    out.append({'brand':brand,'hr':hr,'eid':eid,'realTitle':title,'quoted':quoted,
                'match': bool(title and title.strip()==quoted.strip().replace('&amp;','&').replace('&middot;','·'))})
    print(f"{brand:14s} | 真实={title} | 消息里={quoted} | {'✅' if out[-1]['match'] else '❌'}", flush=True)
json.dump(out, open('title_check.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
