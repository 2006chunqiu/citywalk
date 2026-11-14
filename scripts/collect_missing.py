# -*- coding: utf-8 -*-
"""补采缺失的标签（默认补 park），追加进已有 CSV，按 OSM ID 去重。

用法：
    python scripts/collect_missing.py park
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collect_osm_poi import (  # noqa: E402
    BBOX, STAY, UA, OVERPASS_MIRRORS, has_cjk, wgs84_to_gcj02,
)

FILTERS = {
    "park": [("leisure", "park"), ("leisure", "garden"), ("leisure", "dog_park"),
             ("leisure", "pitch"), ("landuse", "recreation_ground")],
    "river": [("tourism", "viewpoint"), ("natural", "water"), ("man_made", "bridge")],
    "photo": [("tourism", "artwork"), ("man_made", "tower"), ("amenity", "theatre")],
}


def query(key: str, val: str) -> dict:
    s, w, n, e = BBOX
    q = f'[out:json][timeout:180];nwr["{key}"="{val}"]({s},{w},{n},{e});out center 400;'
    body = ("data=" + urllib.parse.quote(q)).encode()
    last = None
    for i in range(4):
        url = OVERPASS_MIRRORS[i % len(OVERPASS_MIRRORS)]
        req = urllib.request.Request(
            url, data=body, headers={"User-Agent": UA, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(3)
    raise RuntimeError(str(last))


def main() -> None:
    group = sys.argv[1] if len(sys.argv) > 1 else "park"
    if group not in FILTERS:
        raise SystemExit(f"未知分组 {group}，可选 {list(FILTERS)}")

    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "poi_from_osm.csv")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    existing_ids = {r["osm_id"] for r in rows}
    existing_names = {r["name"] for r in rows}
    print(f"已有 {len(rows)} 条，开始补采 {group}")

    added = 0
    for key, val in FILTERS[group]:
        try:
            data = query(key, val)
        except Exception as exc:  # noqa: BLE001
            print(f"  {key}={val} 失败: {exc}")
            continue
        n = 0
        for el in data.get("elements", []):
            tags = el.get("tags") or {}
            name = (tags.get("name:zh") or tags.get("name") or "").strip()
            if not name or not has_cjk(name):
                continue
            oid = str(el.get("id", ""))
            if oid in existing_ids or name in existing_names:
                continue
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            lng02, lat02 = wgs84_to_gcj02(lon, lat)
            rows.append({
                "poi_id": f"osm_{len(rows) + 1:04d}",
                "name": name,
                "address": tags.get("addr:full") or tags.get("addr:street") or "",
                "lng": lng02,
                "lat": lat02,
                "typecode": tags.get("leisure") or tags.get("tourism") or tags.get("key") or "",
                "tag_ids": group,
                "source": "osm",
                "stay_minutes": STAY.get(group, 15),
                "reason": "",
                "open_time": "",
                "verified_at": "",
                "verified_by": "",
                "status": "待复核",
                "osm_type": el.get("type", ""),
                "osm_id": oid,
                "wgs_lng": lon,
                "wgs_lat": lat,
            })
            existing_ids.add(oid)
            existing_names.add(name)
            n += 1
            added += 1
        print(f"  {key}={val} 新增 {n} 条")
        time.sleep(2)

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"完成，新增 {added} 条，总计 {len(rows)} 条")


if __name__ == "__main__":
    main()
