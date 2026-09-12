# -*- coding: utf-8 -*-
"""搜集一：消息页新会话与 HR 回复（只读，零网络请求）。

滚动全量会话，分类输出：
  - 未读（有新消息）
  - HR 主动回复的（排除我们发出的内容）
  - 仅默认招呼语、待发定制消息的
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))

from send_paced import RelayCDP, Sender  # noqa: E402

# 我们发出的内容特征
OUR_MARKS = ["您好，看到", "能和您沟通一下吗", "个人简历网页", "虽然本句话为ai发送",
             "补充一下我的个人简历"]
# 拒绝信号
REJECT = ["不合适", "不太合适", "不是很匹配", "不匹配", "抱歉", "不好意思", "已招满", "岗位已关闭"]


def classify(text):
    """返回 (类别, 说明)。"""
    t = text or ""
    if any(k in t for k in REJECT):
        return "reject", "HR 已明确拒绝"
    if any(k in t for k in OUR_MARKS):
        return "ours", "我们发出的内容（等待回复）"
    if t.strip():
        return "reply", "HR 主动发来的消息"
    return "empty", "无消息内容"


def main():
    cdp = RelayCDP()
    s = Sender(cdp, dry_run=True, skip_open=True)
    s.scroll_to_top()
    info = s._scroller()
    rounds = int(info["sh"] / info["ch"]) + 4 if info and info.get("ch") else 30

    seen = {}
    for i in range(rounds):
        for t in s.list_convs():
            if t:
                seen[t[:110]] = t
        if s.scroll_list():
            for t in s.list_convs():
                if t:
                    seen[t[:110]] = t
            break
        time.sleep(0.6)

    rows = []
    for t in seen.values():
        # 列表项格式: 未读标记 / 时间 / HR姓名+公司+职位 / [已读|送达] / 最后一条消息
        parts = [p.strip() for p in t.split("/")]
        unread = ""
        if parts and parts[0] and not any(c.isalpha() for c in parts[0]) \
                and not any("\u4e00" <= c <= "\u9fff" for c in parts[0]):
            # 首段是纯数字 = 未读数
            if parts[0].isdigit():
                unread = parts[0]
        who = parts[1] if unread else parts[0]
        rest = "/".join(parts[2:] if unread else parts[1:])
        cat, why = classify(rest)
        rows.append({"raw": t, "unread": unread, "who": who,
                     "last": rest[:200], "cat": cat, "why": why})

    from collections import Counter
    print("=" * 80)
    print(f"消息页会话总计: {len(rows)}")
    print("=" * 80)
    print("分类:", dict(Counter(r["cat"] for r in rows)))

    for key, title in [("reply", "🎯 HR 主动回复（最有价值）"),
                       ("reject", "🚫 HR 明确拒绝"),
                       ("ours", "⏳ 我们已发、等待回复"),
                       ("empty", "❓ 无内容")]:
        items = [r for r in rows if r["cat"] == key]
        print(f"\n{'=' * 80}\n{title}: {len(items)}\n{'=' * 80}")
        for r in sorted(items, key=lambda x: x["unread"], reverse=True):
            flag = f"[未读×{r['unread']}] " if r["unread"] else ""
            print(f"  {flag}{r['who']}")
            print(f"      {r['last'][:130]}")

    json.dump(rows, open("collect_chats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n明细已写入 collect_chats.json")


if __name__ == "__main__":
    main()
