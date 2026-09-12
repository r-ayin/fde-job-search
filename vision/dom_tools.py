# -*- coding: utf-8 -*-
"""DOM 定位工具：读数据、找元素、拿坐标——全程零网络请求。

为什么不用 OCR（架构决策，2026-09-11 修正）：
  Runtime.evaluate 读 DOM 不产生网络请求、不派发事件、不修改 DOM，服务端完全看不到。
  而 OCR 必须先加载页面才能截图——那一次 Page.navigate 照样发生。
  所以 OCR 对可检测性零贡献，反而多出截图 + 推理耗时和识别误差。

  正确分工：
    - 定位元素 → DOM（getBoundingClientRect，精确、快、零成本）
    - 点击     → CDP 真实坐标（保 isTrusted=True，这是 DOM .click() 做不到的）
  两者结合既隐蔽又准确。

OCR 仅保留一个兜底场景：字体反爬字段（如 job_detail 页的 salary，DOM 里读不到数字）。
"""
import json


def decode_pua_salary(text):
    """解码 BOSS 薪资的 PUA 字体反爬。

    BOSS 用自定义字体 kanzhun-mix 把数字渲染成 PUA 私有区字符，
    DOM 里读到的形如 '-元/天'，
    真实值是 '120-240元/天'。

    映射规律（实测验证，10 个字符全覆盖）：
        数字 d -> chr(0xE031 + d)   即 =0, =1 ... =9
    校验：Accio Work · FDE 工程师 解码得 '120-240元/天'，与接口明文一致。

    这是从"DOM 读取"替代"接口调用"后必须补的一步：接口返回明文，
    DOM 返回 PUA，不解码就无法按薪资筛选。
    """
    if not text:
        return text
    out = []
    for ch in text:
        o = ord(ch)
        if 0xE031 <= o <= 0xE03A:
            out.append(str(o - 0xE031))
        else:
            out.append(ch)
    return "".join(out)


def _eval(cdp, expr):
    """执行 JS 并取返回值。

    注意：cdp.send 返回的**已经是剥掉 CDP 信封**的命令结果（与 send_paced.RelayCDP
    一致），所以取 value 是 r["result"]["value"]。
    对比：send_v5.py 的 cmd() 返回原始响应，要多钻一层，两者不可混用。
    """
    r = cdp.send("Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "awaitPromise": True})
    if r.get("exceptionDetails"):
        return None
    return r.get("result", {}).get("value")


JS_FIND_BY_TEXT = r"""
(() => {
  const want = %s;
  const scope = %s;
  const root = scope ? document.querySelector(scope) : document;
  if (!root) return null;
  const els = [...root.querySelectorAll('a,button,div,span,li')];
  // 归一化空白后比较：BOSS 的按钮文本常带换行/多空格（如 "继续沟通\n   "、
  // "感兴趣 继续沟通"），用精确相等匹配会漏掉。\s 在 JS 正则里含换行。
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const w = norm(want);
  const hit = els.filter(e => norm(e.innerText) === w);
  if (!hit.length) return null;
  // 页面常有隐藏的同名副本（响应式/移动端版本，尺寸为 0），
  // 必须先按可见性过滤，否则会取到隐藏元素并误判为"找不到"（曾报 no_button）。
  const visible = hit.filter(e => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
  if (!visible.length) return null;
  // 在可见元素里取最深的（无其他可见匹配为其后代），避免命中外层容器
  let target = visible[visible.length - 1];
  for (const e of visible) {
    const descendant = visible.some(o => o !== e && e.contains(o));
    if (!descendant) { target = e; break; }
  }
  target.scrollIntoView({block: 'center'});
  const r = target.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  return JSON.stringify({
    x: r.x + r.width / 2, y: r.y + r.height / 2,
    w: r.width, h: r.height, text: norm(target.innerText),
    cls: (target.className || '').toString().slice(0, 60)
  });
})()
"""

JS_RECT_BY_SELECTOR = r"""
(() => {
  const el = document.querySelector(%s);
  if (!el) return null;
  el.scrollIntoView({block: 'center'});
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  return JSON.stringify({
    x: r.x + r.width / 2, y: r.y + r.height / 2,
    w: r.width, h: r.height,
    text: (el.innerText || '').trim().slice(0, 120)
  });
})()
"""

JS_TEXT = r"""
(() => {
  const el = %s;
  return el ? (el.innerText || '').trim() : null;
})()
"""


def find_by_text(cdp, text, scope=None):
    """按可见文本精确定位元素，返回 {x, y, w, h, text, cls}；找不到返回 None。

    坐标是 CSS 像素，可直接交给 real_click。
    scope 为可选 CSS 选择器，把搜索限制在某个容器内。
    """
    expr = JS_FIND_BY_TEXT % (json.dumps(text, ensure_ascii=False),
                              json.dumps(scope) if scope else "null")
    raw = _eval(cdp, expr)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def find_by_selector(cdp, selector):
    """按 CSS 选择器定位，返回中心坐标；找不到或不可见返回 None。"""
    raw = _eval(cdp, JS_RECT_BY_SELECTOR % json.dumps(selector))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def read_text(cdp, selector):
    """读取某选择器的文本（零网络请求）。"""
    return _eval(cdp, JS_TEXT % (f"document.querySelector({json.dumps(selector)})"))


def read_page(cdp, selectors):
    """按选择器映射批量读取。返回 {key: text}。"""
    out = {}
    for k, sel in selectors.items():
        out[k] = read_text(cdp, sel)
    return out


# ---- BOSS 搜索页结构（来自 collect_search.js 等既有脚本的实测选择器）----
JS_JOB_CARDS = r"""
(() => {
  const cards = [];
  const boxes = [...document.querySelectorAll('li.job-card-box')];
  for (const li of boxes) {
    const a = li.querySelector('a.job-name');
    if (!a) continue;
    const href = a.getAttribute('href') || '';
    const m = href.match(/job_detail\/([^.?]+)/);
    if (!m) continue;
    const q = s => { const e = li.querySelector(s); return e ? e.innerText.trim() : ''; };
    const linkRect = a.getBoundingClientRect();
    cards.push({
      eid: m[1],
      jobName: q('a.job-name'),
      salaryRaw: q('.job-salary'),
      company: q('.company-name') || q('.boss-name'),
      tags: [...li.querySelectorAll('.tag-list li')].map(e => e.innerText.trim()).filter(Boolean),
      location: q('.company-location'),
      x: linkRect.x + linkRect.width / 2,
      y: linkRect.y + linkRect.height / 2
    });
  }
  return JSON.stringify({
    url: location.href,
    n: cards.length,
    hasNoMore: (document.body.innerText || '').indexOf('没有更多') >= 0,
    cards: cards
  });
})()
"""


def read_job_cards(cdp):
    """读搜索结果页的岗位卡（零网络请求，替代 joblist.json 接口）。

    返回 {url, n, hasNoMore, cards:[{eid, jobName, salary, company, tags, location, x, y}]}
    """
    raw = _eval(cdp, JS_JOB_CARDS)
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except Exception:
        return None
    # 薪资是 PUA 字体反爬，统一解码为明文
    for c in d.get("cards") or []:
        c["salary"] = decode_pua_salary(c.pop("salaryRaw", "") or "")
    return d


def scroll_to_bottom(cdp, rounds=8, wait=1.2):
    """逐步滚动到底以触发懒加载。返回滚动前后卡片数。"""
    import time
    before = _eval(cdp, "document.querySelectorAll('li.job-card-box').length")
    for _ in range(rounds):
        cdp.send("Runtime.evaluate", {
            "expression": "window.scrollTo(0, document.documentElement.scrollHeight)"})
        time.sleep(wait)
        if _eval(cdp, "(document.body.innerText||'').indexOf('没有更多')>=0"):
            break
    after = _eval(cdp, "document.querySelectorAll('li.job-card-box').length")
    return before, after
