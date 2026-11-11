from __future__ import annotations

import secrets

from fastapi import APIRouter

from ..errors import ApiError
from ..schemas import ShareRequest
from ..services import store

router = APIRouter(prefix="/api/share", tags=["share"])


@router.post("")
async def create_share(req: ShareRequest):
    if store.get_scheme(req.schemeId) is None:
        raise ApiError(404, "SCHEME_NOT_FOUND", "方案不存在")
    token = secrets.token_urlsafe(16)
    store.create_share(token, req.schemeId)
    return {
        "token": token,
        "url": f"/s/{token}",
        "expireAt": None,  # TODO: 接入 walk_session / share_link 表后返回真实过期时间
    }


@router.get("/{token}")
async def read_share(token: str):
    scheme = store.get_share(token)
    if scheme is None:
        raise ApiError(404, "SHARE_EXPIRED", "链接已失效")
    return scheme
