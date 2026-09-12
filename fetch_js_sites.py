# -*- coding: utf-8 -*-
"""抓取酷家乐 + 快手的官网 JD（两家都有干净的 JSON API）。

酷家乐：GET https://ehr-headcount.qunhequnhe.com/api/v1/moka/job/search?limit=100&offset=0&mode=social
快手：  GET https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple?pageNum=1&pageSize=10&positionNatureCode=C001&recruitProject=social
"""
import json
import os
import re
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                  "Accept-Language": "zh-CN,zh;q=0.9"})

OUT = os.path.join(HERE, "js_site_jd.json")


def strip_html(s):
    if not s:
        return ""
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", s, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    import html as _h
    t = _h.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def fetch_kujiale():
    """群核科技（酷家乐）：一次拿全部 53 个岗位含 JD。"""
    url = "https://ehr-headcount.qunhequnhe.com/api/v1/moka/job/search"
    r = S.get(url, params={"limit": 200, "offset": 0, "mode": "social"},
              headers={"Referer": "https://www.kujiale.com/"}, timeout=30)
    d = r.json()
    jobs = (d.get("d") or {}).get("jobs") or []
    out = []
    for j in jobs:
        locs = []
        for l in (j.get("locations") or []):
            s = "".join(str(l.get(k) or "") for k in ("country", "province", "city", "address"))
            if s:
                locs.append(s)
        out.append({
            "uid": f"kujiale:{j.get('jobId')}",
            "company": "群核科技（酷家乐）",
            "title": (j.get("title") or "").strip(),
            "jd": strip_html(j.get("description") or ""),
            "locations": locs,
            "commitment": j.get("commitment"),
            "source": url,
        })
    return out


def fetch_kuaishou(pages=12):
    """快手：分页 API。"""
    base = "https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple"
    out, seen = [], set()
    for p in range(1, pages + 1):
        try:
            r = S.get(base, params={
                "pageNum": p, "pageSize": 50,
                "positionNatureCode": "C001", "recruitProject": "social"},
                headers={"Referer": "https://zhaopin.kuaishou.cn/"}, timeout=30)
            d = r.json()
        except Exception as e:
            print(f"   快手第{p}页失败: {str(e)[:60]}")
            break
        arr = (d.get("data") or {}).get("list") or d.get("result") or []
        if isinstance(arr, dict):
            arr = arr.get("list") or []
        if not arr:
            break
        for j in arr:
            jid = j.get("id") or j.get("positionId") or j.get("code")
            if not jid or jid in seen:
                continue
            seen.add(jid)
            # 地点字段可能多种命名
            loc = j.get("workLocation") or j.get("workLocationName") or ""
            if isinstance(loc, list):
                loc = "/".join(str(x) for x in loc)
            out.append({
                "uid": f"kuaishou:{jid}",
                "company": "快手",
                "title": (j.get("positionName") or j.get("name") or "").strip(),
                "jd": strip_html(j.get("description") or j.get("positionDescription") or ""),
                "locations": [str(loc)],
                "commitment": j.get("positionNature") or "",
                "source": base,
            })
        print(f"   快手第{p}页: {len(arr)} 条，累计 {len(out)}")
        if len(arr) < 50:
            break
        time.sleep(0.6)
    return out


def main():
    results = []

    print("■ 群核科技（酷家乐）")
    try:
        k = fetch_kujiale()
        print(f"   拿到 {len(k)} 个岗位")
        hz = [x for x in k if any("杭州" in l for l in x["locations"])]
        print(f"   杭州: {len(hz)} 个")
        results.extend(k)
    except Exception as e:
        print(f"   × {str(e)[:100]}")

    print("\n■ 快手")
    try:
        ks = fetch_kuaishou()
        print(f"   拿到 {len(ks)} 个岗位")
        hz = [x for x in ks if any("杭州" in l for l in x["locations"])]
        print(f"   杭州: {len(hz)} 个")
        for x in hz[:20]:
            print(f"      {x['title'][:44]:44s} | {x['locations']}")
        results.extend(ks)
    except Exception as e:
        print(f"   × {str(e)[:100]}")

    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = [x for x in results if len(x["jd"]) > 50]
    print(f"\n合计 {len(results)} 条，有 JD 正文 {len(ok)} 条 -> {OUT}")


if __name__ == "__main__":
    main()
