# -*- coding: utf-8 -*-
"""投递前实时清洗（周一 09:30 先跑这个，再跑投递）。

为什么需要：清单是提前采集的，到周一可能已经过期——
  - 岗位下架 / 已停止招聘
  - 公司已招满
  - 岗位信息被 HR 修改（标题变了、不再是 AI 交付类）
  - 期间账号若又联系过某些公司

做法（只读，零风险）：
  逐条打开岗位详情页，检查：
    1. 页面是否还正常（不是 404 / 已关闭）
    2. 是否还能沟通（按钮是「立即沟通」或「继续沟通」，不是「已关闭」）
    3. 标题是否与清单一致（防 HR 改岗）
    4. 阿里系 → 剔除
    5. JD 是否仍属 AI 交付类
  输出 clean_monday.json（可投）+ monday_dropped.json（剔除明细）
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "vision"))

from send_paced import RelayCDP, clean_job, is_ali  # noqa: E402

SRC = os.path.join(HERE, "monday30.json")
OUT = os.path.join(HERE, "monday_clean.json")
DROP = os.path.join(HERE, "monday_dropped.json")

# AI 交付相关必须命中
AI_MARK = r"AI|ai|智能|大模型|模型|Agent|agent|算法|机器学习|数智|数字化|RAG|LLM|机器人|自动化"
DELIVER_MARK = r"交付|实施|部署|解决方案|顾问|项目经理"
# 关闭/失效信号
CLOSED = r"职位已关闭|已停止招聘|该职位已下线|职位不存在|已招满|暂停招聘"


class PageProbe:
    """单页探测（只读）。"""

    JS = r"""
    (() => {
      const norm = s => (s || '').replace(/\s+/g, ' ').trim();
      const body = norm(document.body.innerText || '');
      const jd = document.querySelector('.job-sec-text');
      let comp = '';
      const m = (document.title || '').match(/_([^_]+?)招聘-BOSS直聘/);
      if (m) comp = m[1].trim();
      const btns = [...document.querySelectorAll('a,div,button')]
        .filter(e => {
          const t = norm(e.innerText);
          const r = e.getBoundingClientRect();
          return r.width > 0 && r.height > 0 && t.length < 16 &&
                 /立即沟通|继续沟通|已关闭|停止招聘|已下线/.test(t);
        })
        .map(e => norm(e.innerText));
      const h1 = document.querySelector('h1');
      return JSON.stringify({
        url: location.href,
        title: document.title,
        company: comp,
        jobTitle: h1 ? norm(h1.innerText) : '',
        hasJD: !!jd,
        jdLen: jd ? ((jd.innerText || '').length) : 0,
        buttons: [...new Set(btns)],
        bodyHead: body.slice(0, 400),
        closedHint: /职位已关闭|已停止招聘|该职位已下线|职位不存在|已招满|暂停招聘/.test(body)
      });
    })()
    """


def probe(cdp, eid):
    """返回页面状态 dict，失败返回 None。"""
    cdp.send("Page.navigate", {"url": f"https://www.zhipin.com/job_detail/{eid}.html"})
    for _ in range(16):
        time.sleep(1.2)
        if cdp.val("!!document.querySelector('.job-sec-text')"):
            break
    raw = cdp.val(PageProbe.JS)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def main():
    if not os.path.exists(SRC):
        print(f"❌ 找不到 {SRC}")
        return
    targets = json.load(open(SRC, encoding="utf-8"))
    print(f"投递前清洗：{len(targets)} 条\n")

    try:
        cdp = RelayCDP()
        cdp.ensure_focus()
        print(f"Chrome: {str(cdp.val('location.href'))[:70]}\n")
    except Exception as e:
        print(f"❌ 无法连接 Chrome: {e}")
        return

    keep, drop = [], []
    for i, t in enumerate(targets, 1):
        eid = t.get("eid")
        name = clean_job(t.get("jobName") or "")
        comp = (t.get("company") or "").strip()
        print(f"[{i:2d}/{len(targets)}] {comp[:22]:22s} | {name[:32]}", end=" ")

        p = probe(cdp, eid)
        if p is None:
            print("→ ⛔ 页面读取失败")
            drop.append({**t, "drop_reason": "页面读取失败"})
            time.sleep(1.5)
            continue

        # 1) 是否已关闭
        if p.get("closedHint") or not p.get("buttons"):
            print(f"→ ⛔ 已关闭/无沟通按钮 {p.get('buttons')}")
            drop.append({**t, "drop_reason": "职位已关闭或无法沟通",
                         "drop_detail": str(p.get("buttons"))})
            time.sleep(1.5)
            continue

        # 2) 阿里系
        real_comp = p.get("company") or comp
        if is_ali(real_comp) or is_ali(comp) or is_ali(name):
            print(f"→ ⛔ 阿里系（{real_comp[:18]}）")
            drop.append({**t, "drop_reason": "阿里系", "real_company": real_comp})
            time.sleep(1.5)
            continue

        # 3) 岗位标题是否变了
        page_title = p.get("jobTitle") or ""
        title_changed = False
        if page_title and name:
            a = re.sub(r"[\s（）()【】\[\]、,，·/\\\-_|&+]", "", page_title).lower()
            b = re.sub(r"[\s（）()【】\[\]、,，·/\\\-_|&+]", "", name).lower()
            if a and b and a not in b and b not in a:
                title_changed = True

        # 4) 是否仍是 AI 交付类
        check_text = page_title or name
        is_ai = bool(re.search(AI_MARK, check_text, re.I))
        is_deliver = bool(re.search(DELIVER_MARK, check_text))
        if not (is_ai and is_deliver):
            print(f"→ ⛔ 不再是AI交付类（现标题「{page_title[:22]}」）")
            drop.append({**t, "drop_reason": "不再是AI交付类",
                         "page_title": page_title})
            time.sleep(1.5)
            continue

        # 通过
        note = "标题有变动" if title_changed else "正常"
        print(f"→ ✅ 可投（{note}）")
        keep.append({**t, "real_company": real_comp,
                     "page_title": page_title,
                     "page_buttons": p.get("buttons"),
                     "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        time.sleep(1.5)

    # ---- 自动补位：从备选池补齐到 30 条 ----
    TARGET_N = 30
    REST = os.path.join(HERE, "delivery_rest.json")
    if len(keep) < TARGET_N and os.path.exists(REST):
        rest = json.load(open(REST, encoding="utf-8"))
        used = {k.get("eid") for k in keep} | {d.get("eid") for d in drop}
        cand = [x for x in rest if x.get("eid") not in used
                and (x.get("match_score") or 0) > 0]
        need = TARGET_N - len(keep)
        print()
        print(f"可投 {len(keep)} 条，从备选池补 {need} 条（候补 {len(cand)} 条）")
        for t in cand:
            if len(keep) >= TARGET_N:
                break
            p2 = probe(cdp, t.get("eid"))
            if p2 is None:
                drop.append({**t, "drop_reason": "页面读取失败（补位）"})
                continue
            if p2.get("closedHint") or not p2.get("buttons"):
                drop.append({**t, "drop_reason": "职位已关闭或无法沟通（补位）"})
                time.sleep(1.2)
                continue
            rc = p2.get("company") or t.get("company") or ""
            nm = clean_job(t.get("jobName") or "")
            pt = p2.get("jobTitle") or ""
            if is_ali(rc) or is_ali(nm):
                drop.append({**t, "drop_reason": "阿里系（补位）"})
                time.sleep(1.2)
                continue
            check = pt or nm
            if not (re.search(AI_MARK, check, re.I) and re.search(DELIVER_MARK, check)):
                drop.append({**t, "drop_reason": "不再是AI交付类（补位）"})
                time.sleep(1.2)
                continue
            print(f"   补入: {rc[:22]} | {pt[:30] or nm[:30]}")
            keep.append({**t, "real_company": rc, "page_title": pt,
                         "page_buttons": p2.get("buttons"),
                         "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            time.sleep(1.5)

    json.dump(keep, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(drop, open(DROP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n" + "=" * 78)
    print(f"清洗结果：可投 {len(keep)} 条 | 剔除 {len(drop)} 条")
    print("=" * 78)
    from collections import Counter
    for r, n in Counter(d.get("drop_reason") for d in drop).most_common():
        print(f"  {n:3d}  {r}")
    print(f"\n可投清单 -> {OUT}")
    print(f"剔除明细 -> {DROP}")
    if len(keep) < 20:
        print(f"\n⚠️ 可投数量偏少（{len(keep)} 条），建议从 delivery_rest.json 补充")


if __name__ == "__main__":
    main()
