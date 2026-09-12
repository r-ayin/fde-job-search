# -*- coding: utf-8 -*-
"""批量发送求职消息 v3 —— 详情页驱动 + 发送前身份强校验。

安全保证：写入前必须确认当前会话与目标一致（品牌或岗位匹配），否则放弃。
"""
import json
import os
import sys
import time
import urllib.request

SESSION = "cb-tab-3"

RESUME_BLOCK = "\n个人简历网页，复制到浏览器可以打开：\nhttps://example.com/resume/"
AI_TAIL = "\n虽然本句话为ai发送，但关于本人的经验和工作经历都发自真心，希望给个了解的机会。"

P1 = ("1）垂直行业AI落地：曾在电商行业有完整落地经验，"
      "主导过AI应用从开发到交付的完整流程，有toB交付经验，"
      "已完成多家客户的实际交付。")
P2 = "2）人效提升成果：<个人量化成果，已脱敏>"
P3 = ("3）方案设计与客户对接：在大型互联网公司负责AI工程化建设期间，独立完成过从流程调研、方案设计、"
      "平台部署到功能迭代的完整闭环，搭建的培训平台覆盖数百人、整体运营效率显著提升；"
      "同时承担产品经理角色，负责推动项目落地、运营、报告撰写、效果评估及跨部门协作。")
P4 = ("4）AI工程能力：熟悉本地/边缘部署、mcp开发、docker容器化部署，实操经验丰富，"
      "能够独立搭建复杂Agent系统；主导过知识系统0-1建设，设计企业知识库分层架构"
      "（原始层+检索层+业务层+经验沉淀层），落地RAG+FTS混合检索。")
P4_RAG = ("4）检索与工程能力：搭建过RAG+FTS本地检索系统（Elasticsearch+BM25+BERT微调，"
          "做过准确率/召回率/F1评估）；熟悉本地/边缘部署、mcp开发、docker容器化部署，"
          "能够独立搭建复杂Agent系统，也做过提示词工程与企业知识库分层架构设计。")

RAG_HINTS = ['向量', 'RAG', '检索', '知识库', 'Embedding']
TRIP_HINTS = ['出差', '驻场', '客户现场', '现场实施']


def build_message(job_name, desc):
    desc = desc or ''
    job = (job_name or '该岗位').strip()
    p4 = P4_RAG if any(k in desc for k in RAG_HINTS) else P4
    body = (f"您好，看到「{job}」这个岗位，我的经历有几处和贵司需求比较契合，想和您具体聊聊：\n"
            f"{P1}\n{P2}\n{P3}\n{p4}\n")
    if any(k in desc for k in TRIP_HINTS):
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


JS_STATE = """
(() => {
  const cv = document.querySelector('.chat-conversation');
  const pc = document.querySelector('.chat-position-content');
  const el = document.getElementById('chat-input');
  const btn = [...document.querySelectorAll('div,button')].find(x => /^\\s*发送\\s*$/.test(x.innerText || ''));
  return JSON.stringify({
    conv: cv ? cv.innerText.split('\\n').filter(Boolean).slice(0, 8).join(' / ') : null,
    pos: pc ? pc.innerText.split('\\n').filter(Boolean).join(' / ') : null,
    hasInput: !!el,
    inputLen: el ? (el.innerText || '').length : -1,
    btn: btn ? btn.className : null
  });
})()
"""

JS_CLICK_CONV = """
(() => {
  const brand = %s;
  const hr = %s;
  const items = [...document.querySelectorAll('.friend-content-warp')];
  let fb = null;
  for (const w of items) {
    const t = w.innerText || '';
    if (t.indexOf(brand) < 0) continue;
    if (hr && t.indexOf(hr) >= 0) {
      (w.querySelector('.friend-content') || w.firstElementChild || w).click();
      return 'clicked';
    }
    if (!fb) fb = w;
  }
  if (fb) {
    (fb.querySelector('.friend-content') || fb.firstElementChild || fb).click();
    return 'clicked_fallback';
  }
  return 'not_in_list';
})()
"""



JS_SCROLL_FIND = """
(() => {
  const brand = %s;
  const hr = %s;
  const scroller = document.querySelector('.user-list-content');
  if (!scroller) return 'NO_SCROLLER';
  const total = scroller.scrollHeight;
  const step = Math.max(200, scroller.clientHeight - 60);
  // 从上到下逐屏查找
  for (let pos = 0; pos <= total; pos += step) {
    scroller.scrollTop = pos;
    const items = [...document.querySelectorAll('.friend-content-warp')];
    let fb = null;
    for (const w of items) {
      const t = w.innerText || '';
      if (t.indexOf(brand) < 0) continue;
      if (hr && t.indexOf(hr) >= 0) {
        (w.querySelector('.friend-content') || w.firstElementChild || w).click();
        return 'clicked_at_' + pos;
      }
      if (!fb) fb = w;
    }
    if (fb && pos >= total - step) {
      (fb.querySelector('.friend-content') || fb.firstElementChild || fb).click();
      return 'clicked_fallback';
    }
  }
  return 'not_found_after_scroll';
})()
"""


def scroll_and_click(brand, hr):
    """滚动会话列表查找目标并点击。"""
    raw = val(JS_SCROLL_FIND % (json.dumps(brand, ensure_ascii=False), json.dumps(hr or '', ensure_ascii=False)))
    if raw and str(raw).startswith('clicked'):
        time.sleep(2.5)
        return True, raw
    return False, raw

def read_state():
    raw = val(JS_STATE)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def send_current(msg, brand, hr, actual_job):
    """在已打开的会话中写入并发送。"""
    st = {}
    for _ in range(12):
        r = val("(()=>{const el=document.getElementById('chat-input');if(!el)return 0;el.focus();el.innerHTML='';return 1;})()")
        if r != 1:
            time.sleep(1.0)
            continue
        time.sleep(0.4)
        cmd("Input.insertText", {"text": msg})
        time.sleep(1.2)
        st = read_state()
        if (st.get('inputLen') or 0) >= 50 and 'disabled' not in str(st.get('btn')):
            break
        time.sleep(1.0)
    if (st.get('inputLen') or 0) < 50:
        return False, f'write_failed:{st.get("inputLen")}'
    if 'disabled' in str(st.get('btn')):
        return False, 'btn_disabled'
    # 二次校验：写入后会话没被换掉
    st2 = read_state()
    if brand and brand not in (st2.get('conv') or ''):
        return False, 'switch_after_write'
    val("""(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\\s*发送\\s*$/.test(x.innerText||''));b.click();return 1;})()""")
    time.sleep(3)
    st3 = read_state()
    if (st3.get('inputLen') or 0) == 0:
        return True, f'sent[{actual_job[:14]}]'
    return False, f'not_cleared:{st3.get("inputLen")}'


def send_one(t):
    eid = t['eid']
    brand = t.get('brand') or ''
    hr = t.get('hr') or ''
    desc = t.get('desc') or ''

    # 1) 打开岗位详情页
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    ok = False
    for _ in range(12):
        time.sleep(1.2)
        u = val("location.href") or ''
        if eid in u and val("!!document.querySelector('.job-sec-text')") is True:
            ok = True
            break
    if not ok:
        return False, 'detail_not_ready'

    # 2) 点沟通按钮
    r = val("""(()=>{
      const b=document.querySelector('a.btn-startchat') || [...document.querySelectorAll('a,div')].find(e=>/立即沟通|继续沟通/.test((e.innerText||'').trim()) && (e.innerText||'').trim().length<12);
      if(!b) return 'NOT_FOUND';
      b.click(); return 'clicked';
    })()""")
    if r != 'clicked':
        return False, f'no_button:{r}'

    # 3) 等进入聊天页
    for _ in range(16):
        time.sleep(1.2)
        u = val("location.href") or ''
        if '/web/geek/chat' in u:
            break

    # 4) 等会话渲染并校验身份；不匹配则尝试在列表中点击目标会话
    matched = False
    actual_job = ''
    st = {}
    for attempt in range(3):
        for _ in range(10):
            time.sleep(1.0)
            st = read_state()
            conv = st.get('conv') or ''
            pos = st.get('pos') or ''
            actual_job = pos.split(' / ')[0].strip() if pos else ''
            if st.get('hasInput') and conv:
                if brand and brand in conv:
                    matched = True
                    break
                if brand and t.get('jobName') and t['jobName'][:6] in (pos + conv):
                    matched = True
                    break
        if matched:
            break
        # 滚动查找目标会话
        okc, info = scroll_and_click(brand, hr)
        if not okc:
            last_scroll = info
        time.sleep(1.5)

    if not matched:
        conv = (st.get('conv') or '')[:40]
        return False, f'verify_fail:conv={conv}'

    return send_current(build_message(actual_job or t.get('jobName'), desc), brand, hr, actual_job or t.get('jobName') or '')


if __name__ == '__main__':
    targets = json.load(open('send_targets.json', encoding='utf-8'))
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else len(targets)
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0

    outfile = 'send_results_v4.json'
    results = json.load(open(outfile, encoding='utf-8')) if os.path.exists(outfile) else []
    done = {r['eid'] for r in results if r.get('ok')}

    print(f"目标 {len(targets)}，已完成 {len(done)}，本次 [{start}:{end}]", flush=True)
    fails = 0
    for i, t in enumerate(targets[start:end], start):
        if t['eid'] in done:
            continue
        try:
            ok, note = send_one(t)
        except Exception as e:
            ok, note = False, f'error:{str(e)[:70]}'
        results.append({'eid': t['eid'], 'brand': t.get('brand'), 'hr': t.get('hr'),
                        'job': t.get('jobName'), 'source': t.get('source'),
                        'ok': ok, 'note': note, 'ts': int(time.time())})
        print(f"[{i+1}/{len(targets)}] {'OK ' if ok else 'FAIL'} {t.get('brand')} | {(t.get('jobName') or '')[:24]} | {note}", flush=True)
        json.dump(results, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        fails = 0 if ok else fails + 1
        if fails >= 6:
            print("!! 连续 6 次失败，中止", flush=True)
            break
        time.sleep(delay)
    okn = sum(1 for r in results if r.get('ok'))
    print(f"结束：成功 {okn} / {len(results)}", flush=True)
