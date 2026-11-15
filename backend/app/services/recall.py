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

    给"高德通道"用：补点应该沿走廊撒，而不是以起点为圆心画一个大圆，
    否则会捞一堆要绕远路的点。
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


async def recall_amap(
    origin: tuple[float, float],
    destination: tuple[float, float],
    tag_ids: list[str] | tuple[str, ...],
) -> tuple[list[Poi], dict]:
    """通道 A：沿走廊调高德周边检索，补种子库覆盖不到的点（多为大景点）。

    调用量固定上限：parts × max_pages = 3 × 2 = 6 次。
    任何异常都返回空列表，由调用方降级为纯种子库，不中断整次生成。
    """
    from ..config import settings
    from . import amap as amap_api
    from .tags_data import TAG_INDEX

    meta: dict = {"enabled": settings.recall_amap_enabled, "calls": 0, "matched": 0}
    if not settings.recall_amap_enabled:
        return [], meta

    codes = sorted({c for t in tag_ids if t in TAG_INDEX for c in TAG_INDEX[t]["typecodes"]})
    if not codes:
        meta["reason"] = "no_typecode"
        return [], meta
    types = "|".join(codes)

    straight = haversine_m(origin, destination)
    radius = int(min(3000.0, max(800.0, buffer_radius_m(straight) * 1.2)))

    # 种子库里已有的点，绝不再从高德通道重复进来（人工标注优先）
    existing = {p.poi_id for p in poi_repo.all_pois()}

    out: list[Poi] = []
    for center in corridor_centers(origin, destination, settings.recall_amap_parts):
        for page in range(1, settings.recall_amap_max_pages + 1):
            try:
                items = await amap_api.place_around(
                    center[0], center[1], types, radius=radius, page_num=page
                )
            except Exception as exc:  # noqa: BLE001 - 任何异常都降级，不阻断生成
                logger.warning("高德召回失败 center=%s page=%d: %s", center, page, exc)
                break
            meta["calls"] += 1
            if not items:
                break
            for it in items:
                pid = (it.get("amapId") or "").strip()
                if not pid or pid in existing:
                    continue
                existing.add(pid)
                out.append(
                    Poi(
                        poi_id=pid,
                        name=(it.get("name") or "").strip(),
                        lng=it["lng"],
                        lat=it["lat"],
                        typecode=it.get("typecode") or "",
                        tag_ids=tuple(tag_ids[:1]),
                        rating=it.get("rating"),
                        stay_minutes=10,
                        source="amap",
                        type_name=it.get("typeName") or "",
                        address=it.get("address") or "",
                    )
                )
            if len(items) < 25:  # 该中心点已无更多
                break

    meta["matched"] = len(out)
    logger.info("高德通道：半径 %dm，调用 %d 次，新增 %d 条", radius, meta["calls"], len(out))
    return out, meta


async def recall_both(
    origin: tuple[float, float],
    destination: tuple[float, float],
    tag_ids: list[str] | tuple[str, ...],
) -> tuple[list[Poi], "RecallResult", dict]:
    """双线并行：种子库（同步） + 高德（异步），合并去重后返回。

    合并规则：种子库优先。同一个 POI ID 两边都有时，保留种子库那条，
    因为它带有人工标签、入选理由与停留时长。
    """
    seed_result = recall(origin, destination, tag_ids)
    amap_pois, amap_meta = await recall_amap(origin, destination, tag_ids)

    merged = list(seed_result.pois)
    seen = {p.poi_id for p in merged}
    for poi in amap_pois:
        if poi.poi_id not in seen:
            merged.append(poi)
            seen.add(poi.poi_id)

    meta = {
        "seed": len(seed_result.pois),
        "amap": len(amap_pois),
        "merged": len(merged),
        "amapCalls": amap_meta.get("calls", 0),
        "amapEnabled": amap_meta.get("enabled", False),
        "radiusM": round(seed_result.radius_m, 0),
        "widened": seed_result.widened,
    }
    logger.info(
        "融合召回：seed=%d amap=%d merged=%d 调用=%d",
        meta["seed"], meta["amap"], meta["merged"], meta["amapCalls"],
    )
    return merged, seed_result, meta
