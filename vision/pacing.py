# -*- coding: utf-8 -*-
"""反风控节奏层：控制发送频率与熔断。

设计依据（来自 casperkwok/boss-recruit 的 anti-detection 规范，与本项目封禁复盘一致）：
  平台风控盯的是"非人类模式"，三个最危险的信号：节奏整齐、批量同质、脚本指纹。
  本次封禁复盘（见 memory boss-ban-causes）确认主因是频次，所以这层是硬约束。

核心参数：
  单轮上限  3~5 人（绝不一次刷几十个）
  相邻间隔  随机 25~70 秒（关键是**随机**，不能固定）
  每 N 人    一次轻量校验
  每日封顶  按目标人数而非按时间机械刷
"""
import json
import os
import random
import time
from datetime import datetime

# ---- 默认节奏参数 ----
BATCH_CAP = 5              # 单轮最多发送人数
INTERVAL_MIN = 25.0        # 相邻发送最小间隔（秒）
INTERVAL_MAX = 70.0        # 相邻发送最大间隔（秒）
VERIFY_EVERY = 3           # 每 N 人做一次校验
DAILY_CAP = 30             # 每日上限（可按需调整）

STATE_FILE = "pacing_state.json"

# ---- 风控信号 ----
RISK_MARKERS = [
    "安全验证", "人机验证", "异常验证", "操作频繁", "访问异常",
    "存在异常", "已被禁止", "账户异常", "环境异常",
]
RISK_CODES = {"36", "37"}   # 36=账户异常行为, 37=环境存在异常
RISK_URLS = ["/passport/zp/verify", "verify.html", "/web/passport"]


def is_risk_signal(*texts):
    """判断一批文本里是否出现风控信号。返回命中的标记或 None。

    检查三类：
      1. 页面文案（安全验证/操作频繁/存在异常…）
      2. 接口错误码（code:36 账户异常行为 / code:37 环境异常）
      3. 强制跳转的验证页 URL（最早期的信号，最容易被忽略）
    """
    for t in texts:
        if not t:
            continue
        s = str(t)
        for m in RISK_MARKERS:
            if m in s:
                return m
        for u in RISK_URLS:
            if u in s:
                return f"verify_url:{u}"
        for c in RISK_CODES:
            if f'"code":{c}' in s.replace(" ", "") or f"code:{c}" in s:
                return f"code:{c}"
    return None


class RiskCircuitBreaker(Exception):
    """触发熔断。携带原因，调用方应停止整轮并保留进度。"""


class Pacing:
    """发送节奏控制器。使用前先 load()，发送后 record()。"""

    def __init__(self, state_file=STATE_FILE, batch_cap=BATCH_CAP,
                 interval_min=INTERVAL_MIN, interval_max=INTERVAL_MAX,
                 daily_cap=DAILY_CAP, verify_every=VERIFY_EVERY):
        self.state_file = state_file
        self.batch_cap = batch_cap
        self.interval_min = interval_min
        self.interval_max = interval_max
        self.daily_cap = daily_cap
        self.verify_every = verify_every
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.sent_today = 0
        self.tripped = None
        self.load()

    # ---------- 状态持久化 ----------

    def load(self):
        if not os.path.exists(self.state_file):
            return
        try:
            d = json.load(open(self.state_file, encoding="utf-8"))
        except Exception:
            return
        if d.get("date") == self.today:
            self.sent_today = int(d.get("sent", 0))
        if d.get("tripped"):
            self.tripped = d["tripped"]

    def _save(self):
        json.dump({"date": self.today, "sent": self.sent_today,
                   "tripped": self.tripped, "updated": time.time()},
                  open(self.state_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- 门禁 ----------

    def check_before_round(self, planned):
        """开始一轮前的门禁。planned 为本轮计划发送数。"""
        if self.tripped:
            raise RiskCircuitBreaker(
                f"上次触发风控熔断（{self.tripped}），需人工确认后清除 {self.state_file} 才能继续")
        if self.sent_today >= self.daily_cap:
            raise RiskCircuitBreaker(
                f"今日已达上限 {self.daily_cap} 条（已发 {self.sent_today}），停止发送")
        allow = min(planned, self.batch_cap, self.daily_cap - self.sent_today)
        if allow < planned:
            print(f"[pacing] 本轮计划 {planned} 条，按节奏限制降为 {allow} 条"
                  f"（单轮上限 {self.batch_cap}，今日剩余 {self.daily_cap - self.sent_today}）")
        return allow

    def wait_between(self, index, total):
        """两条之间的随机等待。返回实际等待秒数。"""
        if index >= total - 1:
            return 0.0
        d = random.uniform(self.interval_min, self.interval_max)
        print(f"[pacing] 间隔等待 {d:.1f}s（{self.interval_min:.0f}~{self.interval_max:.0f}s 随机）")
        time.sleep(d)
        return d

    def should_verify(self, index):
        """是否该做一次轻量校验（每 verify_every 人）。"""
        return (index + 1) % self.verify_every == 0

    def record_success(self):
        self.sent_today += 1
        self._save()

    def trip(self, reason):
        """触发熔断并落盘。"""
        self.tripped = str(reason)
        self._save()
        print(f"[pacing] ⛔ 熔断：{reason}")

    def reset_trip(self):
        """清除熔断（人工确认后调用）。"""
        self.tripped = None
        self._save()


def human_delay(base=0.8, jitter=0.5):
    """页面内操作的短随机停顿，避免动作节奏过于整齐。"""
    time.sleep(max(0.05, base + random.uniform(-jitter, jitter)))
