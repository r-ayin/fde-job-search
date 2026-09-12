# -*- coding: utf-8 -*-
"""从杭州企业**官方招聘页**抓取 AI/交付/解决方案类岗位 JD（不用 BOSS 直聘）。

设计
----
每个公司一个 fetcher 函数，统一产出记录：
    {uid, company, title, jd, jd_len, locations, salary, publishedAt, source}

已实现（可复跑）：
    hikvision   海康威视  talent.hikvision.com   JSON API（无需登录）
    netease     网易(杭州) hr.163.com            JSON API（无需登录）
    jd          京东杭州  zhaopin.jd.com          JSON API（可匿名读取列表/详情）
    insigma     浙大网新  (自定义站点)
    ...

跳过：
    北森 zhiye.com（JS 渲染，另行处理）
    需登录 / 纯 SPA 无内部 API 的站点（见 SKIPPED）

用法
----
    python fetch_misc_jd.py                 # 跑全部已实现
    python fetch_misc_jd.py --only hikvision
    python fetch_misc_jd.py --only hikvision,netease --jd-limit 300
    python fetch_misc_jd.py --list          # 只列目标公司状态
"""
import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "official_misc_jd.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 与 FDE / AI 交付相关的岗位关键词
KEEP = re.compile(
    r"AI|ai|人工智能|大模型|Agent|agent|智能体|算法|机器学习|深度学习|"
    r"NLP|CV|视觉|多模态|RAG|LLM|AIGC|具身智能|"
    r"交付|实施|解决方案|售前|售后|客户成功|项目经理|项目负责|项目管理|"
    r"部署|技术支持|架构师|咨询顾问|数据治理|数据分析|数据开发|数据挖掘|"
    r"产品经理|FDE",
)

# 排除纯美术/建模岗（"模型"易误伤游戏美术）
EXCLUDE = re.compile(
    r"角色模型|场景模型|模型制作|模型师|3D模型|UI设计|视觉设计|"
    r"角色设计|场景设计|原画|插画|动画师|特效师|关卡策划|游戏策划|"
    r"文案策划|数值策划|美术",
)

LOC_HZ = re.compile(r"杭州|浙江")


def title_match(title):
    """标题是否属于 AI/交付/解决方案方向。"""
    t = title or ""
    return bool(KEEP.search(t)) and not EXCLUDE.search(t)


def strip_html(s):
    """HTML -> 纯文本。"""
    if not s:
        return ""
    t = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.I)
    t = re.sub(r"</\s*(p|div|li|tr|h[1-6])\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*li[^>]*>", "· ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = t.replace("\u200b", "").replace("\xa0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def new_session(referer=None):
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    if referer:
        s.headers["Referer"] = referer
    return s


HZ_DISTRICTS = ("余杭区", "西湖区", "滨江区", "萧山区", "拱墅区", "上城区",
                "下城区", "江干区", "临平区", "钱塘区", "富阳区", "临安区",
                "桐庐县", "建德市", "淳安县")
_LOC_EXACT = {"浙江省杭州市", "杭州市", "浙江杭州"}


def is_hz(loc):
    return bool(loc) and bool(LOC_HZ.search(loc))


def norm_loc(loc):
    """规范化单个城市名：杭州及下辖区县统一为 '杭州'，便于下游匹配。"""
    l = (loc or "").strip()
    if not l:
        return None
    if l in _LOC_EXACT:
        return "杭州"
    if any(l == x or l.endswith(x) for x in HZ_DISTRICTS):
        return "杭州"
    return l


def mk(company, uid, title, jd, locations, source, salary="", publishedAt=""):
    jd = (jd or "").strip()
    # 拆分 "北京 / 杭州"、"浙江省杭州市,陕西省西安市" 这类多城市串，并去重
    parts = []
    for y in (locations or []):
        for seg in re.split(r"[,，/、;；]", y or ""):
            n = norm_loc(seg)
            if n:
                parts.append(n)
    seen, locs = set(), []
    for y in parts:
        if y not in seen:
            seen.add(y)
            locs.append(y)
    return {
        "uid": uid,
        "company": company,
        "title": (title or "").strip(),
        "jd": jd,
        "jd_len": len(jd),
        "locations": locs,
        "salary": salary or "",
        "publishedAt": publishedAt or "",
        "source": source,
    }


# ---------------------------------------------------------------------------
# 海康威视  talent.hikvision.com
#   列表: POST /api/ats/official/officialPostPosition/getPostInfoForSys
#   详情: GET  /api/ats/official/officialPostPosition/findAdDetailInfo
#   companyId 从 getConfigInfo 取；无登录、无 token 校验。
# ---------------------------------------------------------------------------
HIK_BASE = "https://talent.hikvision.com"
HIK_CID = "cb143b270be34715885a52ce6934b373"


def fetch_hikvision(limit=0, log=print):
    s = new_session(f"{HIK_BASE}/society/index")
    s.headers["Origin"] = HIK_BASE
    out = []

    # 全量杭州岗位（列表接口支持 locationDesc 过滤）
    jobs, page = [], 1
    while True:
        r = s.post(f"{HIK_BASE}/api/ats/official/officialPostPosition/getPostInfoForSys",
                   json={"pageNum": page, "pageSize": 200, "companyId": "",
                         "locationDesc": "杭州"}, timeout=30)
        d = r.json().get("data") or {}
        lst = d.get("list") or []
        jobs += lst
        total = d.get("total") or 0
        if not lst or len(jobs) >= total:
            break
        page += 1
        time.sleep(0.3)

    log(f"   杭州在招岗位总数: {len(jobs)}")
    cand = [j for j in jobs if title_match(j.get("postName")) and is_hz(j.get("locationDesc"))]
    log(f"   AI/交付/解决方案 相关: {len(cand)}")
    if limit:
        cand = cand[:limit]

    for i, j in enumerate(cand, 1):
        sid = j.get("postSecureId")
        try:
            r = s.get(f"{HIK_BASE}/api/ats/official/officialPostPosition/findAdDetailInfo",
                      params={"adIdStr": sid, "companyId": HIK_CID}, timeout=30)
            ad = ((r.json() or {}).get("data") or {}).get("ad") or {}
        except Exception as e:
            log(f"      x [{i}] {j.get('postName')} 详情失败 {e}")
            time.sleep(0.6)
            continue
        parts = []
        if ad.get("postDesc"):
            parts.append("岗位职责：\n" + strip_html(ad["postDesc"]))
        if ad.get("qualifications"):
            parts.append("任职要求：\n" + strip_html(ad["qualifications"]))
        jd = "\n\n".join(parts)
        if len(jd) < 30:
            time.sleep(0.4)
            continue
        loc = ad.get("workPlace") or ad.get("locationDesc") or j.get("locationDesc")
        out.append(mk(
            "海康威视", f"official:hikvision:{sid}", ad.get("postName") or j.get("postName"),
            jd, [loc], f"{HIK_BASE}/society/position?postId={sid}",
            salary=ad.get("salary") or "",
            publishedAt=ad.get("createdon") or j.get("createTime") or "",
        ))
        if i % 20 == 0:
            log(f"      ... {i}/{len(cand)}")
        time.sleep(0.4)
    log(f"   ✓ 海康威视 JD {len(out)} 条")
    return out


# ---------------------------------------------------------------------------
# 网易 hr.163.com
#   列表: POST /api/hr163/position/queryPage  {currentPage,pageSize}
#         —— 列表响应已含完整 JD（description + requirement），无需详情接口
#   详情: GET  /api/hr163/position/query?id=<id>   （字段与列表一致）
#   头部: language / authType / x-ehr-uuid，匿名可读，无需登录。
# ---------------------------------------------------------------------------
NE_BASE = "https://hr.163.com"


def fetch_netease(limit=0, log=print):
    import uuid
    s = new_session(NE_BASE + "/job-list.html")
    s.headers.update({
        "Content-Type": "application/json",
        "Origin": NE_BASE,
        "language": "zh",
        "authType": "ursAuth",
        "x-ehr-uuid": str(uuid.uuid4()),
    })
    jobs, page = [], 1
    while True:
        r = s.post(f"{NE_BASE}/api/hr163/position/queryPage",
                   json={"currentPage": page, "pageSize": 200}, timeout=40)
        d = (r.json() or {}).get("data") or {}
        lst = d.get("list") or []
        jobs += lst
        total = d.get("total") or 0
        if not lst or len(jobs) >= total:
            break
        page += 1
        time.sleep(0.3)

    log(f"   全站在招岗位: {len(jobs)}")
    hz = [j for j in jobs
          if any("杭州" in (w or "") for w in (j.get("workPlaceNameList") or []))]
    log(f"   杭州岗位: {len(hz)}")
    cand = [j for j in hz if title_match(j.get("name"))]
    log(f"   AI/交付/解决方案 相关: {len(cand)}")
    if limit:
        cand = cand[:limit]

    out = []
    for j in cand:
        parts = []
        if j.get("description"):
            parts.append("岗位职责：\n" + strip_html(j["description"]))
        if j.get("requirement"):
            parts.append("任职要求：\n" + strip_html(j["requirement"]))
        jd = "\n\n".join(parts)
        if len(jd) < 30:
            continue
        locs = [w for w in (j.get("workPlaceNameList") or []) if w]
        out.append(mk(
            "网易（杭州研究院）", f"official:netease:{j.get('id')}", j.get("name"),
            jd, locs or ["杭州"], f"{NE_BASE}/job-detail.html?id={j.get('id')}",
            salary="", publishedAt="",
        ))
    log(f"   ✓ 网易 JD {len(out)} 条")
    return out


# ---------------------------------------------------------------------------
# 帆软软件 join.fanruan.com
#   列表: POST /social  (表单 filter=1&page=N&w=)  -> 纯 JSON
#         {list:[{id,job_name,apartment,job_type,base,salary,mode,duty,description}],
#          dataTotal,pageTotal}
#   base 字段含城市（逗号分隔），筛 "杭州" 即得杭州岗位。
# ---------------------------------------------------------------------------
FR_BASE = "https://join.fanruan.com"


def fetch_fanruan(limit=0, log=print):
    s = new_session(FR_BASE + "/social")
    s.headers["X-Requested-With"] = "XMLHttpRequest"

    jobs, page = [], 1
    while True:
        r = s.post(f"{FR_BASE}/social", data={"filter": 1, "page": page, "w": ""}, timeout=30)
        try:
            d = json.loads(r.text)
        except Exception:
            break
        lst = d.get("list") or []
        jobs += lst
        if not lst:
            break
        try:
            total = int(d.get("dataTotal") or 0)
        except Exception:
            total = 0
        if total and len(jobs) >= total:
            break
        page += 1
        time.sleep(0.3)

    log(f"   全站在招岗位: {len(jobs)}")
    cand = [j for j in jobs if is_hz(j.get("base"))]
    log(f"   含杭州岗位: {len(cand)}")
    cand = [j for j in cand if title_match(j.get("job_name"))]
    log(f"   AI/交付/解决方案 相关: {len(cand)}")
    if limit:
        cand = cand[:limit]

    out = []
    for j in cand:
        parts = []
        if j.get("duty"):
            parts.append("岗位职责：\n" + strip_html(j["duty"]))
        if j.get("description"):
            parts.append("岗位要求：\n" + strip_html(j["description"]))
        jd = "\n\n".join(parts)
        if len(jd) < 30:
            continue
        jid = j.get("id")
        locs = [x.strip() for x in re.split(r"[,，]", j.get("base") or "") if x.strip()]
        out.append(mk(
            "帆软软件", f"official:fanruan:{jid}", j.get("job_name"), jd,
            locs or ["杭州"], f"{FR_BASE}/social/detail?id={jid}",
            salary=j.get("salary") or "",
        ))
    log(f"   ✓ 帆软 JD {len(out)} 条")
    return out


# ---------------------------------------------------------------------------
# 泛微网络 weaver.com.cn
#   静态 HTML：/recruit/job1..job6.html?link=1..5 （每个?link 对应一个岗位）
#   注意：泛微 JD 为**全国通用**，页面不标城市；杭州为其华东分支覆盖城市之一。
# ---------------------------------------------------------------------------
WV_BASE = "https://www.weaver.com.cn"


def fetch_weaver(limit=0, log=print):
    s = new_session(WV_BASE + "/recruit/social.html")
    out = []
    # 只取交付/解决方案/项目相关页（job1 营销、job2 项目、job3 客服、job5 产品）
    for pg in (1, 2, 3, 5):
        for lk in range(1, 6):
            url = f"{WV_BASE}/recruit/job{pg}.html?link={lk}"
            try:
                r = s.get(url, timeout=25)
                raw = r.content.decode("utf-8", errors="replace")
            except Exception:
                continue
            body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
            body = re.sub(r"<[^>]+>", "\n", body)
            body = html.unescape(body)
            body = re.sub(r"[ \t]+", " ", body)
            body = re.sub(r"\n{2,}", "\n", body).strip()
            # 岗位名在 "具体职位 ... 岗位名 岗位职责：" 之间；用 JD 起点定位
            i = body.find("岗位职责")
            if i < 0:
                i = body.find("职位描述")
            if i < 0:
                continue
            head = body[max(0, i - 400):i]
            names = [x.strip() for x in head.split("\n") if 2 <= len(x.strip()) <= 22]
            title = names[-1] if names else f"泛微-job{pg}-{lk}"
            jd = body[i:i + 3500]
            # 截到"立即申请"
            for stop in ("立即申请", "泛微的加入方式"):
                k = jd.find(stop)
                if k > 200:
                    jd = jd[:k]
                    break
            jd = jd.strip()
            if not title_match(title) and not title_match(jd[:200]):
                continue
            if len(jd) < 200:
                continue
            out.append(mk(
                "泛微网络", f"official:weaver:{pg}-{lk}", title, jd,
                ["杭州"], url,
            ))
    # 去重（同名岗位可能出现在多个页面）
    seen, uniq = set(), []
    for r in out:
        if r["title"] in seen:
            continue
        seen.add(r["title"])
        uniq.append(r)
    log(f"   ✓ 泛微 JD {len(uniq)} 条（JD 为全国通用，未标城市）")
    return uniq[:limit] if limit else uniq


# ---------------------------------------------------------------------------
# 袋鼠云 dtstack.com —— 官网招聘跳转 MokaHR
#   app.mokahr.com/social-recruitment/dtstack/45467
#   列表: POST /api/outer/ats-apply/website/jobs      （AES-CBC 加密响应）
#   详情: POST /api/outer/ats-apply/website/job
# ---------------------------------------------------------------------------
def fetch_dtstack(limit=0, log=print):
    import base64
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    org, sid = "dtstack", "45467"
    base = f"https://app.mokahr.com/social-recruitment/{org}/{sid}"
    s = new_session(base)
    s.headers["Content-Type"] = "application/json"
    r = s.get(base, timeout=30)
    m = re.search(r'id="init-data"[^>]*value="([^"]*)"', r.text)
    iv = None
    if m:
        try:
            iv = json.loads(html.unescape(m.group(1))).get("aesIv")
        except Exception:
            pass
    if not iv:
        log("   x 无法获取 Moka aesIv，跳过")
        return []

    def post(path, body):
        rr = s.post(f"https://app.mokahr.com/api/outer/ats-apply/website/{path}",
                    json=body, headers={"Referer": base}, timeout=30)
        d = rr.json()
        if not d.get("necromancer") or not d.get("data"):
            return None
        c = AES.new(d["necromancer"].encode(), AES.MODE_CBC, iv.encode())
        return json.loads(unpad(c.decrypt(base64.b64decode(d["data"])), AES.block_size).decode())

    jobs = []
    off = 0
    while off < 500:
        dec = post("jobs", {"orgId": org, "siteId": sid, "limit": 50, "offset": off,
                            "needStat": True, "site": "social"})
        if not dec:
            break
        inner = dec.get("data") if isinstance(dec.get("data"), dict) else dec
        lst = (inner or {}).get("jobs") or []
        if not lst:
            break
        jobs += lst
        if len(lst) < 50:
            break
        off += 50
        time.sleep(0.35)

    log(f"   Moka 岗位总数: {len(jobs)}")

    def in_hz(j):
        locs = j.get("locations") or []
        if not locs:
            return True
        for l in locs:
            cn = (l.get("cityName") or "") + (l.get("provinceName") or "")
            if "杭州" in cn or "浙江" in cn:
                return True
        return False

    cand = [j for j in jobs if title_match(j.get("title")) and in_hz(j)]
    log(f"   AI/交付/解决方案 相关且杭州: {len(cand)}")
    if limit:
        cand = cand[:limit]

    out = []
    for j in cand:
        d = post("job", {"orgId": org, "siteId": sid, "jobId": j.get("id"), "site": "social"})
        dd = d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), dict) else (d or {})
        jd = strip_html(dd.get("jobDescription") or "")
        if len(jd) < 30:
            time.sleep(0.5)
            continue
        locs = [l.get("cityName") or "" for l in (j.get("locations") or []) if l.get("cityName")]
        out.append(mk(
            "袋鼠云", f"official:dtstack:{j.get('id')}", dd.get("title") or j.get("title"),
            jd, locs or ["杭州"], base + "#/job/" + str(j.get("id")),
            publishedAt=(j.get("publishedAt") or ""),
        ))
        time.sleep(0.5)
    log(f"   ✓ 袋鼠云 JD {len(out)} 条")
    return out


# ---------------------------------------------------------------------------
# 彩讯股份 richinfo.cn
#   列表: GET /api/job/public/positions?page=1&pageSize=100
#   详情: GET /api/job/public/position/<id>   （含 responsibility/requirement/benefits）
#   匿名可读。workLocation 为 "北京 / 深圳 / ... /杭州" 多城市字符串。
# ---------------------------------------------------------------------------
RI_BASE = "https://www.richinfo.cn"


def fetch_richinfo(limit=0, log=print):
    s = new_session(RI_BASE + "/jobs/social")
    r = s.get(f"{RI_BASE}/api/job/public/positions",
              params={"page": 1, "pageSize": 200}, timeout=30)
    jobs = ((r.json() or {}).get("data") or {}).get("list") or []
    log(f"   全站在招岗位: {len(jobs)}")
    hz = [j for j in jobs if is_hz(j.get("workLocation"))]
    log(f"   含杭州岗位: {len(hz)}")
    cand = [j for j in hz if title_match(j.get("title"))]
    log(f"   AI/交付/解决方案 相关: {len(cand)}")
    if limit:
        cand = cand[:limit]

    out = []
    for j in cand:
        try:
            d = (s.get(f"{RI_BASE}/api/job/public/position/{j.get('id')}",
                       timeout=30).json() or {}).get("data") or {}
        except Exception:
            d = j
        parts = []
        for label, key in (("岗位职责", "responsibility"), ("任职要求", "requirement")):
            if d.get(key):
                parts.append(f"{label}：\n" + strip_html(d[key]))
        if not parts and d.get("description"):
            parts.append("岗位描述：\n" + strip_html(d["description"]))
        jd = "\n\n".join(parts)
        if len(jd) < 30:
            time.sleep(0.4)
            continue
        locs = [x.strip() for x in re.split(r"[/、,，]", j.get("workLocation") or "") if x.strip()]
        out.append(mk(
            "彩讯股份", f"official:richinfo:{j.get('id')}", j.get("title"), jd,
            locs or ["杭州"], f"{RI_BASE}/jobs/social",
            salary=j.get("salaryRange") or "",
            publishedAt=(j.get("publishTime") or "")[:10],
        ))
        time.sleep(0.4)
    log(f"   ✓ 彩讯 JD {len(out)} 条")
    return out


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------
FETCHERS = {
    "hikvision": ("海康威视", fetch_hikvision),
    "netease": ("网易（杭州研究院）", fetch_netease),
    "fanruan": ("帆软软件", fetch_fanruan),
    "weaver": ("泛微网络", fetch_weaver),
    "dtstack": ("袋鼠云", fetch_dtstack),
    "richinfo": ("彩讯股份", fetch_richinfo),
}

# 探测结论：无可匿名抓取的官方 JD 接口（诚实记录）
SKIPPED = {
    "实在智能": "官网无招聘入口，未挂任何 ATS（招聘应在 BOSS/猎聘等第三方）",
    "群核科技(酷家乐)": "hr.kujiale.com 为重定向的纯 SPA（it-system-app-kjl-recruit），无公开 JSON API，需浏览器",
    "趣链科技": "官网无招聘入口链接；job.hyperchain.cn 无法连接",
    "影刀RPA": "官网跳 ying-dao.jobs.feishu.cn(飞书招聘)，该租户匿名接口返回空/无可用缓存",
    "数梦工场": "站点仅 877 字节 umi 空壳；HTTPS 证书异常；无招聘可抓",
    "浙大网新": "官网无招聘入口/无 JD 列表",
    "彩讯股份": "richinfo.cn/jobs 为 Nuxt SSR，__NUXT_DATA__ 无岗位数据（前端再请求），需浏览器或找私有 API",
    "得力集团": "官网无招聘入口（nbdeli.com 无招聘页）",
    "新中大科技": "官网招聘跳北森 zhiye.com（JS 渲染，另由专门 agent 处理）",
    "天娱数科": "官网无招聘入口",
    "共达地": "www.gongdadi.com TLS 握手失败 / http 502，站点不可达",
    "斑头雁智能": "官网 JS 只有博客/预约接口，无招聘接口（招聘应在第三方）",
    "京东(杭州)": "zhaopin.jd.com API 可匿名读（job_list），但全站 1792 个岗位中杭州=0（杭州岗位走 campus/内部，未公开）",
    "快手(杭州)": "zhaopin.kuaishou.cn 为 React SPA，main.js 无内部 API（走独立网关），需浏览器",
    "泛微-补充": "已抓取，但见 note：JD 为全国通用未标城市",
    "北森系(zhiye.com)": "JS 渲染，按要求跳过，另由专门 agent 处理",
}


def load_existing():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT, encoding="utf-8"))
        except Exception:
            return []
    return []


def save(records):
    """按 uid 去重后写盘。"""
    uniq = {}
    for r in records:
        if r.get("uid"):
            uniq[r["uid"]] = r
    rows = list(uniq.values())
    rows.sort(key=lambda r: (r["company"], r["title"]))
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔的 fetcher 名")
    ap.add_argument("--jd-limit", type=int, default=0, help="每家最多抓几条 JD")
    ap.add_argument("--list", action="store_true", help="只打印注册表")
    args = ap.parse_args()

    if args.list:
        print("已实现:")
        for k, (name, _) in FETCHERS.items():
            print(f"  {k:12s} {name}")
        print("\n待探测/跳过:")
        for k, v in SKIPPED.items():
            print(f"  {k:16s} {v}")
        return

    names = [x.strip() for x in args.only.split(",") if x.strip()] or list(FETCHERS)
    records = load_existing()
    before = len(records)

    for n in names:
        if n not in FETCHERS:
            print(f"!! 未知 fetcher: {n}")
            continue
        comp, fn = FETCHERS[n]
        print(f"\n[{comp}] 开始抓取 ...")
        try:
            got = fn(limit=args.jd_limit)
        except Exception as e:
            print(f"   !! {comp} 抓取异常: {e}")
            continue
        records = [r for r in records if not r["uid"].startswith(f"official:{n}:")]
        records += got
        save(records)  # 每家公司落盘，防中断丢数据

    rows = save(records)
    ok = [r for r in rows if r["jd_len"] > 50]
    print(f"\n{'=' * 72}")
    print(f"输出: {OUT}")
    print(f"本次新增前 {before} 条 -> 现共 {len(rows)} 条，其中 JD 正文>50字: {len(ok)}")
    from collections import Counter
    for c, n in Counter(r["company"] for r in ok).most_common():
        print(f"   {c}: {n} 条")
    print("=" * 72)


if __name__ == "__main__":
    main()
