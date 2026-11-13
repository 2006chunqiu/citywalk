"""一句话输入 → 标签（对应 netlify 版「告诉 AI 你想怎么走」的入口）。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.intent import query_to_tags

router = APIRouter(prefix="/api", tags=["intent"])


class IntentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100, description="一句话需求，如「想走点安静的老街」")


@router.post("/intent")
async def intent(req: IntentRequest):
    return {"tagIds": query_to_tags(req.query)}
