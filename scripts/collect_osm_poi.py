# -*- coding: utf-8 -*-
"""从 OpenStreetMap（Overpass API）采集武汉三镇点位，产出种子库 CSV。

为什么用 OSM 而不是小红书：
  - OSM 数据为 ODbL 许可，允许抓取与二次使用（需署名），学生项目完全合规
  - 每条记录都有真实坐标，能直接落到地图上
  - 缺点：中文名覆盖不全、无"好不好玩"的主观评价 —— 这部分必须人工补

输出：data/poi_from_osm.csv
坐标：已从 WGS-84 转换到 GCJ-02（高德用），避免点位整体偏移。
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = "citywalk-student-project/0.1 (contact: 2006chunqiu)"

# 武汉主城区大致范围：南,西,北,东
BBOX = (30.35, 114.05, 30.85, 114.65)

# 兴趣标签 → OSM 标签过滤条件
GROUPS: dict[str, list[tuple[str, str]]] = {
    "history": [
        ("historic", "memorial"), ("historic", "monument"), ("historic", "building"),
        ("historic", "ruins"), ("historic", "archaeological_site"), ("heritage", "*"),
        ("building", "church"), ("building", "cathedral"), ("building", "temple"),
    ],
    "park": [
        ("leisure", "park"), ("leisure", "garden"), ("leisure", "nature_reserve"),
    ],
    "art": [
        ("tourism", "museum"), ("tourism", "gallery"), ("amenity", "library"),
        ("shop", "books"), ("amenity", "arts_centre"), ("tourism", "artwork"),
    ],
    "river": [
        ("man_made", "pier"), ("amenity", "ferry_terminal"), ("tourism", "viewpoint"),
        ("man_made", "lighthouse"),
    ],
    "local": [
        ("amenity", "marketplace"), ("shop", "convenience"), ("amenity", "food_court"),
    ],
    "family": [
        ("leisure", "playground"), ("tourism", "zoo"), ("tourism", "aquarium"),
        ("leisure", "water_park"),
    ],
    "food": [
        ("amenity", "cafe"),
    ],
    "photo": [
        ("tourism", "attraction"), ("tourism", "viewpoint"), ("tourism", "artwork"),
    ],
}

# 人工补全时的默认停留时长（分钟）
STAY = {
    "history": 10, "park": 15, "art": 15, "river": 15,
    "local": 10, "family": 15, "food": 20, "photo": 10,
}

# WGS-84 -> GCJ-02
_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lng: float, lat: float) -> bool:
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return round(lng + dlng, 6), round(lat + dlat, 6)


def build_query(key: str, val: str) -> str:
    """单个标签条件一条查询，避免一次查太重被 Overpass 拒绝（502）。"""
    s, w, n, e = BBOX
    if val == "*":
        sel = f'nwr["{key}"]({s},{w},{n},{e});'
    else:
        sel = f'nwr["{key}"="{val}"]({s},{w},{n},{e});'
    return f"[out:json][timeout:120];({sel});out center 300;"


def overpass(query: str, tries: int = 2) -> dict:
    body = ("data=" + urllib.parse.quote(query)).encode()
    last = None
    for attempt in range(tries):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        req = urllib.request.Request(
            url, data=body, headers={"User-Agent": UA, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2)
    raise RuntimeError(f"overpass failed: {last}")


def has_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fa5" for ch in s)


def main() -> None:
    records: dict[tuple[str, str], dict] = {}
    ok = 0
    fail = 0

    for group, filters in GROUPS.items():
        for key, val in filters:
            sys.stderr.write(f"查 {group}/{key}={val} ... ")
            try:
                data = overpass(build_query(key, val))
            except Exception as exc:  # noqa: BLE001
                fail += 1
                sys.stderr.write(f"失败 {exc}\n")
                continue
            ok += 1
            n = 0
            for el in data.get("elements", []):
                tags = el.get("tags") or {}
                name = (tags.get("name:zh") or tags.get("name") or "").strip()
                if not name or not has_cjk(name):
                    continue
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat is None or lon is None:
                    continue
                k = (el.get("type", ""), str(el.get("id", "")))
                if k in records:
                    if group not in records[k]["_groups"]:
                        records[k]["_groups"].append(group)
                    continue
                records[k] = {
                    "name": name,
                    "wgs_lng": lon,
                    "wgs_lat": lat,
                    "osm_type": el.get("type", ""),
                    "osm_id": str(el.get("id", "")),
                    "addr": tags.get("addr:full") or tags.get("addr:street") or "",
                    "typecode": tags.get("tourism") or tags.get("historic") or tags.get("leisure")
                                or tags.get("amenity") or tags.get("shop") or "",
                    "_groups": [group],
                }
                n += 1
            sys.stderr.write(f"{n} 条\n")
            time.sleep(2.5)

    sys.stderr.write(f"查询成功 {ok} 组，失败 {fail} 组\n")
    rows = []
    for i, rec in enumerate(records.values(), start=1):
        groups = rec["_groups"]
        primary = groups[0]
        lng, lat = wgs84_to_gcj02(rec["wgs_lng"], rec["wgs_lat"])
        rows.append({
            "poi_id": f"osm_{i:04d}",
            "name": rec["name"],
            "address": rec["addr"],
            "lng": lng,
            "lat": lat,
            "typecode": rec["typecode"],
            "tag_ids": "|".join(groups),
            "source": "osm",
            "stay_minutes": STAY.get(primary, 10),
            "reason": "",
            "open_time": "",
            "verified_at": "",
            "verified_by": "",
            "status": "待复核",
            "osm_type": rec["osm_type"],
            "osm_id": rec["osm_id"],
            "wgs_lng": rec["wgs_lng"],
            "wgs_lat": rec["wgs_lat"],
        })

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "poi_from_osm.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # 统计
    from collections import Counter
    cnt = Counter(g for r in rows for g in r["tag_ids"].split("|"))
    print(f"写出 {len(rows)} 条 -> {out}")
    print("按标签分布：")
    for k, v in cnt.most_common():
        print(f"  {k:10s} {v}")


if __name__ == "__main__":
    main()

