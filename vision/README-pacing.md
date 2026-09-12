# 反风控节奏层（pacing）

控制发送/抓取的频率与熔断。**这一层是硬约束，不是建议**——2026-09-10 的封禁
复盘确认主因是频次，不是客户端指纹。

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `BATCH_CAP` | 5 | 单轮最多发送人数 |
| `INTERVAL_MIN/MAX` | 25 / 70 秒 | 相邻发送间隔，**随机取值**，关键是随机 |
| `VERIFY_EVERY` | 3 | 每 N 人做一次轻量校验 |
| `DAILY_CAP` | 30 | 每日发送上限 |

抓取侧（`fetch_jd_paced.py`）：间隔 15~25 秒随机，每日上限 30。

## 风控信号识别

`is_risk_signal(*texts)` 检查三类信号，命中任意一类即应熔断：

1. **页面文案** —— 安全验证 / 操作频繁 / 存在异常 / 已被禁止…
2. **接口错误码** —— `code:36`（账户异常行为）/ `code:37`（环境存在异常）
3. **验证页 URL** —— `/passport/zp/verify`、`verify.html`

第 3 类是最早期的信号，也是最容易忽略的。2026-09-10 当天 12:52 首次跳验证页时
若能识别并停下，就不会升级到 13:56 的 API 封禁。

9 个用例覆盖测试全部通过（含 3 个正常场景无误报）。

## 熔断机制

命中风控信号 → `trip()` 落盘 → 后续 `check_before_round()` 直接抛
`RiskCircuitBreaker`，必须人工确认（删除状态文件或 `--reset`）才能继续。

状态文件：`pacing_state.json`（发送）、`jd_state.json`（抓取）。

## 用法

```python
from pacing import Pacing, RiskCircuitBreaker, is_risk_signal

pacing = Pacing()
allow = pacing.check_before_round(planned=20)   # -> 5（受单轮上限约束）
for i, t in enumerate(targets[:allow]):
    ...
    pacing.record_success()
    if pacing.should_verify(i):
        ...  # 轻量校验
    pacing.wait_between(i, len(targets[:allow]))
```

## 三类风险的处置优先级

按证据强度排序（详见 memory `boss-ban-causes`）：

1. **服务端频次** —— 唯一确证在跑的，就是它封的账号。**最高优先级**
2. **发送同质化** —— 40 个 HR 收到完全相同的文案，是脚本的典型特征
3. **客户端指纹** —— `isTrusted=False` 等，存在但未被平台用上

节奏层解决第 1 条；第 2 条需要逐人差异化文案（`build_message` 已按岗位名变量化，
但仍需人工判断是否需要更强的差异化）。

## 注意

- `wait_between` 累计等待可能很长（5 人 × 平均 47 秒 ≈ 3 分钟），这是**特性不是缺陷**。
- 熔断后不要用搜索接口试探恢复——每试探一次都刷新风控计时。
