# FDE 求职自动化工具集

杭州 FDE（前沿部署工程师）/ AI 交付 / AI 解决方案类岗位的信息采集、筛选与投递自动化工具。

> ⚠️ 本仓库为**匿名化副本**。原始工作目录中的简历、HR 聊天记录、登录凭证、
> 投递文案均已排除，个人经历与量化成果已脱敏。详见 [EXCLUDED.md](./EXCLUDED.md)。

---

## 项目目标

在杭州寻找 FDE / AI 交付 / AI 解决方案类岗位，建立从**信息采集 → 筛选评分 → 定制文案 → 投递**的完整链路。

核心难点：招聘平台普遍有频率风控，高频接口调用会触发账号限制。
本项目探索了**低可检测性**的采集方式，并在实践中修正了多个真实故障。

---

## 目录结构

```
vision/                       核心库（可复用）
├── dom_tools.py              DOM 读写与元素定位（零网络请求）
├── input_primitives.py       真实鼠标/键盘事件原语（CDP）
├── pacing.py                 反风控节奏层（限速 + 熔断）
├── fde_classify.py           基于 JD 正文判定是否 FDE 岗
├── vision.py                 OCR 层（已降级为兜底）
└── boss_vision.py            岗位卡 OCR 解析（兜底方案）

抓取器
├── fetch_official_jd.py      企业官网 JD 抓取（MokaHR 系统）
├── fetch_beisen.py           企业官网 JD 抓取（北森系统）
├── fetch_misc_jd.py          企业官网 JD 抓取（其他自有系统）
├── fetch_js_sites.py         JS 渲染站点抓取
├── chrome_scraper.py         系统 Chrome + CDP 通用抓取器
└── fetch_jd_paced.py         招聘平台低频 JD 抓取（真实导航 + DOM）

筛选与合并
├── merge_official_jd.py      多源 JD 合并去重 + FDE 判定
├── merge_research.py         公司池合并去重
├── filter_new.py             岗位筛选
├── build_delivery_todo.py    交付类岗位清单构建
├── pick_top30.py             优先投递清单
└── exclude_lang.py           语言要求排除

投递
├── send_paced.py             带节奏控制的发送主流程
├── run_monday.py             批量投递任务
└── precheck_monday.py        投递前实时清洗

数据（企业公开信息）
├── official_jd_all.json      全量 JD
├── official_jd_fde.json      筛选后 AI/交付相关
├── beisen_jd.json            北森来源 JD
└── official_misc_jd.json     其他官网来源 JD
```

---

## 技术要点

### 1. 用 DOM 读取替代接口调用

实测对比（同一页面，CDP Network 域计量）：

| 方案 | 网络请求 | 耗时 |
|---|---|---|
| `Runtime.evaluate` 读 DOM | **0** | **2ms** |
| 截图 + OCR | 0（截图本身） | 1490ms |

关键：**OCR 必须先加载页面才能截图**，那次 `Page.navigate` 照样发生。
所以 OCR 对可检测性零贡献，反而增加耗时和识别误差。

**正确分工**：读数据/定位用 DOM（零请求），点击用 CDP 真实坐标（保 `isTrusted=True`）。

### 2. 真实事件原语

| 方式 | 事件链 | isTrusted |
|---|---|---|
| `Input.dispatchMouseEvent` | pointerdown→mousedown→pointerup→mouseup→click | ✅ True |
| `element.click()` | 仅 click | ❌ False |
| 逐字符 `dispatchKeyEvent` | 每字 keydown→beforeinput→input→keyup | ✅ True |
| `Input.insertText` | 仅 beforeinput+input | True（但零按键） |

### 3. 反风控节奏层

`vision/pacing.py` 把频率控制做成硬门禁：

- 单轮发送上限 5 条，相邻间隔**随机** 25~70 秒
- 每 3 条做一次风控校验
- 风控信号（验证码 / 账号异常 / 操作频繁 / 验证页 URL）命中即**熔断落盘**，需人工清除才能继续

### 4. 字体反爬破解

部分平台用自定义字体把数字渲染成 PUA 私有区字符。
实测映射规律：数字 d → `chr(0xE031 + d)`，已实现 `decode_pua_salary()`。

### 5. 官网招聘系统对接

| 系统 | 对接方式 |
|---|---|
| MokaHR | AES-CBC 解密（密钥在响应头 `necromancer`），列表 + 详情 API |
| 北森 zhiye | `POST /api/Jobad/GetJobAdPageList`，返回体直接含 JD 正文 |
| 某安防厂商自有 | `getPostInfoForSys` 列表接口匿名可读 |
| 某互联网公司自有 | `POST /api/hr163/position/queryPage`，列表响应含完整 JD |

---

## 踩过的坑（供参考）

| 问题 | 根因 | 修复 |
|---|---|---|
| 点击完全无反应（零事件、零网络） | Chrome 在后台时 `visibilityState=hidden`，输入事件不投递 | 操作前 `Page.bringToFront` 并确认 `document.hasFocus()` |
| 按钮找不到 | 按钮文本含换行（`"继续沟通\n   "`），精确匹配失败 | 比较前归一化空白 |
| 消息被拆成多条发出 | 输入框是 Enter 发送模式，逐字符输入时换行触发送 | 正文改用 `Input.insertText` |
| 点「立即沟通」不跳转 | 平台只创建会话不导航 | 回会话列表按品牌+岗位查找兜底 |
| 服务端请求超时 | 长任务中单次 CDP 命令超时 | 逐关键词落盘 + 断点续采 |
| 岗位名大面积错配 | 目标文件记录与实际不符（实测 50%） | 以页面真实岗位名为准，JD 判定作补充 |
| 搜索页翻页无效 | `&page=N` 参数被忽略 | 改用多关键词切分查询 |

---

## 数据说明

- JD 数据来自**企业官方招聘系统**与公开渠道
- 均为企业公开信息，不含个人隐私
- 已剔除：个人简历、HR 聊天记录、登录凭证、投递行为记录、定制文案

---

## 免责声明

本项目仅用于个人求职与技术研究。使用者应遵守目标平台的服务条款，
合理控制请求频率，自行承担账号风控等风险。
