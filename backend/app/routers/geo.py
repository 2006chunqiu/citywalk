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


@router.get("/geocode")
async def geocode(address: str, city: str = "武汉"):
    """文字地址 → 坐标。前端把「武昌火车站」这类输入换成 lng/lat 用这个。"""
    address = address.strip()
    if len(address) < 2:
        raise ApiError(400, "INVALID_ADDRESS", "至少输入 2 个字符")
    try:
        return await amap.geocode(address, city)
    except amap.AllKeysExhausted as exc:
        raise ApiError(503, "ALL_KEYS_EXHAUSTED", str(exc)) from exc
    except amap.AmapError as exc:
        if exc.infocode == "NO_RESULT":
            raise ApiError(404, "GEOCODE_NOT_FOUND", f"没有找到「{address}」，换个说法试试") from exc
        raise ApiError(502, exc.infocode or "AMAP_ERROR", exc.info) from exc
