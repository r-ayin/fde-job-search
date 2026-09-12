# -*- coding: utf-8 -*-
"""带反风控节奏控制的发送主流程。

架构（2026-09-11）：**DOM 定位 + CDP 真实事件**，不用 OCR。
  Runtime.evaluate 读 DOM 零网络请求、2ms 完成（实测）；OCR 要先截图再推理（1490ms），
  且页面该加载还得加载 —— OCR 对可检测性零贡献。
保留的隐蔽性改进：
  1. element.click() -> real_click（真实坐标，isTrusted=True）
  2. 正文用 insert_text 写入（见下方"换行安全"）
  3. el.innerHTML='' -> clear_field（Ctrl+A + Delete，走真实按键）
反风控节奏层：单轮上限 5 人，随机间隔 25~70s，每日封顶 30，风控信号自动熔断。

⚠️ 换行安全（2026-09-11 实际事故后修正）
  BOSS 聊天输入框是「按 Enter 发送」模式。原实现用逐字符 dispatchKeyEvent 写入，
  消息里的换行被当成真实 Enter，**在输入过程中把内容分段发送出去**——
  一条 4 段文案被拆成 8 条消息误发给 HR。
  现改用 Input.insertText 写正文：走文本插入通道，不产生按键事件，换行安全，
  事件仍为 isTrusted=True。type_text 已加断言，含换行直接抛错。

⚠️ 会话匹配（同一公司多个 HR 的坑）
  同一家公司可能有多个 HR、多个岗位的会话（如红熊智能的"潘**/AI智能体专家"
  与"何**/产品运营"）。仅按公司名匹配会点到错误对象。
  现按「品牌 + HR 姓名」匹配，并在发送前用面板校验岗位名。

安全阀：
  --dry-run    只走流程不点发送按钮，也**不写入聊天框**（BOSS 是 Enter 发送模式，
               任何误触都可能发出去），仅验证定位与岗位校验
  --limit N    本次最多发送 N 条
  --skip-open  直接在会话列表点开，不加载岗位详情页（省一次页面访问）
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from dom_tools import find_by_text  # noqa: E402
from fde_classify import is_fde  # noqa: E402
from input_primitives import clear_field, insert_text, real_click  # noqa: E402
from pacing import Pacing, RiskCircuitBreaker, is_risk_signal  # noqa: E402

PORT = 18793
SESSION = "cb-tab-3"

# ---- 文案（沿用 send_v5 的定稿内容）----
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

# 阿里系公司：用户明确要求不发
ALI_MARKS = ['阿里', '阿里巴巴', 'alibaba', '淘天', '淘宝', '天猫', '飞猪', '菜鸟',
             '蚂蚁', '支付宝', '钉钉', '夸克', '饿了么', '高德', '阿里云',
             'ICBU', 'Accio', '1688', '闲鱼', '盒马', '本地生活', '阿里国际']


def is_anonymized(brand):
    """判断是否是 BOSS 的匿名公司名（如「某大型互联网公司」）。

    这类岗位是猎头/外包代招，会话头部不会出现该名字（只有"某**/猎头顾问"），
    因此不能用它做身份校验。
    """
    b = (brand or "").strip()
    return b.startswith("某") or "某大型" in b or "某中型" in b or "某知名" in b


def is_ali(text):
    """判断文本是否指向阿里系公司。"""
    t = (text or "").lower()
    return any(k.lower() in t for k in ALI_MARKS)


RAG_HINTS = ['向量', 'RAG', '检索', '知识库', 'Embedding']
TRIP_HINTS = ['出差', '驻场', '客户现场', '现场实施']

# 岗位名里可能带薪资后缀（如 "FDE工程师 18-30K·13薪"），发文案时要剥掉
RE_JOB_TAIL = re.compile(
    r"\s*(\d+\s*-\s*\d+\s*[Kk](·\d+薪)?|\d+\s*-\s*\d+\s*元/?[天月]?|面议)\s*$")


def clean_job(text):
    """剥离岗位名尾部的薪资，避免把 '18-30K' 写进文案。"""
    if not text:
        return text
    return RE_JOB_TAIL.sub("", text).strip()


def norm(s):
    """归一化用于比较：去空白、标点、大小写。"""
    return re.sub(r"[\s（）()【】\[\]、,，.。·/\\\-_|]", "", (s or "")).lower()


def job_matches(file_job, panel_job):
    """判断目标岗位名与面板岗位名是否指向同一岗位（宽松子串匹配）。"""
    a, b = norm(file_job), norm(panel_job)
    if not a or not b:
        return True  # 缺一方信息时不拦截
    return a in b or b in a


class RelayCDP:
    """把 relay 的 /cmd 端点包装成 send(method, params)。

    约定：send() 返回**已剥掉 CDP 信封**的命令结果，即直接拿到
    {"result": {...}, "exceptionDetails": ...}。
    """

    def __init__(self, port=PORT, session=SESSION, timeout=90):
        self.port, self.session, self.timeout = port, session, timeout

    def send(self, method, params=None):
        body = json.dumps({"method": method, "params": params or {},
                           "sessionId": self.session}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/cmd", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            resp = json.load(r)
        if "error" in resp:
            raise RuntimeError(f"{method}: {resp['error']}")
        return resp.get("result", {})

    def val(self, expr, timeout=60):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        if r.get("exceptionDetails"):
            return None
        return r.get("result", {}).get("value")

    def ensure_focus(self, force=False):
        """确保标签页在前台且文档有焦点。

        为什么必须做：Chrome 在后台时 document.visibilityState === 'hidden'、
        document.hasFocus() === false，此时 Input.dispatchMouseEvent 派发的事件
        不会投递到页面 —— 表现为"点击完全无反应、零事件、零网络请求"。
        （ZCode 会抢前台焦点，本目录的 activate.ps1 就是为此存在的。）
        """
        try:
            if force or self.val("document.hasFocus()") is not True:
                self.send("Page.bringToFront", {})
                import time as _t
                _t.sleep(0.6)
                return self.val("document.hasFocus()") is True
            return True
        except Exception:
            return False


def build_message(job_name, desc):
    desc = desc or ''
    job = clean_job(job_name or '该岗位')
    p4 = P4_RAG if any(k in desc for k in RAG_HINTS) else P4
    body = (f"您好，看到「{job}」这个岗位，我的经历有几处和贵司需求比较契合，想和您具体聊聊：\n"
            f"{P1}\n{P2}\n{P3}\n{p4}\n")
    if any(k in desc for k in TRIP_HINTS):
        body += "我接受出差和客户现场驻场交付。\n"
    body += "期待有机会和您进一步沟通。" + AI_TAIL
    return body + RESUME_BLOCK


# ---- 页面读取：只读 DOM，零网络请求 ----
JS_READ = """
(() => {
  const cv = document.querySelector('.chat-conversation');
  const pc = document.querySelector('.chat-position-content');
  const el = document.getElementById('chat-input');
  const btn = [...document.querySelectorAll('div,button')].find(x => /^\\s*发送\\s*$/.test(x.innerText || ''));
  const r = btn ? btn.getBoundingClientRect() : null;
  const ir = el ? el.getBoundingClientRect() : null;
  const pcLines = pc ? pc.innerText.split('\\n').filter(Boolean) : [];
  return JSON.stringify({
    url: location.href,
    body: (document.body.innerText || '').slice(0, 400),
    conv: cv ? cv.innerText.split('\\n').filter(Boolean).slice(0, 8).join(' / ') : null,
    pos: pcLines.join(' / '),
    posFirst: pcLines.length ? pcLines[0] : null,
    hasInput: !!el,
    inputLen: el ? (el.innerText || '').length : -1,
    btnText: btn ? btn.innerText.trim() : null,
    btnDisabled: btn ? (btn.classList.contains('disabled') || btn.disabled === true || btn.getAttribute('aria-disabled') === 'true') : null,
    btnRect: r ? {x: r.x + r.width / 2, y: r.y + r.height / 2} : null,
    inputRect: ir ? {x: ir.x + ir.width / 2, y: ir.y + ir.height / 2} : null
  });
})()
"""


class Sender:
    def __init__(self, cdp, dry_run=False, skip_open=False, verbose=True):
        self.cdp = cdp
        self.dry_run, self.skip_open, self.verbose = dry_run, skip_open, verbose

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def _focus(self):
        """确保标签页在前台（CDP 实现可能没有 ensure_focus，做兼容）。"""
        fn = getattr(self.cdp, "ensure_focus", None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                return None
        return None

    def read_state(self):
        raw = self.cdp.val(JS_READ)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def check_risk(self, st):
        return is_risk_signal(st.get("url"), st.get("body"))

    # ---------- 会话列表 ----------

    def list_convs(self):
        """列出当前已渲染的会话（虚拟列表，只有可见部分）。"""
        raw = self.cdp.val(
            "JSON.stringify([...document.querySelectorAll('.friend-content-warp')]"
            ".map(w => (w.innerText||'').replace(/\\n+/g,' / ').trim()))")
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    def click_conv_index(self, idx):
        """滚动到指定会话并真实点击。返回 (ok, note)。"""
        raw = self.cdp.val(
            "(()=>{const w=document.querySelectorAll('.friend-content-warp')[%d];"
            "if(!w)return null;const el=w.querySelector('.friend-content')||w.firstElementChild||w;"
            "el.scrollIntoView({block:'center'});return 'ok';})()" % idx)
        if raw != "ok":
            return False, "index_gone"
        time.sleep(0.4)
        rect = self.cdp.val(
            "(()=>{const w=document.querySelectorAll('.friend-content-warp')[%d];"
            "if(!w)return null;const el=w.querySelector('.friend-content')||w.firstElementChild||w;"
            "const b=el.getBoundingClientRect();"
            "return JSON.stringify({x:b.x+b.width/2,y:b.y+b.height/2});})()" % idx)
        if not rect:
            return False, "no_rect"
        try:
            xy = json.loads(rect)
        except Exception:
            return False, "bad_rect"
        real_click(self.cdp, xy["x"], xy["y"])
        time.sleep(1.5)
        return True, "clicked"

    def _scroller(self):
        """返回会话列表滚动容器的 {st, sh, ch}，找不到返回 None。"""
        r = self.cdp.val(
            "(()=>{const f=document.querySelector('.friend-content-warp');"
            "if(!f)return null;let el=f.parentElement,best=null;"
            "for(let i=0;i<12&&el;i++){if(el.scrollHeight>el.clientHeight+20){best=el;break;}"
            "el=el.parentElement;}"
            "return best?JSON.stringify({st:best.scrollTop,sh:best.scrollHeight,ch:best.clientHeight}):null;})()")
        if not r:
            return None
        try:
            return json.loads(r)
        except Exception:
            return None

    def scroll_list(self):
        """会话列表向下滚动一屏。返回是否到底。"""
        r = self.cdp.val(
            "(()=>{const f=document.querySelector('.friend-content-warp');"
            "if(!f)return 'no_item';let el=f.parentElement,best=null;"
            "for(let i=0;i<12&&el;i++){if(el.scrollHeight>el.clientHeight+20){best=el;break;}"
            "el=el.parentElement;}"
            "if(!best)return 'no_scroller';"
            "best.scrollTop=best.scrollTop+best.clientHeight*0.85;"
            "return JSON.stringify({st:best.scrollTop,sh:best.scrollHeight,ch:best.clientHeight});})()")
        try:
            d = json.loads(r) if r and r.startswith("{") else {}
        except Exception:
            d = {}
        return bool(d) and d.get("st", 0) + d.get("ch", 0) >= d.get("sh", 0) - 5

    def scroll_to_top(self):
        self.cdp.val(
            "(()=>{const f=document.querySelector('.friend-content-warp');"
            "if(!f)return 0;let el=f.parentElement;"
            "for(let i=0;i<12&&el;i++){if(el.scrollHeight>el.clientHeight+20){el.scrollTop=0;break;}"
            "el=el.parentElement;}return 1;})()")
        time.sleep(0.6)

    def _conv_rect_by_text(self, brand, hr, job=None):
        """在**当前渲染**的会话里按文本匹配，命中则滚动到可见并返回坐标。

        匹配键：品牌（必需）+ HR 姓名（可选）+ 岗位名（可选，优先级最高）。
        列表项文本包含最后一条消息，而我们发过的招呼语里带「岗位名」，
        所以同公司多 HR 时可以靠岗位名区分。

        关键：查找与取坐标在同一次 JS 求值内完成，避免"先按索引找、再按索引点"
        之间的列表变化导致点错（滚动会改变渲染集合，索引会失效）。
        """
        expr = ("(()=>{const brand=%s,hr=%s,job=%s;"
                "for (const w of document.querySelectorAll('.friend-content-warp')) {"
                "  const t=(w.innerText||'');"
                "  if (t.indexOf(brand)<0) continue;"
                "  if (hr && t.indexOf(hr)<0) continue;"
                "  if (job && t.indexOf(job)<0) continue;"
                "  const el=w.querySelector('.friend-content')||w.firstElementChild||w;"
                "  el.scrollIntoView({block:'center'});"
                "  const b=el.getBoundingClientRect();"
                "  return JSON.stringify({x:b.x+b.width/2,y:b.y+b.height/2,"
                "    text:t.split(String.fromCharCode(10)).join(' | ').slice(0,70)});"
                "} return null;})()") % (json.dumps(brand, ensure_ascii=False),
                                         json.dumps(hr or "", ensure_ascii=False),
                                         json.dumps(job or "", ensure_ascii=False))
        raw = self.cdp.val(expr)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def open_in_list(self, brand, hr=None, job=None):
        """按「品牌 + HR」滚动查找并点开会话。

        会话列表是虚拟滚动：DOM 里只有当前窗口内的项，整列表约 14 屏，
        必须滚动查找（曾因 max_scrolls 太小导致"明明在列表里却找不到"）。

        必须带 HR：同一公司可能有多个会话（不同 HR / 不同岗位），
        只按品牌会点到错误对象（2026-09-11 实际发生过）。
        找不到精确匹配时直接失败，**不降级**为只按品牌匹配。
        """
        self.scroll_to_top()
        info = self._scroller()
        # 按容器高度自适应计算需要的轮数，留 6 轮余量
        if info and info.get("ch"):
            max_scrolls = int(info["sh"] / info["ch"]) + 6
        else:
            max_scrolls = 25

        # 三级尝试（从最严格到最宽松）：
        #   1) 品牌 + HR + 岗位  —— 最精确
        #   2) 品牌 + HR
        #   3) 品牌            —— 仅当列表项不含 HR 名时（BOSS 有些会话列表项
        #                          只显示公司不显示 HR），此时靠面板岗位校验兜底
        attempts = [(hr, job, "品牌+HR+岗位"), (hr, None, "品牌+HR")]
        if hr:
            attempts.append((None, None, "仅品牌(列表项无HR名时)"))
        for hr_key, job_key, label in attempts:
            hit = self._scan_for(brand, hr_key, job_key, max_scrolls)
            if hit:
                if hr_key is None and hr:
                    self.log(f"     ⚠️ 列表项未含 HR「{hr}」，降级为仅品牌匹配，"
                             f"将由面板校验兜底")
                self.log(f"     列表命中[{label}]: {hit['text']}")
                real_click(self.cdp, hit["x"], hit["y"])
                time.sleep(1.5)
                return True, "list_clicked"
        return False, (f"conv_not_found(滚动{max_scrolls}屏，品牌「{brand}」"
                       + (f" HR「{hr}」" if hr else "")
                       + (f" 岗位「{(job or '')[:14]}」" if job else "") + " 均未命中)")

    def _scan_for(self, brand, hr, job, max_scrolls):
        """滚动全表查找一次，命中返回坐标字典，否则 None。"""
        self.scroll_to_top()
        for i in range(max_scrolls):
            hit = self._conv_rect_by_text(brand, hr, job)
            if hit:
                return hit
            if self.scroll_list():
                return self._conv_rect_by_text(brand, hr, job)
            time.sleep(0.7)
        return None

    # ---------- 面板校验 ----------

    @staticmethod
    def identity_ok(conv, brand, hr):
        """判断会话头部是否属于目标对象。

        匹配优先级：
          1. HR 姓名命中 -> 通过（最可靠）
          2. 公司名命中  -> 通过（有些会话头部只显示公司，或 HR 名被省略）
          3. 匿名公司名（「某大型…」）-> 放行，靠面板岗位名校验兜底
             （这类是猎头/外包代招，会话头部只显示"某**/猎头顾问"，
               品牌名不可能出现；不放行会导致全部被误拦）
          4. 都不命中    -> 失败

        注意：.chat-conversation 的内容格式不固定，实测两种都出现过：
          "蔡** / 资深招聘专家 / 更多 / ..."       （只有 HR）
          "江** / 润和软件 / 招聘专员 / 更多 / ..." （HR + 公司）
        所以不能只认 HR，否则会误判。
        """
        conv = conv or ""
        if hr and hr in conv:
            return True
        if brand and brand in conv:
            return True
        if is_anonymized(brand):
            return True
        return False

    def await_panel(self, brand, hr=None, need=3, timeout_s=14):
        """等岗位卡片稳定：连续 need 次采样一致，且会话头部身份匹配。

        两个坑：
        1. 切换会话后 .chat-position-content 更新比 .chat-conversation 慢，
           立刻读会拿到上一个会话的岗位名（send_v5 修复过）。
        2. 会话头部没有公司名，身份校验要用 HR 姓名。
        """
        last, stable = None, 0
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            st = self.read_state()
            conv = st.get("conv") or ""
            panel_job = clean_job(st.get("posFirst") or "")
            if self.identity_ok(conv, brand, hr) and panel_job:
                if panel_job == last:
                    stable += 1
                    if stable >= need:
                        return panel_job, st
                else:
                    last, stable = panel_job, 1
            time.sleep(0.6)
        return (last if stable else None), self.read_state()

    def click_button(self, text):
        """DOM 定位按钮 -> 真实坐标点击。返回 (ok, note)。"""
        self._focus()
        loc = find_by_text(self.cdp, text)
        if not loc:
            return False, f"not_found:{text}"
        real_click(self.cdp, loc["x"], loc["y"])
        return True, f"clicked:{text}={loc.get('text')}"

    def open_target(self, t):
        """打开目标会话。skip_open 时直接列表点开，否则走详情页。"""
        brand = t.get("brand") or ""
        hr = t.get("hr") or ""
        if self.skip_open:
            ok, note = self.open_in_list(brand, hr, clean_job(t.get("jobName") or ""))
            if not ok:
                return False, note
            for _ in range(10):
                st = self.read_state()
                if self.identity_ok(st.get("conv"), brand, hr):
                    return True, "list_opened"
                time.sleep(0.6)
            return False, f"list_open_timeout(conv={(self.read_state().get('conv') or '')[:26]})"

        eid = t["eid"]
        self._focus()
        self.cdp.send("Page.navigate",
                      {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
        # 就绪条件必须包含"沟通按钮已出现"：URL 在内容渲染前就变了，
        # 只看 URL 会过早判定就绪，导致点按钮时页面还没渲染（曾报 no_button）。
        ready = False
        for _ in range(16):
            time.sleep(1.2)
            st = self.read_state()
            if eid not in (st.get("url") or ""):
                continue
            has_btn = self.cdp.val(
                "!!([...document.querySelectorAll('a,div')]"
                ".find(e=>/^(立即沟通|继续沟通)$/.test((e.innerText||'').trim())))")
            if has_btn:
                ready = True
                break
        if not ready:
            return False, "detail_not_ready(无沟通按钮)"

        # 顺手读 JD 正文 + 真实公司名：同一次页面加载内完成，不产生额外请求。
        # 公司名取 document.title 里的「_XXX招聘-BOSS直聘」段：
        # 详情页的 .company-info / .company-name 选择器实测会抓到岗位名（BOSS 改过结构），
        # 只有 title 稳定包含真实公司名。
        page_info = self.cdp.val(
            "(()=>{"
            "const jd=document.querySelector('.job-sec-text');"
            "let comp='';"
            "const m=(document.title||'').match(/_([^_]+?)招聘-BOSS直聘/);"
            "if(m) comp=m[1].trim();"
            "if(!comp){"
            "  const el=document.querySelector('.sider-company .name,"
            "    .job-sec .company-name, .company-name');"
            "  if(el) comp=(el.innerText||'').trim().slice(0,60);"
            "}"
            "return JSON.stringify({"
            "  jd: jd ? (jd.innerText||'').split(String.fromCharCode(10)).join(' ').trim() : '',"
            "  company: comp});})()")
        if page_info:
            try:
                pi = json.loads(page_info)
            except Exception:
                pi = {}
            if pi.get("jd") and not (t.get("desc") or "").strip():
                t["desc"] = pi["jd"]
                self.log(f"     已读 JD {len(pi['jd'])} 字（同页，无额外请求）")
            real_comp = pi.get("company") or ""
            if real_comp and real_comp != (t.get("brand") or ""):
                self.log(f"     真实公司名: {real_comp}")
                t["realCompany"] = real_comp
            # 阿里系直接跳过（用户要求不发）
            if is_ali(real_comp) or is_ali(t.get("brand")):
                return False, f"skip_alibaba（{real_comp or t.get('brand')}）"

        # ⚠️ 点「立即沟通」会触发 BOSS 自动发送默认招呼语
        #    「能和您沟通一下吗？我对这个岗位兴趣很浓。」
        #    这是 BOSS 的固有行为，无法拦截。因此：
        #      - dry-run 到此为止，不点击（保证真正零副作用）
        #      - 实发时会先有一条默认招呼，再是定制文案（共 2 条）
        if self.dry_run:
            loc = (find_by_text(self.cdp, "立即沟通")
                   or find_by_text(self.cdp, "继续沟通"))
            if not loc:
                return False, "no_button(无沟通按钮)"
            return False, (f"[dry-run]确认可进入会话（按钮「{loc['text']}」已找到，"
                           f"未点击以免触发BOSS默认招呼语）")

        ok, note = self.click_button("立即沟通")
        if not ok:
            ok, note = self.click_button("继续沟通")
        if not ok:
            return False, f"no_button:{note}"
        # 等进入会话：必须**确认成功**再返回，否则后续读到空 conv 会误报 panel_mismatch
        entered = False
        for _ in range(20):
            time.sleep(1.0)
            if "/web/geek/chat" in (self.read_state().get("url") or ""):
                entered = True
                break
        if not entered:
            # 点「立即沟通」有时只创建会话、不跳转（按钮已变「继续沟通」）。
            # 兜底：回会话列表，按品牌+岗位找到刚建的会话再进入。
            self.log("     未自动跳转，回会话列表查找刚建的会话")
            self.cdp.send("Page.navigate",
                          {"url": "https://www.zhipin.com/web/geek/chat"})
            for _ in range(16):
                time.sleep(1.2)
                if self.cdp.val("document.querySelectorAll('.friend-content-warp').length"):
                    break
            ok2, note2 = self.open_in_list(brand, hr, clean_job(t.get("jobName") or ""))
            if not ok2:
                return False, f"chat_not_entered 且列表未找到({note2})"
            for _ in range(10):
                st = self.read_state()
                if self.identity_ok(st.get("conv"), brand, hr):
                    break
                time.sleep(0.6)
            entered = True
        # 再等会话面板渲染出内容
        for _ in range(12):
            if (self.read_state().get("conv") or "").strip():
                break
            time.sleep(0.8)
        return True, "chat_opened"

    # ---------- 主流程 ----------

    def send_one(self, t):
        brand = t.get("brand") or ""
        hr = t.get("hr") or ""
        # 岗位名以目标文件为准（已核对过 eid->jobName），面板只用于**校验**
        file_job = clean_job(t.get("jobName") or "")

        ok, note = self.open_target(t)
        if not ok:
            return False, note

        panel_job, st = self.await_panel(brand, hr=hr, need=3, timeout_s=14)
        risk = self.check_risk(st)
        if risk:
            raise RiskCircuitBreaker(f"页面出现风控信号：{risk}")
        conv = st.get("conv") or ""
        if not panel_job or not self.identity_ok(conv, brand, hr):
            return False, f"panel_mismatch:conv={conv[:30]}"

        # 岗位校验：面板与目标不一致时，按 JD 正文判断是否仍属 FDE 岗。
        # 目标文件的 jobName 由 eid 匹配 JD 得到，存在错配
        # （如奥星集团文件写"FDE（前沿部署工程师）"，面板实际是
        #   "AI解决方案经理（工业流程行业）"）。用户要求：此时以 JD 判定为准，
        # 是 FDE 就用**面板真实岗位名**发送，否则跳过。
        use_job = file_job or panel_job
        if file_job and panel_job and not job_matches(file_job, panel_job):
            desc = t.get("desc") or ""
            verdict, score, why = is_fde(desc, panel_job)
            if verdict is True:
                self.log(f"     岗位名不一致，JD 判定为 FDE（{score}分）："
                         f"文件「{file_job[:18]}」-> 面板「{panel_job[:18]}」"
                         f" [{why}]")
                use_job = panel_job          # 以面板真实岗位名为准
            else:
                tag = "非FDE" if verdict is False else "边界(需人工)"
                return False, (f"job_mismatch+{tag} 文件「{file_job[:16]}」"
                               f"≠面板「{panel_job[:16]}」| {why}")
        msg = build_message(use_job, t.get("desc") or "")
        self.log(f"     岗位「{use_job[:22]}」 文案 {len(msg)} 字")

        if self.dry_run:
            # dry-run 不写入聊天框：BOSS 是 Enter 发送模式，任何误触都可能发出去。
            # 这里只验证到"定位 + 岗位校验"这一步。
            return True, f"[dry-run]校验通过未写入[{use_job[:16]}]"

        ir = st.get("inputRect")
        if not ir:
            return False, "no_input_rect"
        self._focus()          # 后台标签页收不到输入事件
        real_click(self.cdp, ir["x"], ir["y"])
        time.sleep(0.4)

        # 清空必须**验证**：Ctrl+A 在 BOSS contenteditable 里可能没选中全部内容，
        # 导致上一次的文案残留，与本次拼接（曾出现 1224 = 609+615 的错误）。
        # 依次尝试：Ctrl+A+Delete → 循环退格兜底，每步都读长度确认。
        cleared = False
        for attempt in range(4):
            clear_field(self.cdp)
            time.sleep(0.4)
            left = self.cdp.val(
                "(()=>{const e=document.getElementById('chat-input');"
                "if(!e)return -1;"
                "return (e.innerText||'').split(String.fromCharCode(13))"
                ".join('').split(String.fromCharCode(10)).join('').length;})()")
            if left is not None and left <= 1:
                cleared = True
                break
            # 兜底：全选后连续退格
            self.cdp.val(
                "(()=>{const e=document.getElementById('chat-input');"
                "if(!e)return 0;e.focus();"
                "const r=document.createRange();r.selectNodeContents(e);"
                "const s=getSelection();s.removeAllRanges();s.addRange(r);return 1;})()")
            time.sleep(0.2)
            for _ in range(6):
                self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Backspace", "code": "Backspace",
                    "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8})
                self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Backspace", "code": "Backspace",
                    "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8})
                time.sleep(0.05)
            time.sleep(0.3)
        if not cleared:
            return False, f"clear_failed:清空{attempt + 1}次仍残留"

        insert_text(self.cdp, msg)          # 换行安全，见文件头说明
        time.sleep(0.6)

        st2 = self.read_state()
        got = st2.get("inputLen") or 0
        # 长度必须与消息一致：短了说明写入被截断或落错地方，绝不发送
        if got != len(msg):
            return False, f"write_len_mismatch:期望{len(msg)} 实际{got}（已中止，未发送）"
        if not self.identity_ok(st2.get("conv"), brand, hr):
            return False, "switch_after_write"

        risk = self.check_risk(st2)
        if risk:
            raise RiskCircuitBreaker(f"写入后出现风控信号：{risk}")

        if st2.get("btnDisabled"):
            return False, "btn_disabled"

        # 点发送：每次重试都重新定位取新坐标。
        # 按下与抬起之间若页面重排（新消息到达/列表刷新），浏览器 click target
        # 取二者最近公共祖先，按钮处理函数不执行 —— 表现为"点了但没发出去"。
        last = None
        for attempt in range(3):
            self._focus()
            loc = find_by_text(self.cdp, "发送")
            if not loc:
                return False, "no_send_button"
            real_click(self.cdp, loc["x"], loc["y"], settle=0.02)
            time.sleep(2.0)
            st3 = self.read_state()
            if (st3.get("inputLen") or 0) == 0:
                tag = f"retry{attempt}" if attempt else "sent"
                return True, f"{tag}[{use_job[:16]}]"
            last = st3
            self.log(f"     发送未生效（第 {attempt + 1} 次），重新定位按钮重试")
        return False, f"not_cleared:{last.get('inputLen') if last else '?'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="?", default="send_targets.json")
    ap.add_argument("--limit", type=int, default=5, help="本次最多发送条数（默认 5）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只验证定位与岗位校验，不写入聊天框、不点发送")
    ap.add_argument("--skip-open", action="store_true",
                    help="目标已在会话列表中，直接列表点开，不加载岗位详情页")
    args = ap.parse_args()

    cdp = RelayCDP()
    sender = Sender(cdp, dry_run=args.dry_run, skip_open=args.skip_open)
    pacing = Pacing()

    targets = json.load(open(args.targets, encoding="utf-8"))
    print(f"目标池 {len(targets)} 条 | 单轮上限 {pacing.batch_cap} | "
          f"间隔 {pacing.interval_min:.0f}~{pacing.interval_max:.0f}s | "
          f"今日已发 {pacing.sent_today}/{pacing.daily_cap} | "
          f"{'DRY-RUN' if args.dry_run else '实发'} | "
          f"{'列表点开' if args.skip_open else '详情页'}")

    allow = pacing.check_before_round(args.limit)
    todo = targets[:allow]
    results = []
    for i, t in enumerate(todo):
        print(f"\n[{i+1}/{len(todo)}] {t.get('brand')} | hr={t.get('hr')} | "
              f"{(t.get('jobName') or '')[:24]}")
        if sender._focus() is False:
            print("   ⚠️ 无法激活 Chrome 标签页，输入事件可能不生效")
        try:
            ok, note = sender.send_one(t)
        except RiskCircuitBreaker as e:
            pacing.trip(e)
            print(f"⛔ 已熔断，停止本轮。已完成 {sum(1 for r in results if r[1])} 条")
            break
        except Exception as e:
            ok, note = False, f"error:{str(e)[:80]}"
        print(f"   {'OK ' if ok else 'FAIL'} {note}")
        results.append((t, ok, note))
        if ok and not args.dry_run:
            pacing.record_success()
        if pacing.should_verify(i) and i < len(todo) - 1:
            print("[pacing] 轻量校验：检查页面是否出现风控")
            risk = sender.check_risk(sender.read_state())
            if risk:
                pacing.trip(f"周期校验命中：{risk}")
                break
        if i < len(todo) - 1:
            pacing.wait_between(i, len(todo))

    out = [{"eid": t["eid"], "brand": t.get("brand"), "hr": t.get("hr"),
            "job": t.get("jobName"), "ok": ok, "note": note}
           for t, ok, note in results]
    fn = "send_results_paced.json"
    json.dump(out, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完成：成功 {sum(1 for _, ok, _ in results if ok)}/{len(results)} | 结果写入 {fn}")
    print(f"今日累计已发 {pacing.sent_today}/{pacing.daily_cap}")


if __name__ == "__main__":
    main()
