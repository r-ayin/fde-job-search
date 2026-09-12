# -*- coding: utf-8 -*-
"""批量发送求职消息 v2 —— 会话驱动 + 身份校验。

安全设计：发送前必须校验当前激活会话与目标一致，避免发错人。
"""
import json, urllib.request, time, os, sys

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
    p4 = P4_RAG if any(k in desc for k in ['向量', 'RAG', '检索', '知识库', 'Embedding']) else P4
    body = (f"您好，看到「{job}」这个岗位，我的经历有几处和贵司需求比较契合，想和您具体聊聊：\n"
            f"{P1}\n{P2}\n{P3}\n{p4}\n")
    if any(k in desc for k in ['出差', '驻场', '客户现场', '现场实施']):
        body += "我接受出差和客户现场驻场交付。\n"
    body += "期待有机会和您进一步沟通。" + AI_TAIL
    return body + RESUME_BLOCK


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


JS_LIST = """
(() => [...document.querySelectorAll('.friend-content-warp')].map(w => {
  const li = w.closest('li');
  const lines = (w.innerText || '').split('\\n').filter(Boolean);
  return { idx: [...document.querySelectorAll('li')].indexOf(li), header: lines.slice(0, 3).join(' / ') };
}))()
"""

JS_CLICK_BY_BRAND = """
(() => {
  const brand = %s;
  const hr = %s;
  const items = [...document.querySelectorAll('.friend-content-warp')];
  let fallback = null;
  for (const w of items) {
    const t = w.innerText || '';
    if (t.indexOf(brand) < 0) continue;
    if (hr) {
      if (t.indexOf(hr) >= 0) {
        (w.querySelector('.friend-content') || w.firstElementChild || w).click();
        return 'clicked';
      }
      if (!fallback) fallback = w;
    } else {
      (w.querySelector('.friend-content') || w.firstElementChild || w).click();
      return 'clicked';
    }
  }
  if (fallback) {
    (fallback.querySelector('.friend-content') || fallback.firstElementChild || fallback).click();
    return 'clicked_fallback';
  }
  return 'not_in_list';
})()
"""

JS_ACTIVE = """
(() => {
  const cv = document.querySelector('.chat-conversation');
  const pc = document.querySelector('.chat-position-content');
  const input = document.getElementById('chat-input');
  return JSON.stringify({
    conv: cv ? cv.innerText.split('\\n').filter(Boolean).slice(0, 6).join(' / ') : null,
    pos: pc ? pc.innerText.split('\\n').filter(Boolean).join(' / ') : null,
    hasInput: !!input
  });
})()
"""

JS_INPUT_STATE = """
(() => {
  const el = document.getElementById('chat-input');
  const b = [...document.querySelectorAll('div,button')].find(x => /^\\s*发送\\s*$/.test(x.innerText || ''));
  return JSON.stringify({
    len: el ? (el.innerText || '').length : -1,
    btn: b ? b.className : null
  });
})()
"""


def goto_chat():
    cmd("Page.navigate", {"url": "https://www.zhipin.com/web/geek/chat/"})
    for _ in range(20):
        time.sleep(1.2)
        u = val("location.href") or ''
        if '/web/geek/chat' in u and (val("document.querySelectorAll('.friend-content-warp').length") or 0) > 5:
            return True
    return False


def send_via_chat(brand, hr, msg, job_name, jd_desc=''):
    """会话驱动发送：定位会话 → 点击 → 校验 → 发送。"""
    if not goto_chat():
        return False, 'chat_load_failed'

    # 按 品牌+HR 定位（品牌可能重名）
    r = val(JS_CLICK_BY_BRAND % (json.dumps(brand, ensure_ascii=False), json.dumps(hr or '', ensure_ascii=False)))
    if r not in ('clicked', 'clicked_fallback'):
        return False, f'conv_not_found:{r}'

    # 等待会话真正打开（会话区出现品牌名）
    st = {}
    for _ in range(14):
        time.sleep(1.0)
        raw = val(JS_ACTIVE)
        if not raw:
            continue
        st = json.loads(raw)
        conv = st.get('conv') or ''
        if conv and brand and brand in conv and st.get('hasInput'):
            break
    conv = st.get('conv') or ''
    if brand and brand not in conv:
        return False, f'verify_brand_fail:{conv[:40]}'
    pos = st.get('pos') or ''
    # 以会话面板显示的真实岗位名为准（避免 JD 库与线上不一致）
    actual_job = pos.split(' / ')[0].strip() if pos else ''
    if actual_job:
        msg = build_message(actual_job, (jd_desc or ''))
    if not st.get('hasInput'):
        return False, 'no_input_box'

    # 写入（失败重试 3 次）
    ist = {}
    for attempt in range(10):
        r = val("(()=>{const el=document.getElementById('chat-input');if(!el)return 0;el.focus();el.innerHTML='';return 1;})()")
        if r != 1:
            time.sleep(1.0)
            continue
        time.sleep(0.4)
        cmd("Input.insertText", {"text": msg})
        time.sleep(1.2)
        ist = json.loads(val(JS_INPUT_STATE) or '{}')
        if (ist.get('len') or 0) >= 50 and 'disabled' not in str(ist.get('btn')):
            break
        time.sleep(1.0)
    if (ist.get('len') or 0) < 50:
        return False, f'write_failed:{ist.get("len")}'
    if 'disabled' in str(ist.get('btn')):
        return False, 'btn_disabled'

    val("""(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\\s*发送\\s*$/.test(x.innerText||''));b.click();return 1;})()""")
    time.sleep(3)
    left = val("(()=>{const el=document.getElementById('chat-input');return el?el.innerText:'';})()")
    return (left == ''), ('sent' if left == '' else f'not_cleared:{len(left or "")}')


if __name__ == '__main__':
    targets = json.load(open('send_targets.json', encoding='utf-8'))
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else len(targets)
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0

    outfile = 'send_results.json'
    results = json.load(open(outfile, encoding='utf-8')) if os.path.exists(outfile) else []
    done = {r['eid'] for r in results if r.get('ok')}

    print(f"目标 {len(targets)}，已完成 {len(done)}，本次 [{start}:{end}]", flush=True)
    fails = 0
    for i, t in enumerate(targets[start:end], start):
        if t['eid'] in done:
            continue
        try:
            ok, note = send_via_chat(t.get('brand'), t.get('hr'), build_message(t.get('jobName'), t.get('desc')), t.get('jobName'), t.get('desc'))
        except Exception as e:
            ok, note = False, f'error:{str(e)[:70]}'
        results.append({'eid': t['eid'], 'brand': t.get('brand'), 'hr': t.get('hr'),
                        'job': t.get('jobName'), 'source': t.get('source'), 'ok': ok,
                        'note': note, 'ts': int(time.time())})
        print(f"[{i+1}/{len(targets)}] {'OK ' if ok else 'FAIL'} {t.get('brand')} | {(t.get('jobName') or '')[:24]} | {note}", flush=True)
        json.dump(results, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        fails = 0 if ok else fails + 1
        if fails >= 6:
            print("!! 连续 6 次失败，中止", flush=True)
            break
        time.sleep(delay)
    okn = sum(1 for r in results if r.get('ok'))
    print(f"结束：成功 {okn} / {len(results)}", flush=True)
