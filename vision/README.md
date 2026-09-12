# 视觉/操作层（vision）

> **架构修正（2026-09-11）**：本目录原设计的「OCR 读数据」已退出主链路，
> 改为 **DOM 定位 + CDP 真实事件**。OCR 降级为可选兜底。理由见下。

## 架构决策：为什么不用 OCR 读数据

实测对比（同一页面，CDP Network 域计量）：

| 方案 | 网络请求 | 耗时 | 隐蔽性收益 |
|---|---|---|---|
| `Runtime.evaluate` 读 DOM | **0** | **2ms** | 无网络、无事件、无 DOM 变更 |
| 截图 + OCR | 0（截图本身） | 1490ms | **零** |

关键点：**OCR 必须先加载页面才能截图**——那一次 `Page.navigate` 照样发生。
所以 OCR 对可检测性零贡献，只增加耗时和识别误差。

直接证据：搜索页 DOM 读到的薪资本来就是明文（`15-25K`、`18-30K·13薪`、
`200-300元/天`），不需要识别。

**OCR 唯一保留场景**：字体反爬字段。`job_detail` 页 DOM 的 `salary` 是空串
（数字不在 DOM 文本里），此时才需要 OCR 兜底。

## 正确的分工

| 环节 | 用什么 | 为什么 |
|---|---|---|
| 读数据 / 定位元素 | **DOM**（`getBoundingClientRect`） | 零请求、精确、2ms |
| 点击 | **CDP 真实坐标**（`Input.dispatchMouseEvent`） | 保 `isTrusted=True`，DOM `.click()` 做不到 |
| 输入 | **逐字符 `dispatchKeyEvent`** | 每字 keydown/keyup；`insertText` 是一次性插入 |

DOM 定位 + CDP 真实点击 = 既隐蔽又准确，两者不冲突。

## 实测结论（均为本地验证）

**读 DOM（`test_dom.py`）**
- 读卡片期间网络请求数 **0**（CDP Network 域实测，非推断）
- 3 张卡的 eid/岗位/薪资/公司/标签/坐标全部正确，薪资均为明文
- DOM 定位 + 真实点击：5 个事件全部 `isTrusted=True`
- 对照 `element.click()`：`isTrusted=False`

**输入原语（`test_primitives2.py` / `test_e2e.py`）**
- `dispatchMouseEvent`：pointerdown→mousedown→pointerup→mouseup→click，全 trusted
- 逐字符 `dispatchKeyEvent`：每字 keydown→beforeinput→input→keyup，中文正确
- `clear_field`（Ctrl+A + Delete）替代 `innerHTML=''`，走真实按键

**发送写路径（`test_send_offline.py`，用 mock_chat.html 复刻 BOSS DOM）**
- 面板更新滞后 900ms 时，`await_panel` 仍能拿到正确岗位名（2.4s 内稳定）
- 岗位名正确剥离薪资后缀（`...负责人 18-30K` → `...负责人`）
- 589 字文案完整写入，591 个 keydown，全部 trusted
- 发送成功、输入框清空

## 文件

| 文件 | 作用 |
|---|---|
| `dom_tools.py` | **主用**：读数据、定位元素、取坐标（零请求） |
| `input_primitives.py` | `real_click` / `type_text` / `clear_field` / `human_scroll` |
| `pacing.py` | 反风控节奏层：单轮上限、随机间隔、熔断 |
| `vision.py` | OCR 层（**已降级为兜底**，仅字体反爬字段需要） |
| `boss_vision.py` | 岗位卡 OCR 解析（兜底方案） |
| `mock_search.html` / `mock_chat.html` | 本地测试页（复刻 BOSS 结构） |
| `test_dom.py` | DOM 方案验证（含零请求实测） |
| `test_send_offline.py` | 发送写路径离线验证 |
| `test_primitives2.py` / `test_e2e.py` | 输入原语验证 |
| `test_parse.py` | 岗位卡 OCR 解析验证（兜底方案） |

## 用法

```python
from dom_tools import find_by_text, read_job_cards
from input_primitives import real_click, type_text, clear_field

# 读搜索页岗位卡（零网络请求）
data = read_job_cards(cdp)
for c in data["cards"]:
    print(c["company"], c["jobName"], c["salary"])

# 读任意文本
from dom_tools import read_text
title = read_text(cdp, ".chat-conversation")

# DOM 定位 + 真实点击
loc = find_by_text(cdp, "立即沟通")
if loc:
    real_click(cdp, loc["x"], loc["y"])
```

发送主流程：`cd <PROJECT_DIR> && python send_paced.py --limit 5 --dry-run`

## 三个实现坑（都踩过并修掉）

**1. 坐标换算（仅 OCR 方案需要）**
`Page.captureScreenshot` 返回设备像素图，`Input.dispatchMouseEvent` 收 CSS 像素，
差一个 `devicePixelRatio`。用 DOM 的 `getBoundingClientRect` 则直接是 CSS 像素，无需换算。

**2. `cdp.send()` 的返回约定不统一**
本目录 `dom_tools._eval` 假定 `send()` 已剥掉 CDP 信封（即直接拿到
`{"result": {...}}`），与 `send_paced.RelayCDP` 一致。
而旧的 `send_v5.py` 里 `cmd()` 返回**原始响应**，要多钻一层 `["result"]`。
两种约定混用会静默拿到 `None`。

**3. mousedown 与 mouseup 之间不能有重排**
浏览器的 `click` target 取 `mousedown` 与 `mouseup` 的最近公共祖先。
若期间页面重排（新消息到达、列表刷新、输入区高度变化），
`click` 会落到外层容器，按钮的处理函数不执行 —— 表现为**"点了但没发出去"**。
`send_one` 因此改为：每次重试都重新定位取新坐标，并用"输入框是否清空"做业务层校验，最多重试 3 次。

## 注意

- `rapidocr` 默认会拉 `numpy 2.5+`，会破坏 `numba`。本机已固定 `numpy 2.3.5`。
- 所有验证都在**本地 mock 页 / 合成图**上完成，**未接触 BOSS 线上服务**。
