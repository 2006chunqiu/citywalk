"""种子 POI 库：把 data/poi.csv 读成 Poi 对象，供召回层使用。

设计取舍：
- 首次访问读盘，之后走内存缓存；文件很小（几百行），没必要上数据库。
- 文件缺失或格式异常时返回空元组，**不抛异常**。上层 recall / build_schemes
  会退到合成数据，保证演示时页面永远不白。
- 这里不做任何数据清洗，清洗在 scripts/build_poi.py 里完成。脏数据进到这里，
  说明上游脚本的规则要改，不要在这里偷偷过滤。
"""
from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path

from ..algo.scoring import Poi

logger = logging.getLogger(__name__)

# backend/app/services/poi_repo.py -> citywalk/data/poi.csv
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "poi.csv"

FIELDS = (
    "poi_id", "name", "address", "lng", "lat",
    "typecode", "tag_ids", "rating", "stay_minutes", "source", "type_name",
)


def _parse(row: dict[str, str]) -> Poi | None:
    try:
        tag_ids = tuple(t for t in (row.get("tag_ids") or "").split("|") if t)
        rating_raw = (row.get("rating") or "").strip()
        return Poi(
            poi_id=(row.get("poi_id") or "").strip(),
            name=(row.get("name") or "").strip(),
            lng=float(row["lng"]),
            lat=float(row["lat"]),
            typecode=(row.get("typecode") or "").strip(),
            tag_ids=tag_ids,
            rating=float(rating_raw) if rating_raw else None,
            stay_minutes=int(row.get("stay_minutes") or 15),
            source=(row.get("source") or "seed").strip() or "seed",
            type_name=(row.get("type_name") or "").strip(),
            address=(row.get("address") or "").strip(),
        )
    except (KeyError, TypeError, ValueError):
        return None


@lru_cache(maxsize=4)
def _load(path_str: str) -> tuple[Poi, ...]:
    path = Path(path_str)
    if not path.exists():
        logger.warning("种子库不存在：%s，召回将退回合成数据", path)
        return ()
    pois: list[Poi] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            poi = _parse(row)
            if poi is not None and poi.poi_id:
                pois.append(poi)
    logger.info("种子库载入 %d 条：%s", len(pois), path)
    return tuple(pois)


def all_pois(path: Path | str | None = None) -> tuple[Poi, ...]:
    return _load(str(path or DEFAULT_PATH))


def by_tags(tag_ids: tuple[str, ...] | list[str], path: Path | str | None = None) -> list[Poi]:
    wanted = set(tag_ids)
    return [p for p in all_pois(path) if wanted & set(p.tag_ids)]


def stats(path: Path | str | None = None) -> dict:
    pois = all_pois(path)
    counter: dict[str, int] = {}
    for poi in pois:
        for tag in poi.tag_ids:
            counter[tag] = counter.get(tag, 0) + 1
    rated = [p for p in pois if p.rating is not None]
    return {
        "total": len(pois),
        "withRating": len(rated),
        "byTag": dict(sorted(counter.items(), key=lambda x: -x[1])),
        "source": str(path or DEFAULT_PATH),
    }


def reload() -> None:
    """改完 CSV 后调一次，不用重启进程。"""
    _load.cache_clear()
