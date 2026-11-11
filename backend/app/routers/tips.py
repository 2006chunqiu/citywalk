from __future__ import annotations

from fastapi import APIRouter

from ..errors import ApiError
from ..services import amap
from ..services.tags_data import TAG_INDEX

router = APIRouter(prefix="/api", tags=["tips"])


@router.get("/tips")
async def get_tips(keywords: str, city: str = "武汉"):
    if len(keywords.strip()) < 2:
        raise ApiError(400, "INVALID_KEYWORDS", "至少输入 2 个字符")
    try:
        items = await amap.inputtips(keywords.strip(), city)
    except amap.AllKeysExhausted as exc:
        raise ApiError(503, "ALL_KEYS_EXHAUSTED", f"高德 Key 不可用：{exc}") from exc
    except amap.AmapError as exc:
        raise ApiError(502, exc.infocode or "AMAP_ERROR", exc.info or "高德接口调用失败") from exc
    return {"tips": items}


@router.get("/tags")
async def get_tags():
    # 真实实现应读取 tag_mapping 表；此处直接返回常量以便前端联调
    return {"tags": [dict(t, tagIds=[t["tagId"]]) for t in TAG_INDEX.values()]}
