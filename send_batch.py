# -*- coding: utf-8 -*-
"""批量发送求职消息到 BOSS直聘。

流程：导航岗位详情页 → 点立即沟通/继续沟通 → 弹窗写入文案 → 发送
支持断点续传、风控检测、延迟控制。
"""
import json, urllib.request, time, os, sys, re

SESSION = "cb-tab-3"
RESUME_BLOCK = "\n个人简历网页，复制到浏览器可以打开：\nhttps://example.com/resume/"
AI_TAIL = "\n虽然本句话为ai发送，但关于本人的经验和工作经历都发自真心，希望给个了解的机会。"

P1 = "1）垂直行业AI落地：曾在电商行业有完整落地经验，主导过AI应用从开发到交付的完整流程，有toB交付经验，已完成多家客户的实际交付。"
P2 = "2）人效提升成果：<个人量化成果，已脱敏>"
P3 = "3）方案设计与客户对接：在大型互联网公司负责AI工程化建设期间，独立完成过从流程调研、方案设计、平台部署到功能迭代的完整闭环，搭建的培训平台覆盖数百人、整体运营效率显著提升；同时承担产品经理角色，负责推动项目落地、运营、报告撰写、效果评估及跨部门协作。"
P4 = "4）AI工程能力：熟悉本地/边缘部署、mcp开发、docker容器化部署，实操经验丰富，能够独立搭建复杂Agent系统；主导过知识系统0-1建设，设计企业知识库分层架构（原始层+检索层+业务层+经验沉淀层），落地RAG+FTS混合检索。"
P4_RAG = "4）检索与工程能力：搭建过RAG+FTS本地检索系统（Elasticsearch+BM25+BERT微调，做过准确率/召回率/F1评估）；熟悉本地/边缘部署、mcp开发、docker容器化部署，能够独立搭建复杂Agent系统，也做过提示词工程与企业知识库分层架构设计。"


def build_message(job_name, desc):
    desc = desc or ''
    job = (job_name or '该岗位').strip()
    # 若 JD 强调检索/向量，用 RAG 版第 4 点
    if any(k in desc for k in ['向量', 'RAG', '检索', '知识库', 'Embedding']):
        p4 = P4_RAG
    else:
        p4 = P4
    body = f"您好，看到「{job}」这个岗位，我的经历有几处和贵司需求比较契合，想和您具体聊聊：\n{P1}\n{P2}\n{P3}\n{p4}\n"
    # 出差/驻场意愿
    if any(k in desc for k in ['出差', '驻场', '客户现场', '现场实施']):
        body += "我接受出差和客户现场驻场交付。\n"
    body += "期待有机会和您进一步沟通。"
    return body + RESUME_BLOCK + AI_TAIL


def cmd(method, params=None, timeout=60):
    body = json.dumps({"method": method, "params": params or {}, "sessionId": SESSION}).encode()
    req = urllib.request.Request("http://127.0.0.1:18793/cmd", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def val(expr, timeout=60):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, timeout)
    i = r.get("result", {})
    if i.get("exceptionDetails"):
        return None
    return i.get("result", {}).get("value")


def fill_and_send(msg):
    """在弹窗或聊天页写入并发送。返回 (ok, note)"""
    # 弹窗流程
    if val("!!document.querySelector('textarea.input-area')") is True:
        val("(()=>{const t=document.querySelector('textarea.input-area');t.focus();t.value='';return 1;})()")
        time.sleep(0.3)
        cmd("Input.insertText", {"text": msg})
        time.sleep(0.8)
        n = val("(()=>{const t=document.querySelector('textarea.input-area');return t?t.value.length:0;})()")
        cls = val("(()=>{const b=document.querySelector('div.send-message');return b?b.className:'none';})()")
        if not n or n < 50:
            return False, f'popup_write_failed:{n}'
        if 'disable' in str(cls):
            return False, 'popup_btn_disabled'
        val("(()=>{const b=document.querySelector('div.send-message');b.click();return 1;})()")
        time.sleep(3)
        left = val("(()=>{const t=document.querySelector('textarea.input-area');return t?t.value:'';})()")
        return (left == ''), ('sent_popup' if left == '' else f'popup_not_cleared:{len(left)}')

    # 聊天页流程
    if val("!!document.getElementById('chat-input')") is True:
        val("(()=>{const el=document.getElementById('chat-input');el.focus();el.innerHTML='';return 1;})()")
        time.sleep(0.3)
        cmd("Input.insertText", {"text": msg})
        time.sleep(0.8)
        n = val("document.getElementById('chat-input').innerText.length")
        cls = val("""(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\\s*发送\\s*$/.test(x.innerText||''));return b?b.className:'none';})()""")
        if not n or n < 50:
            return False, f'chat_write_failed:{n}'
        if 'disabled' in str(cls):
            return False, 'chat_btn_disabled'
        val("""(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\\s*发送\\s*$/.test(x.innerText||''));b.click();return 1;})()""")
        time.sleep(3)
        left = val("document.getElementById('chat-input').innerText")
        return (left == ''), ('sent_chat' if left == '' else f'chat_not_cleared:{len(left)}')

    return False, 'no_input_found'


def send_one(t):
    eid, job = t['eid'], t.get('jobName') or ''
    msg = build_message(job, t.get('desc'))
    # 导航详情页
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    ready = False
    for _ in range(12):
        time.sleep(1.2)
        if val("!!document.querySelector('.job-sec-text')") is True:
            ready = True
            break
    if not ready:
        return False, 'detail_not_ready'

    # 点沟通
    r = val("""(()=>{
      const b=document.querySelector('a.btn-startchat') || [...document.querySelectorAll('a,div')].find(e=>/立即沟通|继续沟通/.test((e.innerText||'').trim()) && (e.innerText||'').trim().length<12);
      if(!b) return 'NOT_FOUND';
      b.click(); return 'clicked';
    })()""")
    if r != 'clicked':
        return False, f'no_button:{r}'
    time.sleep(5)

    # 等任一输入界面出现
    for _ in range(12):
        if val("!!document.querySelector('textarea.input-area') || !!document.getElementById('chat-input')") is True:
            break
        time.sleep(1.2)

    return fill_and_send(msg)


if __name__ == '__main__':
    targets = json.load(open('send_targets.json', encoding='utf-8'))
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else len(targets)
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0

    outfile = 'send_results.json'
    results = json.load(open(outfile, encoding='utf-8')) if os.path.exists(outfile) else []
    done = {r['eid'] for r in results if r.get('ok')}

    print(f"目标 {len(targets)} 个，已完成 {len(done)}，本次处理 [{start}:{end}]", flush=True)
    fails_in_row = 0
    for i, t in enumerate(targets[start:end], start):
        if t['eid'] in done:
            continue
        try:
            ok, note = send_one(t)
        except Exception as e:
            ok, note = False, f'error:{str(e)[:60]}'
        results.append({'eid': t['eid'], 'brand': t.get('brand'), 'hr': t.get('hr'),
                        'job': t.get('jobName'), 'source': t.get('source'),
                        'ok': ok, 'note': note, 'ts': int(time.time())})
        print(f"[{i+1}/{len(targets)}] {'OK ' if ok else 'FAIL'} {t.get('brand')} | {(t.get('jobName') or '')[:26]} | {note}", flush=True)
        json.dump(results, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if ok:
            fails_in_row = 0
        else:
            fails_in_row += 1
            if fails_in_row >= 5:
                print("!! 连续 5 次失败，疑似风控，中止", flush=True)
                break
        time.sleep(delay)
    okn = sum(1 for r in results if r.get('ok'))
    print(f"本次结束：累计成功 {okn} / {len(results)}", flush=True)
