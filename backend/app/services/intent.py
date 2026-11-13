"""一句话输入 → 兴趣标签（关键词词表，不用 LLM，无幻觉风险）。

对应 PRD FR-02-01 的"自然语言意图解析"降级实现：答辩口径为
"词表规则映射，模型不参与，保证结果可复现"。词表顺序即优先级，
最多返回 4 个标签（接口约定 tagIds 1~4 个）。
"""
from __future__ import annotations

KEYWORDS: list[tuple[str, list[str]]] = [
    ("art",     ["文艺", "书店", "咖啡", "美术馆", "艺术", "博物馆", "小资", "安静", "文创"]),
    ("park",    ["公园", "绿地", "湖", "东湖", "自然", "草坪", "湿地"]),
    ("history", ["历史", "老建筑", "旧址", "故居", "民国", "古街", "老街", "里份", "租界"]),
    ("food",    ["美食", "小吃", "过早", "好吃", "吃", "热干面", "豆皮", "夜市"]),
    ("river",   ["江", "江滩", "滨江", "码头", "轮渡", "江景", "长江", "江风"]),
    ("local",   ["市井", "烟火", "菜场", "菜市场", "巷", "老街", "生活气"]),
    ("photo",   ["拍照", "出片", "打卡", "网红", "好看", "风景", "机位"]),
    ("family",  ["亲子", "孩子", "带娃", "儿童", "全家", "遛娃", "科普"]),
]

MAX_TAGS = 4


def query_to_tags(text: str) -> list[str]:
    """命中即保留；无命中返回空列表，由前端引导用户改用标签选择。"""
    if not text:
        return []
    out: list[str] = []
    for tag_id, words in KEYWORDS:
        if any(w in text for w in words):
            out.append(tag_id)
        if len(out) >= MAX_TAGS:
            break
    return out
