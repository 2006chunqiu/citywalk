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
    """给三条方案起短名、把 reason 换成有画面的一句话。

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
                "title": s.get("title"),
                "km": round((s.get("distanceM") or 0) / 1000, 1),
                "minutes": round((s.get("durationS") or 0) / 60),
                "detour": s.get("detourRatio"),
                "stops": names,
            }
        )

    system = (
        "你在为武汉 City Walk 的三条备选路线起短名、写推荐理由。\n"
        "每条短名 3~7 个汉字，像「老城慢走线」「江边吹风线」，要体现路线气质；"
        "每条理由一句中文，不超过 45 字。\n"
        "只能使用用户给出的公里数、分钟数、站点名和已有标题，"
        "不得新增任何地名、店铺、事实或数字。\n"
        '只返回 JSON：{"routes": [{"title": "短名", "reason": "一句话"}, ...]}'
    )
    user = json.dumps({"routes": lines}, ensure_ascii=False)

    data = await _chat_json(system, user, temperature=0.6)
    routes = (data or {}).get("routes")
    if not isinstance(routes, list) or len(routes) != len(schemes):
        return result

    for scheme, item in zip(schemes, routes):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip().replace("\n", "")
        if 2 <= len(title) <= 12:
            scheme["titleAuto"] = scheme.get("title")
            scheme["title"] = title
        text = str(item.get("reason", "")).strip()
        if text:
            scheme["reasonLlm"] = scheme.get("reason")
            scheme["reason"] = text
    result["llm"] = "on"
    return result


def _fallback_share_text(scheme: dict) -> str:
    title = scheme.get("title") or "武汉 City Walk"
    km = round((scheme.get("distanceM") or 0) / 1000, 1)
    stops = [w.get("name", "") for w in scheme.get("waypoints", []) if w.get("name")]
    if stops:
        return f"我走了条 {km} 公里的「{title}」，从{stops[0]}到{stops[-1]}，一共 {len(stops)} 站。"
    return f"我走了条 {km} 公里的「{title}」。"


async def share_text(scheme: dict) -> str:
    """写一句分享文案；不配 Key 时退回固定模板。"""
    fallback = _fallback_share_text(scheme)
    if not enabled():
        return fallback

    payload = {
        "title": scheme.get("title") or "武汉 City Walk",
        "km": round((scheme.get("distanceM") or 0) / 1000, 1),
        "minutes": round((scheme.get("durationS") or 0) / 60),
        "stops": [w.get("name", "") for w in scheme.get("waypoints", [])],
    }
    system = (
        "你在写一条武汉 City Walk 的朋友圈分享文案，一句话，不超过 45 字。\n"
        "只能使用给出的路线名、公里数、分钟数和站点名，不得新增任何地名、店铺、事实或数字；"
        "不要加链接，不要夸张。返回 JSON：{\"text\": \"...\"}"
    )
    data = await _chat_json(
        system, json.dumps(payload, ensure_ascii=False), temperature=0.75
    )
    text = str((data or {}).get("text", "")).strip().replace("\n", " ")
    if 4 <= len(text) <= 80:
        return text
    return fallback
