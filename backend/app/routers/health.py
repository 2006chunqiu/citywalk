from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..services.amap import KEY_POOL

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    snap = KEY_POOL.snapshot()
    return {
        "ok": True,
        "llm": "up" if settings.llm_api_key else "off",
        "amap": "up" if snap["alive"] else "off",
        "keyPool": {"total": snap["total"], "alive": snap["alive"], "calls": snap["calls"]},
        "budget": {"apiCallBudget": settings.api_call_budget},
    }
