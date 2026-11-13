"""打分与约束求解：纯函数，不依赖数据库与网络。

对应 PRD 的 FR-03-02（打分与排序）、FR-03-03（约束求解与途经点编排）。
改动这里请同步跑 tests/test_scoring.py。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import Sequence

EARTH_R = 6378137.0

# 三方案的因子权重，见 PRD 附录 B
MODE_WEIGHTS: dict[str, dict[str, float]] = {
    "shortest": {"M": 0.30, "A": 0.35, "H": 0.05, "T": 0.20, "V": 0.10},
    "max": {"M": 0.55, "A": 0.10, "H": 0.20, "T": 0.05, "V": 0.10},
    "balanced": {"M": 0.40, "A": 0.25, "H": 0.15, "T": 0.10, "V": 0.10},
}

# 标签优先级对应的权重
TAG_WEIGHTS = (1.0, 0.7, 0.5, 0.4)


@dataclass
class Poi:
    """候选点。字段与 data/poi.csv、表 poi 保持一致。"""

    poi_id: str
    name: str
    lng: float
    lat: float
    typecode: str = ""
    tag_ids: tuple[str, ...] = ()
    rating: float | None = None
    stay_minutes: int = 10
    source: str = "amap"
    type_name: str = ""
    address: str = ""

    @property
    def xy(self) -> tuple[float, float]:
        return (self.lng, self.lat)


@dataclass
class ScoreContext:
    origin: tuple[float, float]
    destination: tuple[float, float]
    tag_order: Sequence[str]
    radius_m: float
    avg_stay_minutes: float = 12.0
    weights: dict[str, float] = field(default_factory=lambda: dict(MODE_WEIGHTS["balanced"]))


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """两点球面距离（米）。参数为 (lng, lat)。"""
    lng1, lat1 = a
    lng2, lat2 = b
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    h = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * EARTH_R * asin(sqrt(h))


def buffer_radius_m(straight_m: float) -> float:
    """缓冲区半径 = clamp(0.5 × 直线距离, 500, 2500)。"""
    return max(500.0, min(2500.0, 0.5 * straight_m))


def waypoint_target_count(straight_m: float) -> int:
    """按起终点距离决定途经点目标数量（3–6 个）。"""
    if straight_m < 3000:
        return 3
    if straight_m < 5000:
        return 4
    if straight_m < 7000:
        return 5
    return 6


def _project_t(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """点在线段 ab 上的投影参数 t，0 表示 a，1 表示 b。用于沿线排序。"""
    kx = cos(radians(a[1])) * 111320.0
    ky = 110540.0
    px = (point[0] - a[0]) * kx
    py = (point[1] - a[1]) * ky
    bx = (b[0] - a[0]) * kx
    by = (b[1] - a[1]) * ky
    len2 = bx * bx + by * by
    if len2 == 0:
        return 0.0
    return (px * bx + py * by) / len2


def offset_from_line_m(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """点到起终点连线的最短距离（米）。"""
    kx = cos(radians(a[1])) * 111320.0
    ky = 110540.0
    px = (point[0] - a[0]) * kx
    py = (point[1] - a[1]) * ky
    bx = (b[0] - a[0]) * kx
    by = (b[1] - a[1]) * ky
    len2 = bx * bx + by * by
    if len2 == 0:
        return sqrt(px * px + py * py)
    t = max(0.0, min(1.0, (px * bx + py * by) / len2))
    return sqrt((px - t * bx) ** 2 + (py - t * by) ** 2)


def factor_interest(poi: Poi, tag_order: Sequence[str]) -> float:
    """M 兴趣匹配度：命中标签的权重和 ÷ 全部标签权重和。"""
    total = sum(TAG_WEIGHTS[i] for i in range(len(tag_order)))
    if total == 0:
        return 0.0
    hit = sum(TAG_WEIGHTS[i] for i, tag in enumerate(tag_order) if tag in poi.tag_ids)
    return hit / total


def factor_reachability(poi: Poi, ctx: ScoreContext) -> float:
    """A 可达性：偏离度越小越高。"""
    offset = offset_from_line_m(poi.xy, ctx.origin, ctx.destination)
    return max(0.0, 1.0 - offset / ctx.radius_m)


def factor_heat(poi: Poi) -> float:
    """H 热度：高德评分 ÷ 5，无评分取中值 0.5。"""
    if poi.rating is None:
        return 0.5
    return max(0.0, min(1.0, poi.rating / 5.0))


def factor_time_fit(poi: Poi, ctx: ScoreContext) -> float:
    """T 时长适配：与平均停留时长的相对偏差。"""
    if ctx.avg_stay_minutes <= 0:
        return 0.5
    return max(0.0, 1.0 - abs(poi.stay_minutes - ctx.avg_stay_minutes) / ctx.avg_stay_minutes)


def factor_diversity(poi: Poi, selected: Sequence[Poi]) -> float:
    """V 多样性：与已选点位重复分类码的比例越低越高。"""
    if not selected:
        return 1.0
    same = sum(1 for p in selected if p.typecode == poi.typecode)
    return max(0.0, 1.0 - same / len(selected))


def score_poi(poi: Poi, ctx: ScoreContext, selected: Sequence[Poi] = ()) -> tuple[float, dict[str, float]]:
    """返回 (综合得分, 五因子明细)。明细用于接口的 scoreDetail 字段。"""
    detail = {
        "M": factor_interest(poi, ctx.tag_order),
        "A": factor_reachability(poi, ctx),
        "H": factor_heat(poi),
        "T": factor_time_fit(poi, ctx),
        "V": factor_diversity(poi, selected),
    }
    w = ctx.weights
    score = (
        w["M"] * detail["M"]
        + w["A"] * detail["A"]
        + w["H"] * detail["H"]
        + w["T"] * detail["T"]
        + w["V"] * detail["V"]
    )
    return score, detail


def rank(pois: Sequence[Poi], ctx: ScoreContext) -> list[tuple[Poi, float, dict[str, float]]]:
    """按得分降序排列。同分时按偏离度更小的在前，保证结果确定。"""
    scored = [(p, *score_poi(p, ctx)) for p in pois]
    scored.sort(key=lambda x: (-x[1], -x[2]["A"], x[0].poi_id))
    return scored


def select_waypoints(
    ranked: Sequence[tuple[Poi, float, dict[str, float]]],
    target_n: int,
    min_gap_m: float = 200.0,
    max_same_type: int = 2,
) -> list[Poi]:
    """贪心选取途经点：两两间距 ≥200 米，同分类码不超过 2 个。"""
    chosen: list[Poi] = []
    type_count: dict[str, int] = {}
    for poi, _score, _detail in ranked:
        if len(chosen) >= target_n:
            break
        if any(haversine_m(poi.xy, c.xy) < min_gap_m for c in chosen):
            continue
        if type_count.get(poi.typecode, 0) >= max_same_type:
            continue
        chosen.append(poi)
        type_count[poi.typecode] = type_count.get(poi.typecode, 0) + 1
    return chosen


def order_along_line(
    pois: Sequence[Poi], origin: tuple[float, float], destination: tuple[float, float]
) -> list[Poi]:
    """按沿线投影排序，避免折返。"""
    return sorted(pois, key=lambda p: _project_t(p.xy, origin, destination))


def plan_waypoints(
    pois: Sequence[Poi],
    ctx: ScoreContext,
    target_n: int | None = None,
    min_gap_m: float = 200.0,
    max_same_type: int = 2,
) -> tuple[list[Poi], list[tuple[Poi, float, dict[str, float]]]]:
    """一步到位：排序 → 选取 → 沿线排序。返回 (途经点序列, 完整排名)。"""
    ranked = rank(pois, ctx)
    n = target_n or waypoint_target_count(haversine_m(ctx.origin, ctx.destination))
    chosen = select_waypoints(ranked, n, min_gap_m, max_same_type)
    return order_along_line(chosen, ctx.origin, ctx.destination), ranked
