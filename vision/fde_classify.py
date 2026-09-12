# -*- coding: utf-8 -*-
"""基于 JD 正文判断岗位是否为 FDE（前沿部署 / 客户现场交付类）。

为什么需要：目标池的 jobName 由 eid 匹配 JD 得到，存在错配
（如奥星集团文件写"FDE（前沿部署工程师）"，面板实际是
"AI解决方案经理（工业流程行业）"）。用户在岗位名对不上时要求
**按 JD 正文判断是否属于 FDE**，是则用面板真实岗位名发送，否则跳过。

FDE 的本质特征（据此打分，不看标题）：
  深入客户现场 / 客户业务需求 / 方案设计与落地 / PoC 验证 /
  交付与客户满意度 / 客户对接 / 私有化部署 / 业务访谈

反例词必须精确到"岗位型"短语：曾用裸词 "评测" 误伤奥星集团
（其 JD 有"建立评测集与质量基线"，那是 FDE 的工作内容），
裸词 "地推" 误伤浙江连信（其 JD 只是列举获客渠道）。
"""
import re

# 强信号：客户现场 + 交付（+3 各，最多计 4 个）
STRONG = [
    "客户现场", "客户一线", "深入业务现场", "业务现场", "客户业务", "现场交付",
    "客户满意度", "客户对接", "客户成功", "客户的核心", "企业客户",
    "需求访谈", "业务访谈", "场景共创", "现场实施", "驻场", "交付工程师",
]
# 标题类信号（+3，最多计 1 个）
TITLE = ["前沿部署", "前线部署", "前向部署", "forward deployed", "fde"]
# 中信号：交付/部署/落地/方案（+2 各，最多计 8 个）
MEDIUM = [
    "交付", "部署", "落地", "解决方案", "方案设计", "poc", "mvp",
    "私有化", "陪跑", "实施", "集成", "上线", "prompt", "agent",
    "rag", "工作流", "大模型", "知识库",
]
# 反例（-8）：必须是**岗位型**短语，不是任意提及
NEGATIVE = [
    "数据标注", "标注任务", "标注团队", "标注评测", "标注员", "试标",
    "模型评测", "内容评测", "评测专员", "评测员", "评测标注",
    "数据质检", "质检专员", "店铺运营", "天猫运营", "京东运营",
    "客服专员", "地推专员", "地推销售", "电话销售", "美工",
]
# 研发偏科（-3）：只说内部研发、无客户现场
DEV_ONLY = [
    "自建ai原生平台", "参与公司自建", "内部平台建设",
    "核心模块的前端", "前端实现", "研发与迭代",
]


def _empty_hits():
    return {"strong": [], "medium": [], "title": [], "negative": [], "dev_only": []}


def fde_score(desc, title=""):
    """返回 (分数, 命中明细)。",
    """
    text = ((desc or "") + " " + (title or "")).lower()
    hits = _empty_hits()
    if not text.strip():
        return 0, hits
    for k in STRONG:
        if k in text:
            hits["strong"].append(k)
    for k in TITLE:
        if k in text:
            hits["title"].append(k)
    for k in MEDIUM:
        if k in text:
            hits["medium"].append(k)
    for k in NEGATIVE:
        if k in text:
            hits["negative"].append(k)
    for k in DEV_ONLY:
        if k in text:
            hits["dev_only"].append(k)

    score = (3 * min(len(hits["strong"]), 4)
             + 3 * min(len(hits["title"]), 1)
             + 2 * min(len(hits["medium"]), 8)
             - 8 * len(hits["negative"])
             - 3 * len(hits["dev_only"]))
    return score, hits


# 阈值：>=12 且至少 1 个强信号（真实客户现场证据）才算 FDE
THRESHOLD_FDE = 12
THRESHOLD_NO = 6


def is_fde(desc, title=""):
    """返回 (是否FDE|None, 分数, 说明)。None 表示边界，需人工判断。"""
    s, hits = fde_score(desc, title)
    if hits["negative"]:
        return False, s, f"命中反例特征: {'/'.join(hits['negative'][:3])}"
    # 标题直接写 FDE / 前沿部署 的，视为充分证据（用户口径：标题即岗位性质）
    if hits["title"] and s >= THRESHOLD_NO:
        return True, s, ("FDE 信号: 标题命中 " + "/".join(hits["title"])
                         + (" + " + "/".join(hits["strong"][:3]) if hits["strong"] else ""))
    if s >= THRESHOLD_FDE and hits["strong"]:
        return True, s, ("FDE 信号: " + "/".join(hits["strong"][:3])
                         + (" + " + "/".join(hits["title"]) if hits["title"] else ""))
    if s < THRESHOLD_NO:
        return False, s, f"信号不足（{s} 分）"
    if not hits["strong"]:
        return None, s, (f"边界（{s} 分，无客户现场强信号）: "
                         + "/".join(hits["medium"][:4]))
    return None, s, (f"边界（{s} 分）: " + "/".join(hits["strong"][:2] + hits["medium"][:3])
                     + (" | 研发偏科 " + "/".join(hits["dev_only"]) if hits["dev_only"] else ""))
