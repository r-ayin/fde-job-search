# -*- coding: utf-8 -*-
"""
北森（zhiye.com）招聘门户 JD 抓取脚本
=====================================

已探明的真实 API（北森 ux-recruitment-portal-2022 门户）
  POST https://<org>.zhiye.com/api/Jobad/GetJobAdPageList
       Body(JSON): {"PageIndex":0,"PageSize":1000,"Category":["1"],"DisplayFields":["LocId"]}
       返回 Data[]，其中 JobAdName / Duty / Require / LocNames / ChangeDate 均为明文，Duty 即 JD 职责正文。

  说明：
    - 旧猜测的 /api/social/job/list 返回的是 HTML 壳，不是接口。
    - /api/JobAd/GetJobAdInfo 需要额外签名/cookie，实测始终返回 500「参数错误」；
      但 GetJobAdPageList 已直接带出完整 Duty/Require，无需再调详情接口。
    - Category: "1"=社会招聘, "2"=校园招聘, "3"=实习生。不传则返回全部。
    - 本站点仅抓社会招聘（与任务给出的 /social 入口一致）；如需校招/实习，
      把 collect() 里的 category="1" 改为 "2" / "3" 或不传。

恒生电子（hundsun.zhiye.com）例外：
    - 该域仍使用北森旧版 CMS 门户，/api/... 一律 302 到 /404。
    - 校招子站 campus.hundsun.com 用新版 SPA，但其 API 只覆盖校招/实习；
      且「社会招聘」导航直接外链 51job（https://hundsun.51job.com/），
      故此处在北森系统内拿不到恒生的社招 JD。

用法：
    python fetch_beisen.py                # 抓取并写入 beisen_jd.json
    python fetch_beisen.py --debug        # 打印每家公司的接口返回概况
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beisen_jd.json")

# org 域名 -> 公司名。北森租户 ID 见各站 HTML 里的 BSGlobal.tenantInfo.Id
COMPANIES = [
    ("h3c", "新华三"),
    ("youzan", "有赞"),
    ("arcvideo", "当虹科技"),
    ("dahua", "大华股份"),
    ("dptech", "迪普科技"),
    ("hundsun", "恒生电子"),
]

# 杭州关键词（LocNames 形如 "浙江省·杭州市"）
CITY_KEYWORD = "杭州"

# 目标岗位关键词：AI / 交付 / 实施 / 解决方案 / 售前 / 客户成功 / 项目经理 / 大模型 / Agent
TITLE_KEYWORDS = [
    "AI", "人工智能", "大模型", "大语言", "模型", "算法", "智能", "智算",
    "Agent", "agent", "LLM", "微调", "推理",
    "交付", "实施", "解决方案", "售前", "售后", "客户成功", "技术支持",
    "服务工程师", "服务产品", "服务拓展",
    "项目经理", "项目管理", "咨询", "架构师", "数据架构",
]

# 明显不相关岗位的排除词（避免「顾问/服务」等宽泛词带入销售、职能岗）
TITLE_EXCLUDE = [
    "HRBP", "法务", "会计", "财务", "税务", "招聘", "行政", "秘书", "薪酬",
    "审计", "文员", "普工", "仓储", "资料员", "培训", "土建", "基建", "弱电",
    "造价", "安装工程师", "机械", "焊接", "质量检验", "采购", "商务", "品牌",
    "文案", "记者", "编辑", "招商", "团长", "客服", "运营", "设计师", "销售",
    "司机", "厨师", "保安", "保洁", "营销顾问",
]

API_PATH = "/api/Jobad/GetJobAdPageList"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Requested-With": "xmlhttprequest",
    "langType": "zh_CN",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


def strip_html(text):
    """北森接口返回的多为纯文本，这里兜底去掉可能的 HTML 标签。"""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_page_list(org, category=None, page_size=1000, page_index=0):
    """调用北森岗位列表接口，返回 Data 列表。"""
    url = "https://%s.zhiye.com%s" % (org, API_PATH)
    body = {"PageIndex": page_index, "PageSize": page_size,
            "DisplayFields": ["LocId", "Category"]}
    if category is not None:
        body["Category"] = [category]
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", "ignore")
    data = json.loads(raw)
    if data.get("Code") != 200:
        raise RuntimeError("接口返回 Code=%s Message=%s" % (data.get("Code"), data.get("Message")))
    return data.get("Data") or []


def in_hangzhou(item):
    locs = item.get("LocNames") or []
    return any(CITY_KEYWORD in (l or "") for l in locs)


def title_matches(title):
    t = title or ""
    if any(e in t for e in TITLE_EXCLUDE):
        return False
    return any(k in t for k in TITLE_KEYWORDS)


def norm_date(change_date):
    """ChangeDate -> YYYY-MM-DD。北森的 PostDate 常为 0001-01-01，故用 ChangeDate。"""
    if not change_date:
        return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", change_date)
    return m.group(1) if m else ""


def collect(debug=False):
    results = []
    summary = []

    for org, company in COMPANIES:
        try:
            items = fetch_page_list(org, category="1")  # 社会招聘
        except Exception as e:
            summary.append((company, org, "ERROR", str(e)))
            if debug:
                print("[%s] %s 抓取失败: %s" % (company, org, e))
            continue

        hz = [i for i in items if in_hangzhou(i)]
        picked = [i for i in hz if title_matches(i.get("JobAdName"))]
        summary.append((company, org, "OK", "总%d条 / 杭州%d条 / 命中关键词%d条"
                        % (len(items), len(hz), len(picked))))
        if debug:
            print("[%s] %s" % (company, summary[-1][3]))

        for i in picked:
            duty = strip_html(i.get("Duty"))
            require = strip_html(i.get("Require"))
            jd = duty
            if require:
                jd = (duty + "\n\n【任职要求】\n" + require).strip()
            if not jd:
                continue
            job_id = i.get("JobAdId")
            results.append({
                "uid": "beisen:%s:%s" % (org, job_id),
                "company": company,
                "title": i.get("JobAdName") or "",
                "jd": jd,
                "jd_len": len(jd),
                "locations": i.get("LocNames") or [],
                "publishedAt": norm_date(i.get("ChangeDate")),
                "source": "https://%s.zhiye.com%s" % (org, API_PATH),
            })

    return results, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true", help="打印各站点抓取概况")
    ap.add_argument("--out", default=OUT_PATH, help="输出 JSON 路径")
    args = ap.parse_args()

    results, summary = collect(debug=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n===== 抓取汇总 =====")
    for company, org, status, msg in summary:
        print("  %-8s %-14s %s  %s" % (company, org, status, msg))
    print("\n共写入 %d 条 JD -> %s" % (len(results), args.out))
    if not results:
        print("未抓到任何 JD，请检查网络或接口是否变更。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
