"""走廊召回：从种子库里捞出起终点连线附近的候选点。

对应 PRD FR-03-01（候选召回）。打分与选取不在这里做，全部交给
app/algo/scoring.py，保持"召回只看空间和标签、打分只看质量"的分工。

召回规则：
1. 只想命中用户标签的点（标签取交集，不是全等）。
2. 只保留落在走廊带内的点：到起终点连线的最短距离 ≤ 缓冲区半径。
   缓冲区半径复用 scoring.buffer_radius_m()，不另设一套公式。
3. 离起终点太近的点不算途经点（出门就走过去，不叫"逛"）。
4. 同名点位只留离走廊最近的一个（连锁/多录入的常见形态）。
5. 候选太少时，把半径放大一次再捞，而不是放宽标签——宁可路绕一点，
   也不要把用户没兴趣的点塞给他。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..algo.scoring import Poi, buffer_radius_m, haversine_m, offset_from_line_m
from . import poi_repo

logger = logging.getLogger(__name__)

MIN_NEAR_ENDPOINT_M = 120.0   # 距起终点小于这个距离不作为途经点
WIDEN_FACTOR = 1.6            # 候选不足时半径放大倍数
WIDEN_MAX_M = 3000.0          # 放大后的上限，再大就不像"顺路"了
MIN_REQUIRED = 12             # 少于这个数就触发放大


@dataclass
class RecallResult:
    pois: list[Poi] = field(default_factory=list)
    radius_m: float = 0.0
    scanned: int = 0          # 种子库总条数
    tag_matched: int = 0      # 命中标签的条数（未过空间过滤）
    matched: int = 0          # 最终进入候选池的条数
    widened: bool = False
    tags: tuple[str, ...] = ()

    def summary(self) -> dict:
        return {
            "radiusM": round(self.radius_m, 1),
            "scanned": self.scanned,
            "tagMatched": self.tag_matched,
            "matched": self.matched,
            "widened": self.widened,
            "tags": list(self.tags),
        }


def _dedupe_by_name(items: list[tuple[float, Poi]]) -> list[tuple[float, Poi]]:
    """同名点位只留离走廊最近的一个。输入已按距离升序。"""
    seen: set[str] = set()
    out: list[tuple[float, Poi]] = []
    for offset, poi in items:
        key = poi.name
        if key in seen:
            continue
        seen.add(key)
        out.append((offset, poi))
    return out


def recall(
    origin: tuple[float, float],
    destination: tuple[float, float],
    tag_ids: list[str] | tuple[str, ...],
    *,
    limit: int = 60,
    min_required: int = MIN_REQUIRED,
) -> RecallResult:
    """返回走廊内的候选点。不调外部接口，纯本地计算。"""
    tags = tuple(dict.fromkeys(tag_ids))
    pool = poi_repo.all_pois()
    result = RecallResult(scanned=len(pool), tags=tags)

    if not pool or not tags:
        return result

    straight = haversine_m(origin, destination)
    radius = buffer_radius_m(straight)
    wanted = set(tags)

    def collect(r: float) -> list[tuple[float, Poi]]:
        hits: list[tuple[float, Poi]] = []
        for poi in pool:
            if not wanted & set(poi.tag_ids):
                continue
            offset = offset_from_line_m(poi.xy, origin, destination)
            if offset > r:
                continue
            if haversine_m(poi.xy, origin) < MIN_NEAR_ENDPOINT_M:
                continue
            if haversine_m(poi.xy, destination) < MIN_NEAR_ENDPOINT_M:
                continue
            hits.append((offset, poi))
        return hits

    tag_matched = sum(1 for p in pool if wanted & set(p.tag_ids))
    result.tag_matched = tag_matched

    hits = collect(radius)
    if len(hits) < min_required and radius < WIDEN_MAX_M:
        wider = min(radius * WIDEN_FACTOR, WIDEN_MAX_M)
        if wider > radius:
            logger.info("候选 %d 条不足，缓冲区 %.0fm -> %.0fm", len(hits), radius, wider)
            radius = wider
            hits = collect(radius)
            result.widened = True

    hits.sort(key=lambda x: x[0])
    hits = _dedupe_by_name(hits)

    result.radius_m = radius
    result.pois = [poi for _offset, poi in hits[:limit]]
    result.matched = len(hits)
    logger.info(
        "召回完成：库 %d 条 / 命中标签 %d 条 / 走廊内 %d 条 / 返回 %d 条（半径 %.0fm）",
        result.scanned, tag_matched, result.matched, len(result.pois), radius,
    )
    return result


def corridor_centers(
    origin: tuple[float, float], destination: tuple[float, float], parts: int = 3
) -> list[tuple[float, float]]:
    """把起终点连线等分成若干段，返回每段中点。

    留给后续"种子库覆盖不足时调高德周边检索补点"用：补点应该沿走廊撒，
    而不是以起点为圆心画一个大圆，否则会捞一堆要绕远路的点。
    """
    if parts < 1:
        return []
    points: list[tuple[float, float]] = []
    for i in range(parts):
        t = (i + 0.5) / parts
        points.append(
            (
                origin[0] + (destination[0] - origin[0]) * t,
                origin[1] + (destination[1] - origin[1]) * t,
            )
        )
    return points
