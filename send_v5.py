# -*- coding: utf-8 -*-
"""批量发送求职消息 v5 —— 详情页驱动 + 岗位卡片稳定校验。

关键修复（相对 v4）：
  切换会话后，BOSS 的 .chat-position-content 更新比 .chat-conversation 慢。
  v4 会在卡片未更新时读取到上一个会话的岗位名 → 文案岗位名错配。
  v5 强制要求：岗位卡片文本**连续 3 次采样一致**才认为稳定，且必须与会话头部品牌对应。
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


JS_READ = """
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


def read_state():
    raw = val(JS_READ)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def wait_panel_stable(brand, need=3, timeout_s=14):
    """等岗位卡片稳定：连续 need 次采样岗位名一致，且会话头部含品牌。"""
    last = None
    stable = 0
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st = read_state()
        conv = st.get('conv') or ''
        pos = st.get('pos') or ''
        panel_job = pos.split(' / ')[0].strip() if pos else ''
        if brand and brand in conv and panel_job:
            if panel_job == last:
                stable += 1
                if stable >= need:
                    return panel_job, st
            else:
                last = panel_job
                stable = 1
        time.sleep(0.6)
    return (last if stable else None), read_state()


def send_one(t):
    eid = t['eid']
    brand = t.get('brand') or ''
    desc = t.get('desc') or ''
    job_from_list = (t.get('jobName') or '').strip()

    # 1) 打开岗位详情页
    cmd("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    ready = False
    for _ in range(12):
        time.sleep(1.2)
        u = val("location.href") or ''
        if eid in u and val("!!document.querySelector('.job-sec-text')") is True:
            ready = True
            break
    if not ready:
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
        time.sleep(1.0)
        if '/web/geek/chat' in (val("location.href") or ''):
            break

    # 4) 等面板稳定并校验品牌
    actual_job = None
    st = {}
    for attempt in range(3):
        job, st = wait_panel_stable(brand, need=3, timeout_s=12)
        conv = st.get('conv') or ''
        if job and brand and brand in conv:
            actual_job = job
            break
        # 品牌不匹配 → 可能停在上一个会话，尝试点击列表中的目标
        val("""(()=>{
          const brand = %s;
          const items = [...document.querySelectorAll('.friend-content-warp')];
          for (const w of items) {
            if ((w.innerText||'').indexOf(brand) >= 0) {
              (w.querySelector('.friend-content')||w.firstElementChild||w).click();
              return 'clicked';
            }
          }
          return 'not_in_list';
        })()""" % json.dumps(brand, ensure_ascii=False))
        time.sleep(2.5)

    if not actual_job:
        return False, f'panel_unstable:conv={(st.get("conv") or "")[:34]}'

    # 5) 岗位名以「列表已知的 jobName」为准；若与面板不一致，以面板为准并记录
    use_job = actual_job
    note_extra = ''
    if job_from_list and job_from_list != actual_job:
        # 以面板为准（面板来自实时页面，更可信）
        note_extra = f'[list说={job_from_list[:16]} 用面板]'

    msg = build_message(use_job, desc)

    # 6) 写入（重试）
    ist = {}
    for _ in range(10):
        r = val("(()=>{const el=document.getElementById('chat-input');if(!el)return 0;el.focus();el.innerHTML='';return 1;})()")
        if r != 1:
            time.sleep(1.0)
            continue
        time.sleep(0.4)
        cmd("Input.insertText", {"text": msg})
        time.sleep(1.2)
        ist = read_state()
        if (ist.get('inputLen') or 0) >= 50 and 'disabled' not in str(ist.get('btn')):
            break
        time.sleep(1.0)
    if (ist.get('inputLen') or 0) < 50:
        return False, f'write_failed:{ist.get("inputLen")}'
    if 'disabled' in str(ist.get('btn')):
        return False, 'btn_disabled'

    # 7) 写入后再确认会话未变
    st2 = read_state()
    if brand and brand not in (st2.get('conv') or ''):
        return False, 'switch_after_write'

    val("""(()=>{const b=[...document.querySelectorAll('div,button')].find(x=>/^\\s*发送\\s*$/.test(x.innerText||''));b.click();return 1;})()""")
    time.sleep(3)
    st3 = read_state()
    if (st3.get('inputLen') or 0) == 0:
        return True, f'sent[{use_job[:16]}]{note_extra}'
    return False, f'not_cleared:{st3.get("inputLen")}'


if __name__ == '__main__':
    tf = sys.argv[1] if len(sys.argv) > 1 else 'send_targets.json'
    targets = json.load(open(tf, encoding='utf-8'))
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    end = int(sys.argv[3]) if len(sys.argv) > 3 else len(targets)
    delay = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0

    outfile = 'send_results_v5.json'
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
        print(f"[{i+1}/{len(targets)}] {'OK ' if ok else 'FAIL'} {t.get('brand')} | {(t.get('jobName') or '')[:22]} | {note}", flush=True)
        json.dump(results, open(outfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        fails = 0 if ok else fails + 1
        if fails >= 6:
            print("!! 连续 6 次失败，中止", flush=True)
            break
        time.sleep(delay)
    okn = sum(1 for r in results if r.get('ok'))
    print(f"结束：成功 {okn} / {len(results)}", flush=True)
