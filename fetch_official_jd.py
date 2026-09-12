# -*- coding: utf-8 -*-
"""从企业官网抓取 JD（不用 BOSS）。

覆盖：
  1. MokaHR 系统（app.mokahr.com）：列表 + 详情 API，响应 AES 加密，可批量
  2. 北森 zhiye.com：JS 渲染，走其内部 API
  3. 其他公司官网：逐个定制（海康、网易、帆软等）

用法：
  python fetch_official_jd.py --moka         只抓 MokaHR 公司
  python fetch_official_jd.py --moka --limit 11
"""
import argparse
import base64
import html
import json
import os
import re
import sys
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

S = requests.Session()
S.headers.update({"User-Agent": UA,
                  "Accept": "application/json, text/plain, */*",
                  "Accept-Language": "zh-CN,zh;q=0.9"})


def decrypt(b64, key, iv):
    ct = base64.b64decode(b64)
    c = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    return json.loads(unpad(c.decrypt(ct), AES.block_size).decode("utf-8"))


class Moka:
    """MokaHR 招聘系统客户端。"""

    def __init__(self, org, site_id):
        self.org, self.site_id = org, str(site_id)
        self.base = f"https://app.mokahr.com/social-recruitment/{org}/{site_id}"
        self.iv = None

    def load(self):
        r = S.get(self.base, timeout=30, allow_redirects=True)
        m = re.search(r'id="init-data"[^>]*value="([^"]*)"', r.text)
        if m:
            try:
                self.iv = json.loads(html.unescape(m.group(1))).get("aesIv")
            except Exception:
                pass
        return bool(self.iv)

    def _post(self, path, body):
        r = S.post(f"https://app.mokahr.com/api/outer/ats-apply/website/{path}",
                   json=body, headers={"Referer": self.base,
                                       "Content-Type": "application/json"}, timeout=30)
        d = r.json()
        if not d.get("necromancer") or not d.get("data"):
            return None
        return decrypt(d["data"], d["necromancer"], self.iv)

    def list_jobs(self, keyword="", limit=50, offset=0):
        dec = self._post("jobs", {"orgId": self.org, "siteId": self.site_id,
                                  "limit": limit, "offset": offset,
                                  "needStat": True, "site": "social",
                                  **({"keyword": keyword} if keyword else {})})
        if not dec:
            return []
        inner = dec.get("data") if isinstance(dec.get("data"), dict) else dec
        return (inner or {}).get("jobs") or []

    def detail(self, job_id):
        dec = self._post("job", {"orgId": self.org, "siteId": self.site_id,
                                 "jobId": job_id, "site": "social"})
        if not dec:
            return None
        return dec.get("data") if isinstance(dec.get("data"), dict) else dec

    def collect_all(self, cap=1500):
        """抓全量岗位（不传关键词）。

        注意：MokaHR 传 keyword 会**漏岗位**——传 "AI" 只回 2 个，
        而不传关键词能看到全部并本地筛。所以必须分页抓全量再本地过滤。
        """
        seen, out = set(), []
        off = 0
        while off < cap:
            js = self.list_jobs(keyword="", limit=50, offset=off)
            if not js:
                break
            for j in js:
                if j.get("id") in seen:
                    continue
                seen.add(j["id"])
                out.append(j)
            if len(js) < 50:
                break
            off += 50
            time.sleep(0.35)
        return out


# 目标公司 -> Moka 站点
MOKA_SITES = {
    "商米科技": ("sunmi", "118589"),
    "信雅达": ("sunyard", "43202"),
    "云从科技": ("cloudwalk", "4871"),
    "吉利控股集团": ("geely", "96123"),
    "税友软件": ("servyou", "42864"),
    "极智嘉 Geek+": ("geekplus", "5030"),
    "涂鸦智能": ("tuya", "3236"),
    "微医": ("wedoctor", "41066"),
    "中控技术": ("supcon", "78261"),
    "月之暗面（Moonshot AI）": ("moonshot", "148506"),
    "第四范式": ("4paradigm", "102013"),
}

# 关注的关键词（AI 交付/解决方案向）
KEYWORDS = ["AI", "交付", "实施", "解决方案", "售前", "Agent", "大模型",
            "智能体", "客户成功", "项目经理", "部署"]


def strip_html(s):
    if not s:
        return ""
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", s, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moka", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="最多抓几家公司")
    ap.add_argument("--jd-limit", type=int, default=0, help="每家公司最多抓几条 JD")
    ap.add_argument("--out", default="official_jd.json")
    args = ap.parse_args()

    out_path = os.path.join(HERE, args.out)
    results = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else []
    done = {r.get("uid") for r in results}

    sites = list(MOKA_SITES.items())
    if args.limit:
        sites = sites[:args.limit]
    if not args.moka:
        print("当前仅实现 --moka；其他官网后续补充")
        return

    for i, (comp, (org, sid)) in enumerate(sites, 1):
        print(f"\n[{i}/{len(sites)}] {comp}（{org}/{sid}）")
        m = Moka(org, sid)
        if not m.load():
            print("   × 无法获取 aesIv")
            continue
        print(f"   aesIv OK")

        jobs = m.collect_all(cap=1500)
        print(f"   岗位列表: {len(jobs)} 个")

        # 筛选 AI 交付/解决方案相关的
        KEEP = re.compile(r"AI|ai|大模型|模型|Agent|agent|智能体|算法|交付|实施|"
                          r"解决方案|售前|客户成功|项目经理|部署", re.I)
        cand = [j for j in jobs if KEEP.search(j.get("title") or "")]
        # 只看杭州或未标城市的
        def in_hz(j):
            locs = j.get("locations") or []
            if not locs:
                return True
            for l in locs:
                cn = (l.get("cityName") or "") + (l.get("provinceName") or "")
                if "杭州" in cn or "浙江" in cn:
                    return True
            return False
        cand = [j for j in cand if in_hz(j)]
        print(f"   AI/交付相关且杭州: {len(cand)} 个")
        if args.jd_limit:
            cand = cand[:args.jd_limit]

        for j in cand:
            uid = f"moka:{org}:{j.get('id')}"
            if uid in done:
                continue
            d = m.detail(j["id"])
            if not d:
                print(f"      × {j.get('title')} 详情失败")
                time.sleep(0.8)
                continue
            jd = strip_html(d.get("jobDescription") or "")
            locs = [(l.get("cityName") or "") for l in (j.get("locations") or [])]
            results.append({
                "uid": uid,
                "company": comp,
                "title": d.get("title") or j.get("title"),
                "jd": jd,
                "jd_len": len(jd),
                "commitment": d.get("commitment") or j.get("commitment"),
                "locations": locs,
                "mjCode": j.get("mjCode"),
                "publishedAt": j.get("publishedAt"),
                "source": "moka:" + m.base,
            })
            done.add(uid)
            print(f"      ✓ {j.get('title')[:34]:34s} JD {len(jd)} 字 {locs}")
            time.sleep(0.6)

        json.dump(results, open(out_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    ok = [r for r in results if r["jd_len"] > 50]
    print(f"\n{'=' * 70}")
    print(f"完成：{len(results)} 条记录，其中有 JD 正文 {len(ok)} 条")
    print(f"输出：{out_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
