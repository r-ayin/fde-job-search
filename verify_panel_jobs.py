# -*- coding: utf-8 -*-
"""核对面板真实岗位（只读，零发送）。

背景：目标文件 send_targets.json 的 jobName 由 eid 匹配 JD 得到，
      存在匹配错误（如奥星集团实际是"AI解决方案经理（工业流程行业）"，
      目标文件写的是"FDE（前沿部署工程师）"）。

做法：逐条定位会话 -> 等面板稳定 -> 记录**面板真实岗位名** + 会话头部身份。
      全程只读，不写入、不发送。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from send_paced import RelayCDP, Sender, clean_job  # noqa: E402


def main():
    cdp = RelayCDP()
    s = Sender(cdp, dry_run=True, skip_open=True)
    targets = json.load(open("send_ready_fde.json", encoding="utf-8"))

    out = []
    for i, t in enumerate(targets, 1):
        brand = t.get("brand") or ""
        hr = t.get("hr") or ""
        file_job = clean_job(t.get("jobName") or "")
        print(f"\n[{i}/{len(targets)}] {brand} | {hr} | 文件岗位「{file_job}」")

        ok, note = s.open_in_list(brand, hr, file_job)
        if not ok:
            print(f"   ✗ 未定位: {note}")
            out.append({**t, "panel_job": None, "conv": None, "match": None,
                        "locate": note})
            continue

        panel_job, st = s.await_panel(brand, hr=hr, need=3, timeout_s=15)
        conv = (st.get("conv") or "").replace("\n", " / ")
        match = s.job_matches(file_job, panel_job or "")
        print(f"   会话头部: {conv}")
        print(f"   面板岗位: 「{panel_job}」")
        print(f"   与文件一致: {'✅ 是' if match else '❌ 否'}")

        out.append({**t, "panel_job": panel_job, "conv": conv,
                    "match": match, "locate": note})
        time.sleep(0.8)

    json.dump(out, open("panel_verify.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n" + "=" * 80)
    print("汇总")
    print("=" * 80)
    okn = sum(1 for x in out if x.get("match"))
    print(f"  文件岗位与面板一致: {okn}/{len(out)}")
    print("\n  不一致的（文件数据有误，应以面板为准）:")
    for x in out:
        if x.get("match") is False:
            print(f"    {x['brand']} | {x['hr']}")
            print(f"      文件: 「{clean_job(x.get('jobName') or '')}」")
            print(f"      面板: 「{x.get('panel_job')}」")
    print("\n  未定位到会话的:")
    for x in out:
        if x.get("panel_job") is None:
            print(f"    {x['brand']} | {x['hr']} | {x.get('locate')}")
    print("\n明细已写入 panel_verify.json")


if __name__ == "__main__":
    main()
