"""请求与响应模型。字段名以 docs/api.md 为准，全部 camelCase。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LngLat(BaseModel):
    lng: float = Field(ge=73.0, le=136.0)
    lat: float = Field(ge=3.0, le=54.0)


class GenerateRequest(BaseModel):
    origin: LngLat
    destination: LngLat
    tagIds: list[str] = Field(min_length=1, max_length=4)
    tagOrder: list[str] | None = None
    effort: str = "normal"


class ReplanRequest(GenerateRequest):
    excludeIds: list[str] = Field(default_factory=list)


class ShareRequest(BaseModel):
    schemeId: str
