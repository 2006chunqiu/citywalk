from __future__ import annotations

from fastapi import APIRouter

from ..algo.scoring import haversine_m
from ..errors import ApiError
from ..schemas import GenerateRequest, ReplanRequest
from ..services import mock_data, store

router = APIRouter(prefix="/api/route", tags=["route"])

MIN_M = 100.0      # 起终点过近
MAX_M = 15000.0    # 步行距离上限


def _check_distance(origin, destination) -> float:
    straight = haversine_m((origin.lng, origin.lat), (destination.lng, destination.lat))
    if straight < MIN_M:
        raise ApiError(400, "SAME_POINT", "起终点太近，请拉开距离")
    if straight > MAX_M:
        raise ApiError(
            400,
            "INVALID_DISTANCE",
            f"步行距离过长（约 {straight / 1000:.1f} 公里），建议缩短起终点或改乘公共交通",
        )
    return straight


@router.post("/generate")
async def generate(req: GenerateRequest):
    _check_distance(req.origin, req.destination)
    result = mock_data.build_schemes(
        origin=(req.origin.lng, req.origin.lat),
        destination=(req.destination.lng, req.destination.lat),
        tag_ids=req.tagIds,
        tag_order=req.tagOrder or req.tagIds,
        effort=req.effort,
    )
    store.save_result(result)
    return result


@router.post("/replan")
async def replan(req: ReplanRequest):
    _check_distance(req.origin, req.destination)
    result = mock_data.build_schemes(
        origin=(req.origin.lng, req.origin.lat),
        destination=(req.destination.lng, req.destination.lat),
        tag_ids=req.tagIds,
        tag_order=req.tagOrder or req.tagIds,
        effort=req.effort,
    )
    excluded = set(req.excludeIds)
    if excluded:
        # 已到达的点不得再出现在新路线中（PRD R-04-05-3）
        for scheme in result["schemes"]:
            kept = [w for w in scheme["waypoints"] if w["poiId"] not in excluded]
            scheme["waypoints"] = [
                dict(w, seq=i) for i, w in enumerate(kept, start=1)
            ]
            scheme["waypointCount"] = len(kept)
    store.save_result(result)
    return result


@router.get("/{scheme_id}")
async def get_scheme(scheme_id: str):
    scheme = store.get_scheme(scheme_id)
    if scheme is None:
        raise ApiError(404, "SCHEME_NOT_FOUND", "方案不存在或已过期")
    return scheme
