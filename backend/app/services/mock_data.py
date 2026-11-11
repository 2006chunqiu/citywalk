"""生成三条方案的示例实现。

注意：这里的点位是按起终点连线合成的假数据，仅用于打通前后端。
真实实现应替换为 FR-03-01 的召回（种子库 + 高德周边检索），
打分部分已经可以直接复用 app/algo/scoring.py。
"""
from __future__ import annotations

from ..algo.scoring import (
    MODE_WEIGHTS,
    Poi,
    ScoreContext,
    buffer_radius_m,
    haversine_m,
    plan_waypoints,
    waypoint_target_count,
)

MODE_LABEL = {"shortest": "最短路线", "max": "兴趣最大化", "balanced": "均衡"}

# 分类码与展示名，用于合成候选点
TYPES = [
    ("140400", "书店", ("art",), 15),
    ("050500", "咖啡厅", ("art", "photo"), 20),
    ("110200", "历史建筑", ("history", "photo"), 10),
    ("110100", "公园", ("park", "family"), 15),
    ("140300", "美术馆", ("art", "history"), 15),
    ("050100", "小吃", ("food", "local"), 20),
]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def synthetic_pois(origin: tuple[float, float], destination: tuple[float, float]) -> list[Poi]:
    """沿起终点连线生成固定模式的候选点，保证同输入结果稳定（不引入随机）。"""
    pois: list[Poi] = []
    lng1, lat1 = origin
    lng2, lat2 = destination
    for i in range(1, 11):
        t = i / 11.0
        typecode, type_name, tags, stay = TYPES[i % len(TYPES)]
        side = 1.0 if i % 2 else -1.0
        # 垂直方向的小偏移，让点位不完全落在连线上
        d_lng = _lerp(lng1, lng2, t) + side * 0.0009 * (1 + (i % 3) * 0.4)
        d_lat = _lerp(lat1, lat2, t) + side * 0.0011 * (1 + (i % 2) * 0.5)
        pois.append(
            Poi(
                poi_id=f"demo_{i:02d}",
                name=f"示例{type_name}{chr(64 + i)}",
                lng=round(d_lng, 6),
                lat=round(d_lat, 6),
                typecode=typecode,
                tag_ids=tags,
                rating=None if i % 3 == 0 else round(4.0 + (i % 5) * 0.1, 1),
                stay_minutes=stay,
                source="seed" if i % 2 else "amap",
            )
        )
    return pois


def _reason(mode: str, distance_m: int, base_m: int, count: int) -> str:
    """推荐理由模板：所有数字由后端算好填入，模型不生成数字。"""
    delta_km = round((distance_m - base_m) / 1000, 1)
    if mode == "shortest":
        return f"全程 {distance_m / 1000:.1f} 公里，只绕行 {(distance_m / base_m - 1) * 100:.0f}%，适合时间紧的时候走。"
    if mode == "max":
        return f"兴趣覆盖度最高，{count} 个点位里多数命中你的首选标签，代价是比最短路线多走 {delta_km:.1f} 公里。"
    return f"比最短路线多走 {abs(delta_km):.1f} 公里，但在点位数量与步行强度之间更平衡。"


def build_schemes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    tag_ids: list[str],
    tag_order: list[str] | None = None,
    effort: str = "normal",
) -> dict:
    tag_order = tag_order or tag_ids
    straight = haversine_m(origin, destination)
    radius = buffer_radius_m(straight)
    pois = synthetic_pois(origin, destination)

    base_n = waypoint_target_count(straight)
    if effort == "easy":
        base_n = max(3, base_n - 1)
    elif effort == "deep":
        base_n = min(6, base_n + 1)

    # 三方案的途经点数量差异（对应 PRD 附录 B：最短 3–4、均衡 3–6、兴趣 5–6）
    mode_adj = {"shortest": -1, "balanced": 0, "max": 2}

    base_m = straight * 1.18  # 起终点最短路步行距离的粗略估算
    schemes = []

    for mode in ("shortest", "max", "balanced"):
        target_n = max(3, min(6, base_n + mode_adj[mode]))
        ctx = ScoreContext(
            origin=origin,
            destination=destination,
            tag_order=tag_order,
            radius_m=radius,
            avg_stay_minutes=15.0,
            weights=dict(MODE_WEIGHTS[mode]),
        )
        chosen, ranked = plan_waypoints(pois, ctx, target_n=target_n)
        if not chosen:
            continue

        path = [origin] + [p.xy for p in chosen] + [destination]
        path_m = sum(haversine_m(path[i], path[i + 1]) for i in range(len(path) - 1)) * 1.18
        walk_s = int(path_m / 1.25)
        stay_s = sum(p.stay_minutes for p in chosen) * 60
        distance_m = int(path_m)

        waypoints = []
        prev = origin
        for seq, poi in enumerate(chosen, start=1):
            waypoints.append(
                {
                    "seq": seq,
                    "poiId": poi.poi_id,
                    "amapId": f"MOCK{seq:04d}",
                    "name": poi.name,
                    "address": "示例地址（待替换为种子库数据）",
                    "lng": poi.lng,
                    "lat": poi.lat,
                    "typeName": dict((t[0], t[1]) for t in TYPES)[poi.typecode],
                    "tagIds": list(poi.tag_ids),
                    "stayMinutes": poi.stay_minutes,
                    "rating": poi.rating,
                    "source": poi.source,
                    "distanceFromPrevM": int(haversine_m(prev, poi.xy)),
                }
            )
            prev = poi.xy

        difficulty = "easy" if distance_m < 4000 else ("standard" if distance_m <= 8000 else "deep")

        schemes.append(
            {
                "schemeId": f"s_{mode}_{int(straight)}",
                "mode": mode,
                "distanceM": distance_m,
                "durationS": walk_s + stay_s,
                "walkS": walk_s,
                "stayS": stay_s,
                "waypointCount": len(chosen),
                "detourRatio": round(distance_m / base_m, 2) if base_m else 1.0,
                "difficulty": difficulty,
                "reason": _reason(mode, distance_m, int(base_m), len(chosen)),
                "polyline": [[round(x, 6), round(y, 6)] for x, y in path],
                "waypoints": waypoints,
                "crossing": {"isCrossing": False, "type": None, "distanceM": 0, "extraMinutes": 0},
            }
        )

    return {
        "status": "success" if schemes else "fail",
        "validation": {"passed": True, "dropped": 0, "reasons": []},
        "schemes": schemes,
        "apiCalls": 0,  # 示例实现不调外部接口
    }
