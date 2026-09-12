# -*- coding: utf-8 -*-
"""周一投递任务（2026-09-14 09:30 自动执行）。

流程：对 monday30.json 里 30 个新岗位逐条：
  1. 打开岗位详情页（顺带读 JD，同页无额外请求）
  2. 阿里系直接跳过；JD 判定是否为 AI 交付类
  3. 点「立即沟通」（会发 BOSS 默认招呼语，这是固有行为）
  4. 未自动跳转时回会话列表兜底进入
  5. 写入定制文案并发送
  6. 逐条核对实际送达

节奏：单轮上限 30，相邻间隔随机 25~70 秒，每 3 人风控校验。
预计耗时 30 条 × 约 47 秒 ≈ 24 分钟。

安全：
  - 风控信号（验证码/异常/限制）立即熔断并落盘
  - 写入长度不符即中止，绝不发送半截内容
  - 每条发送后核对输入框是否清空
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "vision"))

from pacing import Pacing, RiskCircuitBreaker  # noqa: E402
from send_paced import RelayCDP, Sender, clean_job  # noqa: E402

TODO = os.path.join(HERE, "monday30.json")
LOG = os.path.join(HERE, "monday_send_log.json")


def main():
    if not os.path.exists(TODO):
        print(f"❌ 找不到 {TODO}")
        return
    targets = json.load(open(TODO, encoding="utf-8"))
    print(f"周一投递任务：{len(targets)} 条")

    # 检查 relay / Chrome
    try:
        cdp = RelayCDP()
        cdp.ensure_focus()
        url = cdp.val("location.href")
        print(f"Chrome 当前页: {str(url)[:70]}")
    except Exception as e:
        print(f"❌ 无法连接 Chrome（relay 未启动或扩展未连接）: {e}")
        print("   请确认：1) relay.py 在运行  2) Chrome 已开  3) OpenClaw 扩展已连接")
        return

    sender = Sender(cdp, dry_run=False, skip_open=False)
    pacing = Pacing(batch_cap=30)

    if pacing.tripped:
        print(f"⛔ 处于熔断状态（{pacing.tripped}），需人工 --reset 后重试")
        return

    results = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else []
    done = {r["eid"] for r in results if r.get("ok")}

    for i, t in enumerate(targets):
        if t.get("eid") in done:
            continue
        print(f"\n[{i+1}/{len(targets)}] {t.get('company')} | "
              f"{(t.get('jobName') or '')[:34]}")
        try:
            ok, note = sender.send_one(t)
        except RiskCircuitBreaker as e:
            pacing.trip(e)
            print(f"⛔ 熔断：{e}")
            break
        except Exception as e:
            ok, note = False, f"error:{str(e)[:80]}"
        print(f"   {'OK ' if ok else 'FAIL'} {note}")
        results.append({"eid": t.get("eid"), "company": t.get("company"),
                        "job": t.get("jobName"), "ok": ok, "note": note})
        json.dump(results, open(LOG, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if ok:
            pacing.record_success()
        if pacing.should_verify(i) and i < len(targets) - 1:
            risk = sender.check_risk(sender.read_state())
            if risk:
                pacing.trip(f"周期校验命中：{risk}")
                break
        if i < len(targets) - 1:
            pacing.wait_between(i, len(targets))

    okn = sum(1 for r in results if r.get("ok"))
    print(f"\n{'=' * 70}")
    print(f"完成：成功 {okn}/{len(results)} | 今日已发 {pacing.sent_today}/30")
    print(f"日志：{LOG}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
