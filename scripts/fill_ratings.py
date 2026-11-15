# -*- coding: utf-8 -*-
"""只补 poi_v2.csv 的 rating 列（place/detail 必须显式请求 show_fields=business）。"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

CSV = r"C:\Users\wangl\Documents\deepseek-harness\default-workspace\citywalk\data\poi_v2.csv"
KEY = os.getenv("AMAP_WEB_KEYS", "").split(",")[0]
API = "https://restapi.amap.com/v5/place/detail"


def fetch(pid: str) -> dict | None:
    q = urllib.parse.urlencode(
        {"id": pid, "key": KEY, "output": "json", "show_fields": "business"}
    )
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "citywalk-import/0.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
    pois = d.get("pois") or []
    return pois[0] if pois else None


def main() -> None:
    if not KEY:
        print("缺少 AMAP_WEB_KEYS")
        sys.exit(1)
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    print(f"{len(rows)} 条，开始补评分…")

    filled = 0
    for i, row in enumerate(rows, 1):
        poi = None
        for attempt in range(4):
            try:
                poi = fetch(row["poi_id"])
                if poi is None:
                    time.sleep(0.5 + attempt * 0.5)
                    continue
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.4)
        if poi:
            biz = poi.get("business") or {}
            rating = biz.get("rating")
            if rating not in (None, "", []):
                row["rating"] = str(rating)
                filled += 1
            # 顺手补 type_name / 地址（部分点位 detail 才有）
            if not row.get("type_name"):
                row["type_name"] = str(poi.get("type") or "").split(";")[-1]
            if not row.get("address"):
                row["address"] = poi.get("address") or ""
        time.sleep(0.42)
        if i % 200 == 0:
            print(f"  {i}/{len(rows)} 已填 {filled}", flush=True)

    fields = list(rows[0].keys())
    with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"\n完成：{filled}/{len(rows)} 条有评分（{filled/len(rows)*100:.0f}%）")


if __name__ == "__main__":
    main()
