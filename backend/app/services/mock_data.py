"""生成三条方案的组装层。

点位来源优先走种子库召回（services/recall.py），种子库为空或走廊内无候选时
退回 synthetic_pois() 的合成点，保证接口永远有结果。打分与编排全部复用
app/algo/scoring.py，本模块只负责"取点 -> 拼成接口要的形状"。
"""
from __future__ import annotations

import logging

from ..algo.scoring import (
    MODE_WEIGHTS,
    Poi,
    ScoreContext,
    buffer_radius_m,
    haversine_m,
    plan_waypoints,
    waypoint_target_count,
)
from .recall import recall

logger = logging.getLogger(__name__)

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

# 真 POI 拿不到 type_name 时的兜底，避免 KeyError
TYPE_NAMES = {code: name for code, name, _tags, _stay in TYPES}


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


# 约束求解的两个参数。用"绕行容忍度"而不是绝对米数——起终点本身可能有 4 公里，
# 绝对预算会把路程全吃掉，最后只剩一个点，那就不是"路线推荐"了。
# 单段上限对应 PRD 里写的"单段步行 ≤ 2km"。
MODE_DETOUR_LIMIT = {"shortest": 1.12, "balanced": 1.30, "max": 1.65}
MODE_LEG_LIMIT_M = {"shortest": 1800, "balanced": 2000, "max": 3000}
EFFORT_FACTOR = {"easy": 0.95, "normal": 1.0, "deep": 1.08}
# 三档最少保留点数必须拉开，否则裁完之后三条方案会长得一模一样
MODE_MIN_KEEP = {"shortest": 2, "balanced": 3, "max": 4}

# 接入真实路径规划前，用"直线 × 1.18"估步行距离（1.18 是城区绕行经验值）
DETOUR_FACTOR = 1.18


def _legs_m(points: list[Poi], origin: tuple[float, float], destination: tuple[float, float]) -> list[float]:
    seq = [origin, *(p.xy for p in points), destination]
    return [haversine_m(seq[i], seq[i + 1]) * DETOUR_FACTOR for i in range(len(seq) - 1)]


def _path_m(points: list[Poi], origin: tuple[float, float], destination: tuple[float, float]) -> float:
    return sum(_legs_m(points, origin, destination))


def _budget_m(effort: str, mode: str, straight_m: float) -> float:
    """总步行预算 = 直达距离 × 绕行容忍度 × 体力系数。"""
    limit = MODE_DETOUR_LIMIT.get(mode, 1.4) * EFFORT_FACTOR.get(effort, 1.0)
    return straight_m * DETOUR_FACTOR * limit


def _fit_budget(
    points: list[Poi],
    origin: tuple[float, float],
    destination: tuple[float, float],
    budget_m: float,
    leg_limit_m: float,
    scores: dict[str, float],
    min_keep: int = 3,
) -> list[Poi]:
    """同时压两个约束：总步行距离 ≤ 预算，任意单段 ≤ 单段上限。

    每次删掉"删掉之后省得最多"的那个；并列时删得分低的。
    于是保下来的是"顺路又有兴趣"的点，先被砍掉的是"专程绕过去"的点。
    最少保留 min_keep 个——宁可略微超预算，也不给用户一条只有一个点的"路线"。
    """
    kept = list(points)
    while len(kept) > min_keep:
        total = _path_m(kept, origin, destination)
        legs = _legs_m(kept, origin, destination)
        if total <= budget_m and max(legs) <= leg_limit_m:
            break
        best_i, best_gain, best_score = None, -1.0, 0.0
        for i in range(len(kept)):
            trial = kept[:i] + kept[i + 1:]
            gain = total - _path_m(trial, origin, destination)
            score = scores.get(kept[i].poi_id, 0.0)
            if gain > best_gain or (gain == best_gain and score < best_score):
                best_i, best_gain, best_score = i, gain, score
        if best_i is None:
            break
        kept.pop(best_i)
    return kept


def build_schemes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    tag_ids: list[str],
    tag_order: list[str] | None = None,
    effort: str = "normal",
) -> dict:
    tag_order = tag_order or tag_ids
    straight = haversine_m(origin, destination)

    recalled = recall(origin, destination, list(tag_order))
    pois = list(recalled.pois)
    if not pois:
        logger.warning(
            "走廊内无候选（种子库 %d 条），本次退回合成点位：%s -> %s",
            recalled.scanned, origin, destination,
        )
        pois = synthetic_pois(origin, destination)
    radius = recalled.radius_m or buffer_radius_m(straight)

    base_n = waypoint_target_count(straight)
    if effort == "easy":
        base_n = max(3, base_n - 1)
    elif effort == "deep":
        base_n = min(6, base_n + 1)

    # 三方案的途经点数量差异（对应 PRD 附录 B：最短 3–4、均衡 3–6、兴趣 5–6）
    mode_adj = {"shortest": -1, "balanced": 0, "max": 2}

    base_m = straight * DETOUR_FACTOR  # 起终点最短路步行距离的粗略估算
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

        # 约束求解：总步行距离 + 单段距离双约束（PRD FR-03-03）
        scores = {p.poi_id: s for p, s, _detail in ranked}
        budget = _budget_m(effort, mode, straight)
        leg_limit = MODE_LEG_LIMIT_M.get(mode, 2200) * EFFORT_FACTOR.get(effort, 1.0)
        fitted = _fit_budget(
            chosen, origin, destination, budget, leg_limit, scores,
            min_keep=MODE_MIN_KEEP.get(mode, 3),
        )
        if len(fitted) < len(chosen):
            logger.info(
                "%s 方案触发约束：%.0fm/%.0fm 预算、最长段 %.0fm/%.0fm，途经点 %d -> %d",
                mode, _path_m(chosen, origin, destination), budget,
                max(_legs_m(chosen, origin, destination)), leg_limit,
                len(chosen), len(fitted),
            )
        chosen = fitted

        path = [origin] + [p.xy for p in chosen] + [destination]
        path_m = _path_m(chosen, origin, destination)
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
                    # 高德 POI id 以 B0 开头；合成点和无 id 的样本给 null，前端显示「—」
                    "amapId": poi.poi_id if poi.poi_id.startswith("B0") else None,
                    "name": poi.name,
                    "address": poi.address or "",
                    "lng": poi.lng,
                    "lat": poi.lat,
                    "typeName": poi.type_name or TYPE_NAMES.get(poi.typecode, "城市点位"),
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
