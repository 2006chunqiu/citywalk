"""路径规划层：把编排好的途经点连成真实步行折线。

分工约定：
- mock_data 只负责"选哪些点、按什么顺序"（估算距离用于约束求解）
- 本模块负责"实际怎么走过去"：逐段调高德 /v3/direction/walking 拼折线

三条降级规则（保证接口永远不 500）：
1. 短段（<120 米）不调接口，直接直线——省配额，视觉上也看不出差别
2. 单段接口失败（网络/无路/Key 冷却）→ 该段降级直线，其余段照常
3. 单次请求调用数超过预算 → 剩余段全部直线，并标记 budgetExhausted

产出：
- polyline 变成真实步行折线（含每个转弯点）
- distanceM / walkS / durationS / detourRatio / difficulty / reason 全部按真实数据重算
- 每条方案带 polylineSource（amap / mixed / estimated），答辩时可解释折线来源
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..algo.scoring import haversine_m
from ..config import settings
from . import amap
from .mock_data import DETOUR_FACTOR, _reason

logger = logging.getLogger(__name__)

MIN_LEG_M = 120.0            # 短于此距离不调接口
QPS_INTERVAL = 0.35          # 段与段之间至少间隔，个人 Key 约 3 QPS
_CACHE_LIMIT = 512           # 进程内折线缓存上限（同一段路跨方案复用）
_CACHE: dict[tuple[float, float, float, float], dict[str, Any]] = {}
_last_call_ts = 0.0


async def _throttle() -> None:
    """控制在途 QPS：两条腿之间强制间隔，避免触发 10021 并发超限。"""
    global _last_call_ts
    wait = QPS_INTERVAL - (time.time() - _last_call_ts)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_call_ts = time.time()


def _cache_key(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float, float, float]:
    return (round(a[0], 5), round(a[1], 5), round(b[0], 5), round(b[1], 5))


def _straight_leg(a: tuple[float, float], b: tuple[float, float]) -> dict[str, Any]:
    """估算段：直线 + 城区绕行系数 1.18，速度按 1.25 m/s。"""
    straight = haversine_m(a, b)
    dist = straight * DETOUR_FACTOR
    return {
        "distance": int(dist),
        "duration": int(dist / 1.25),
        "polyline": [[a[0], a[1]], [b[0], b[1]]],
        "source": "estimated",
    }


async def _leg(
    a: tuple[float, float],
    b: tuple[float, float],
    budget: int,
    stats: dict[str, Any],
) -> dict[str, Any]:
    """取一段路的折线：缓存 → 接口 → 降级。"""
    if haversine_m(a, b) < MIN_LEG_M:
        stats["straightLegs"] += 1
        return _straight_leg(a, b)

    key = _cache_key(a, b)
    if key in _CACHE:
        stats["cacheHits"] += 1
        return _CACHE[key]

    if stats["calls"] >= budget:
        stats["budgetExhausted"] = True
        stats["straightLegs"] += 1
        return _straight_leg(a, b)

    try:
        await _throttle()
        result = await amap.walking(a, b)
    except (amap.AmapError, amap.AllKeysExhausted) as exc:
        logger.warning("步行路径失败，本段降级直线：%s -> %s（%s）", a, b, exc)
        stats["failedLegs"] += 1
        return _straight_leg(a, b)

    stats["calls"] += 1
    if len(_CACHE) < _CACHE_LIMIT:
        _CACHE[key] = result
    return result


async def attach_walking(result: dict, budget: int | None = None) -> dict:
    """给每条方案补真实步行折线，并按真实数据重算全部指标。"""
    budget = settings.api_call_budget if budget is None else budget
    stats: dict[str, Any] = {
        "calls": 0,
        "cacheHits": 0,
        "failedLegs": 0,
        "straightLegs": 0,
        "budgetExhausted": False,
    }

    for scheme in result.get("schemes") or []:
        waypoints = scheme.get("waypoints") or []
        line = scheme.get("polyline") or []
        if len(line) < 2:
            continue

        origin = (line[0][0], line[0][1])
        destination = (line[-1][0], line[-1][1])
        seq: list[tuple[float, float]] = [origin]
        seq += [(w["lng"], w["lat"]) for w in waypoints]
        seq.append(destination)

        coords: list[list[float]] = []
        total_m = 0
        total_s = 0
        scheme_amap = 0
        scheme_est = 0

        for a, b in zip(seq, seq[1:]):
            leg = await _leg(a, b, budget, stats)
            total_m += leg["distance"]
            total_s += leg["duration"]
            for pt in leg["polyline"]:
                if not coords or abs(coords[-1][0] - pt[0]) > 1e-7 or abs(coords[-1][1] - pt[1]) > 1e-7:
                    coords.append(pt)
            if leg["source"] == "amap":
                scheme_amap += 1
            else:
                scheme_est += 1

        straight = haversine_m(origin, destination)
        base_m = straight * DETOUR_FACTOR

        scheme["polyline"] = [[round(x, 6), round(y, 6)] for x, y in coords]
        scheme["distanceM"] = int(total_m)
        scheme["walkS"] = int(total_s)
        scheme["durationS"] = int(total_s) + int(scheme.get("stayS") or 0)
        scheme["detourRatio"] = round(total_m / base_m, 2) if base_m else 1.0
        scheme["difficulty"] = (
            "easy" if total_m < 4000 else ("standard" if total_m <= 8000 else "deep")
        )
        scheme["reason"] = _reason(scheme["mode"], int(total_m), int(base_m), len(waypoints))
        if scheme_amap and scheme_est:
            scheme["polylineSource"] = "mixed"
        elif scheme_amap:
            scheme["polylineSource"] = "amap"
        else:
            scheme["polylineSource"] = "estimated"

    result["apiCalls"] = stats["calls"]
    result["routing"] = {
        "provider": "amap" if stats["calls"] else "estimated",
        "calls": stats["calls"],
        "cacheHits": stats["cacheHits"],
        "straightLegs": stats["straightLegs"],
        "failedLegs": stats["failedLegs"],
        "budgetExhausted": stats["budgetExhausted"],
    }
    logger.info(
        "路径规划完成：调用 %d 次 / 缓存命中 %d / 降级 %d / 短段 %d",
        stats["calls"], stats["cacheHits"], stats["failedLegs"], stats["straightLegs"],
    )
    return result
