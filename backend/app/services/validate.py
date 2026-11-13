"""校验层：输出前对途经点做最后一次守门（PRD FR-03-04 / 防 AI 幻觉）。

三道检查：
1. 坐标范围：必须落在武汉 bbox 内（lng 113.7~114.6 / lat 30.2~30.9）
2. 去重：同一条方案里同一个 poiId 只保留一次
3. 来源白名单：只允许 amap / seed / keyword / hot，出现其他来源说明数据管线被污染

校验不通过的点直接剔除，结果写入 validation 字段，前端与答辩都能解释
"每个点位都是有据可查的"。
"""
from __future__ import annotations

LNG_MIN, LNG_MAX = 113.7, 114.6
LAT_MIN, LAT_MAX = 30.2, 30.9
ALLOWED_SOURCES = {"amap", "seed", "keyword", "hot"}
MAX_REASONS = 10


def validate_schemes(result: dict) -> dict:
    dropped = 0
    reasons: list[str] = []

    for scheme in result.get("schemes") or []:
        kept = []
        seen: set[str] = set()
        for waypoint in scheme.get("waypoints") or []:
            lng, lat = waypoint["lng"], waypoint["lat"]
            if not (LNG_MIN <= lng <= LNG_MAX and LAT_MIN <= lat <= LAT_MAX):
                dropped += 1
                reasons.append(f"越界:{waypoint['name']}")
                continue

            poi_id = waypoint.get("poiId") or waypoint.get("name")
            if poi_id in seen:
                dropped += 1
                reasons.append(f"重复:{waypoint['name']}")
                continue
            seen.add(poi_id)

            source = waypoint.get("source")
            if source not in ALLOWED_SOURCES:
                dropped += 1
                reasons.append(f"来源异常:{source}")
                continue

            kept.append(waypoint)

        for seq, waypoint in enumerate(kept, start=1):
            waypoint["seq"] = seq
        scheme["waypoints"] = kept
        scheme["waypointCount"] = len(kept)

    result["schemes"] = [s for s in (result.get("schemes") or []) if s["waypoints"]]
    if not result["schemes"]:
        result["status"] = "fail"

    result["validation"] = {
        "passed": dropped == 0,
        "dropped": dropped,
        "reasons": reasons[:MAX_REASONS],
    }
    return result
