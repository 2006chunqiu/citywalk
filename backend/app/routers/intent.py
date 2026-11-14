"""一句话输入 → 标签。

顺序：先跑关键词词表（快、可复现、零成本），命中不足 2 个时再问 DeepSeek；
模型只返回标签，不参与选点。没有配置 LLM_API_KEY 时行为与原来完全一致。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import llm
from ..services.intent import query_to_tags

router = APIRouter(prefix="/api", tags=["intent"])


class IntentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100, description="一句话需求，如「想走点安静的老街」")


@router.post("/intent")
async def intent(req: IntentRequest):
    rule = query_to_tags(req.query)
    source = "rule"

    if len(rule) < 2 and llm.enabled():
        llm_tags = await llm.tags_from_query(req.query)
        if llm_tags:
            rule = list(dict.fromkeys(llm_tags + rule))[:4]
            source = "llm"

    return {"tagIds": rule, "source": source}
