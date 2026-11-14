"""高德 Web 服务封装：Key 池、失败分类、冷却与降级。

对应 PRD 5.6。只有配额与并发类错误才切换 Key，业务类错误直接抛出。
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from ..config import settings

BASE = "https://restapi.amap.com"

# infocode -> 冷却秒数；None 表示永久失效
COOLDOWN: dict[str, int | None] = {
    "10003": 3600,    # DAILY_QUERY_OVER_LIMIT 当日配额耗尽
    "10001": None,    # INVALID_USER_KEY
    "10009": None,    # USERKEY_PLAT_NOMATCH
}

# 瞬时并发超限（个人 Key 约 3 QPS）：短等待后重试，不惩罚 Key
# 单 Key 场景下若把 Key 打入冷却，本次请求就彻底没 Key 可用了
BACKOFF = {"10021", "10044", "10004"}
BACKOFF_SECONDS = 0.6

# 不会因为切换 Key 而好转的错误，直接抛出
FATAL_REPORT = {"10001", "10009"}


class AmapError(Exception):
    def __init__(self, infocode: str, info: str):
        super().__init__(f"{infocode}: {info}")
        self.infocode = infocode
        self.info = info


class AllKeysExhausted(Exception):
    """所有 Key 都在冷却或失效，调用方应降级到种子库/缓存。"""


class _KeyState:
    __slots__ = ("key", "calls", "cooldown_until", "dead")

    def __init__(self, key: str):
        self.key = key
        self.calls = 0
        self.cooldown_until = 0.0
        self.dead = False

    def healthy(self, now: float) -> bool:
        return not self.dead and now >= self.cooldown_until


class KeyPool:
    def __init__(self, keys: list[str]):
        self.states = [_KeyState(k) for k in keys]

    def __len__(self) -> int:
        return len(self.states)

    def pick(self, now: float | None = None) -> _KeyState | None:
        """当日用量最少优先，避免某个 Key 先耗尽。"""
        now = time.time() if now is None else now
        alive = [s for s in self.states if s.healthy(now)]
        if not alive:
            return None
        return min(alive, key=lambda s: s.calls)

    def report(self, state: _KeyState, infocode: str) -> None:
        policy = COOLDOWN.get(infocode, "keep")
        if policy is None:
            state.dead = True
        elif policy == "keep":
            return  # 业务错误，不惩罚 Key
        else:
            state.cooldown_until = time.time() + policy

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        alive = sum(1 for s in self.states if s.healthy(now))
        return {
            "total": len(self.states),
            "alive": alive,
            "calls": sum(s.calls for s in self.states),
        }


KEY_POOL = KeyPool(settings.amap_web_keys)


async def _call(path: str, params: dict[str, Any], timeout: float = 5.0, tries: int = 3) -> dict:
    if not len(KEY_POOL):
        raise AllKeysExhausted("未配置 AMAP_WEB_KEYS")

    last: AmapError | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for _ in range(tries):
            state = KEY_POOL.pick()
            if state is None:
                raise AllKeysExhausted("所有 Key 均在冷却或已失效")

            query = {**params, "key": state.key, "output": "json"}
            try:
                resp = await client.get(BASE + path, params=query)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last = AmapError("NETWORK", str(exc))
                continue

            state.calls += 1
            infocode = str(data.get("infocode", ""))
            if str(data.get("status")) == "1":
                return data

            if infocode in BACKOFF:
                last = AmapError(infocode, data.get("info", ""))
                await asyncio.sleep(BACKOFF_SECONDS)
                continue

            if infocode in FATAL_REPORT or infocode in COOLDOWN:
                KEY_POOL.report(state, infocode)
                last = AmapError(infocode, data.get("info", ""))
                continue
            raise AmapError(infocode, data.get("info", ""))

    raise last or AmapError("UNKNOWN", "高德接口调用失败")


async def inputtips(keywords: str, city: str = "武汉") -> list[dict]:
    data = await _call("/v3/assistant/inputtips", {"keywords": keywords, "city": city})
    out = []
    for tip in data.get("tips", []):
        loc = tip.get("location")
        if not loc or "," not in str(loc):
            continue  # 没有坐标的候选直接丢弃（PRD R-01-01-2）
        lng, lat = str(loc).split(",")[:2]
        out.append(
            {
                "name": tip.get("name", ""),
                "address": tip.get("address", "") or "",
                "lng": float(lng),
                "lat": float(lat),
                "adcode": str(tip.get("adcode", "")),
            }
        )
    return out


async def regeo(lng: float, lat: float) -> dict:
    data = await _call("/v3/geocode/regeo", {"location": f"{lng:.6f},{lat:.6f}"})
    regeocode = data.get("regeocode", {}) or {}
    comp = regeocode.get("addressComponent", {}) or {}
    return {
        "address": regeocode.get("formatted_address", "") or "",
        "name": None,
        "adname": comp.get("district", "") or "",
    }


async def geocode(address: str, city: str = "武汉") -> dict:
    """地址 → 坐标（正地理编码）。找不到时抛 NO_RESULT，由调用方转成 404。"""
    data = await _call("/v3/geocode/geo", {"address": address, "city": city})
    geos = data.get("geocodes") or []
    if not geos:
        raise AmapError("NO_RESULT", "没有匹配到该地点")
    geo = geos[0]
    loc = str(geo.get("location", ""))
    if "," not in loc:
        raise AmapError("NO_RESULT", "该地点没有坐标")
    lng_s, lat_s = loc.split(",")[:2]
    return {
        "name": geo.get("formatted_address") or address,
        "lng": float(lng_s),
        "lat": float(lat_s),
        "level": str(geo.get("level", "")),
        "adcode": str(geo.get("adcode", "")),
    }


async def place_around(
    lng: float,
    lat: float,
    types: str,
    radius: int = 2000,
    page_num: int = 1,
    page_size: int = 25,
) -> list[dict]:
    """周边检索（POI 2.0）。types 支持多个分类码用 | 分隔，合并召回。"""
    data = await _call(
        "/v5/place/around",
        {
            "location": f"{lng:.6f},{lat:.6f}",
            "types": types,
            "radius": str(radius),
            "page_num": str(page_num),
            "page_size": str(page_size),
            "show_fields": "business",
        },
    )
    out = []
    for poi in data.get("pois", []):
        loc = poi.get("location")
        if not loc:
            continue
        lng_s, lat_s = str(loc).split(",")[:2]
        biz = poi.get("business", {}) or {}
        rating = biz.get("rating")
        out.append(
            {
                "amapId": poi.get("id", ""),
                "name": poi.get("name", ""),
                "address": poi.get("address", "") or "",
                "lng": float(lng_s),
                "lat": float(lat_s),
                "typecode": str(poi.get("typecode", "")),
                "typeName": str(poi.get("type", "")).split(";")[-1],
                "rating": float(rating) if rating not in (None, "", []) else None,
            }
        )
    return out


async def walking(origin: tuple[float, float], destination: tuple[float, float]) -> dict:
    """步行路径规划（v3/direction/walking）。

    返回 {distance: 米, duration: 秒, polyline: [[lng,lat],...], source: "amap"}。
    steps[].polyline 是 "lng,lat;lng,lat" 字符串，这里按分号切开、逐个转成浮点数组，
    并去掉相邻重复点——前端直接把数组喂给高德 Polyline，不需要二次解析。
    """
    data = await _call(
        "/v3/direction/walking",
        {
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{destination[0]:.6f},{destination[1]:.6f}",
        },
    )
    paths = (data.get("route") or {}).get("paths") or []
    if not paths:
        raise AmapError("NO_PATH", "起终点之间无可用步行路径")

    path = paths[0]
    polyline: list[list[float]] = []
    for step in path.get("steps") or []:
        for pair in str(step.get("polyline") or "").split(";"):
            if "," not in pair:
                continue
            lng_s, lat_s = pair.split(",")[:2]
            try:
                pt = [round(float(lng_s), 6), round(float(lat_s), 6)]
            except ValueError:
                continue
            if not polyline or pt != polyline[-1]:
                polyline.append(pt)

    return {
        "distance": int(float(path.get("distance") or 0)),
        "duration": int(float(path.get("duration") or 0)),
        "polyline": polyline,
        "source": "amap",
    }
