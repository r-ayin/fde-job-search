# 文件排除说明

本仓库为求职自动化项目的**匿名化副本**，以下内容被排除：

## 一、绝不包含（安全红线）
- **Chrome 用户数据**（`Default/`、`Local State`）—— 含 BOSS 直聘登录 cookie
- **简历与个人档案**（`简历档案-*.md`、`resume_text.txt`、`FDE岗位信息wiki.md` 等）
- **HR 聊天记录**（`chat*.json`、`collect_chats.json`、`*convs*.json`）—— 含第三方真实姓名

## 二、已匿名化处理
| 原内容 | 替换为 |
|---|---|
| 候选人真实姓名 | `候选人` |
| 手机号 | `130****48` 形式 |
| 简历页 URL | `https://example.com/resume/` |
| 本机绝对路径 | `<PROJECT_DIR>` |

## 三、排除文件类型
- Chrome/系统脚本（`*.ps1`）
- 临时调试产物（`_*.json`、`*.log`、`t_*.json`）
- 投递行为记录（`send_*.json`、`sent_*.json`、`monday*.json`）
- 中间数据目录（`_research/`、`_research_tmp/`、`__pycache__/`）

## 四、保留内容
- 全部抓取/分析**脚本**（可复现）
- 岗位**数据**（企业公开信息，不含个人投递行为）
- **方法论文档**（技术路径、FDE 判定规则等）

排除文件共 138 个。
