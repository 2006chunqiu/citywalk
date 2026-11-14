"""DeepSeek 兜底服务（可选）。

设计原则（答辩口径）：模型只做两件事——听懂人话、写出人话。
- 不选点、不给坐标、不算距离；点位永远来自种子库，折线永远来自高德。
- 没有配置 LLM_API_KEY 时，所有函数返回 None，调用方自动降级为词表 / 模板，
  接口行为完全不变。
"""
from __future__ import annotations

import json
import logging
import os

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "8"))

# 只允许这 8 个标签，模型返回其他值一律丢弃
ALLOWED_TAGS = {"art", "park", "history", "food", "river", "local", "photo", "family"}


def enabled() -> bool:
    return bool(settings.llm_api_key)


async def _chat_json(system: str, user: str, temperature: float = 0.4) -> dict | None:
    """调用 DeepSeek，返回解析后的 JSON；任何失败都返回 None（不抛出）。"""
    if not enabled():
        return None

    payload = {
        "model": MODEL,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 - 模型不可用时必须降级
        logger.warning("LLM 调用失败，降级处理：%s", exc)
        return None

    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    try:
        return json.loads(content)
    except ValueError:
        logger.warning("LLM 返回非 JSON：%s", content[:120])
        return None


async def tags_from_query(text: str) -> list[str] | None:
    """把一句话翻成最多 4 个标签。失败或结果为空返回 None。"""
    system = (
        "你是武汉 City Walk 的需求解析器。把用户的一句话翻译成兴趣标签。\n"
        "只能从这 8 个标签里选：art(文艺) park(公园绿地) history(历史建筑) food(美食小吃) "
        "river(江景滨江) local(市井烟火) photo(拍照出片) family(亲子友好)。\n"
        "最多 4 个，按重要程度排序。只返回 JSON：{\"tagIds\": [\"art\", \"river\"]}\n"
        "不确定就少给，不要编。"
    )
    data = await _chat_json(system, text, temperature=0.2)
    if not data:
        return None

    raw = data.get("tagIds")
    if not isinstance(raw, list):
        return None

    out: list[str] = []
    for item in raw:
        tag = str(item).strip().lower()
        if tag in ALLOWED_TAGS and tag not in out:
            out.append(tag)
    return out[:4] or None


async def polish_schemes(result: dict) -> dict:
    """把三条方案的 reason 换成有画面的一句话。

    只改文字，不动任何数字/坐标/点位；失败原样返回。
    """
    if not enabled():
        return result

    schemes = result.get("schemes") or []
    if not schemes:
        return result

    lines = []
    for i, s in enumerate(schemes, start=1):
        names = "、".join(w.get("name", "") for w in s.get("waypoints", []))
        lines.append(
            {
                "index": i,
                "mode": s.get("mode"),
                "km": round((s.get("distanceM") or 0) / 1000, 1),
                "minutes": round((s.get("durationS") or 0) / 60),
                "detour": s.get("detourRatio"),
                "stops": names,
            }
        )

    system = (
        "你在为武汉 City Walk 的三条备选路线写推荐理由，每条一句中文，不超过 45 字。\n"
        "只能使用用户给出的公里数、分钟数、站点名，不得新增任何地名、店铺、事实或数字。\n"
        "语气自然、有画面，但不要夸张。返回 JSON：{\"reasons\": [\"第一句\", \"第二句\", \"第三句\"]}"
    )
    user = json.dumps({"routes": lines}, ensure_ascii=False)

    data = await _chat_json(system, user, temperature=0.6)
    reasons = (data or {}).get("reasons")
    if not isinstance(reasons, list) or len(reasons) != len(schemes):
        return result

    for scheme, text in zip(schemes, reasons):
        text = str(text).strip()
        if text:
            scheme["reasonLlm"] = scheme.get("reason")
            scheme["reason"] = text
    result["llm"] = "on"
    return result
