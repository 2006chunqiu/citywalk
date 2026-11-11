from __future__ import annotations

from fastapi import APIRouter

from ..errors import ApiError
from ..services import amap

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("/regeo")
async def regeo(lng: float, lat: float):
    try:
        return await amap.regeo(lng, lat)
    except amap.AllKeysExhausted as exc:
        raise ApiError(503, "ALL_KEYS_EXHAUSTED", str(exc)) from exc
    except amap.AmapError as exc:
        raise ApiError(502, exc.infocode or "AMAP_ERROR", exc.info) from exc
