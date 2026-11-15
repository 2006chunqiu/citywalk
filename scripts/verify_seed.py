# -*- coding: utf-8 -*-
"""种子库真实性核验。

用法：
    # 只做本地结构审计（不需要 Key）
    python scripts/verify_seed.py --csv "<种子库.csv>"

    # 同时调用高德 POI 详情接口逐条核验（需要「Web服务」类型的 Key）
    set AMAP_WEB_KEYS=你的key
    python scripts/verify_seed.py --csv "<种子库.csv>" --api

判定口径（--api 模式）：
    PASS        名称一致（或互相包含）且坐标偏差 ≤200 米
    OFFSET      名称一致但坐标偏差 >200 米
    NAME_DIFF   按 ID 查到的点位名称不一致（ID 指错或数据串行）
    NOT_FOUND   高德查不到该 ID（点位已下线或 ID 有误）
    ERROR       网络/配额错误，未能判定

输出：
    终端摘要 + 同目录 `核验明细.csv`
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from math import asin, cos, radians, sin, sqrt

EARTH_R = 6378137.0
API = "https://restapi.amap.com/v5/place/detail"
ID_RE = re.compile(r"^B0[A-Z0-9]{8,10}$")
LNG_RANGE = (113.7, 115.1)
LAT_RANGE = (29.9, 31.4)


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lng1, lat1 = a
    lng2, lat2 = b
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    h = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_R * asin(sqrt(h))


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({
            "id": (r.get("ID") or "").strip(),
            "name": (r.get("名称") or "").strip(),
            "lng": float((r.get("经度") or "0").strip() or 0),
            "lat": float((r.get("纬度") or "0").strip() or 0),
            "tags": (r.get("标签") or "").strip(),
            "desc": (r.get("特色") or "").strip(),
        })
    return out


def local_audit(rows: list[dict]) -> dict:
    ids = [r["id"] for r in rows]
    names = [r["name"] for r in rows]
    bad_id = [r for r in rows if not ID_RE.match(r["id"])]
    oob = [
        r for r in rows
        if not (LNG_RANGE[0] <= r["lng"] <= LNG_RANGE[1] and LAT_RANGE[0] <= r["lat"] <= LAT_RANGE[1])
    ]
    tag_counter: Counter = Counter()
    for r in rows:
        for t in re.split(r"[|、,，/]", r["tags"]):
            t = t.strip()
            if t:
                tag_counter[t] += 1
    desc_len = [len(r["desc"]) for r in rows if r["desc"]]
    desc_dup = Counter(r["desc"] for r in rows if r["desc"])
    return {
        "total": len(rows),
        "bad_id": bad_id,
        "dup_id": [k for k, c in Counter(ids).items() if c > 1],
        "dup_name": [(k, c) for k, c in Counter(names).most_common() if c > 1],
        "oob": oob,
        "no_desc": sum(1 for r in rows if not r["desc"]),
        "desc_len_avg": (sum(desc_len) / len(desc_len)) if desc_len else 0,
        "desc_dup": [(k, c) for k, c in desc_dup.most_common(5) if c > 1],
        "tags": tag_counter,
    }


def api_lookup(poi_id: str, key: str, timeout: float = 10.0) -> tuple[dict | None, str]:
    q = urllib.parse.urlencode({"id": poi_id, "key": key, "output": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "citywalk-verify/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if str(data.get("status")) != "1":
        return None, str(data.get("infocode", ""))
    pois = data.get("pois") or []
    return (pois[0] if pois else None), "10000"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--api", action="store_true", help="调用高德接口逐条核验")
    ap.add_argument("--delay", type=float, default=0.08, help="每次请求间隔秒")
    args = ap.parse_args()

    rows = read_csv(args.csv)
    audit = local_audit(rows)

    print("=" * 60)
    print(f"种子库：{args.csv}")
    print(f"总条数：{audit['total']}")
    print("-" * 60)
    print("【本地审计】")
    print(f"  ID 格式异常：      {len(audit['bad_id'])}")
    print(f"  重复 ID：          {len(audit['dup_id'])}")
    print(f"  重复名称：         {len(audit['dup_name'])} 组")
    print(f"  坐标越界：         {len(audit['oob'])}")
    print(f"  缺少特色文案：     {audit['no_desc']}")
    print(f"  特色文案平均长度： {audit['desc_len_avg']:.1f} 字")
    print("  标签分布：" + "，".join(f"{k}({v})" for k, v in audit["tags"].most_common(12)))

    if not args.api:
        print("\n未加 --api，跳过接口核验。")
        print("要逐条核验请先配置「Web服务」类型的 Key：")
        print('  $env:AMAP_WEB_KEYS="你的key"; python scripts/verify_seed.py --csv ... --api')
        return

    keys = [k.strip() for k in os.getenv("AMAP_WEB_KEYS", "").split(",") if k.strip()]
    if not keys:
        print("\n[错误] 未设置 AMAP_WEB_KEYS")
        sys.exit(1)
    key = keys[0]

    print("\n【接口核验】开始逐条查询...")
    verdicts: list[dict] = []
    stat: Counter = Counter()
    for i, r in enumerate(rows, 1):
        verdict, api_name, dist, rating, infocode = "ERROR", "", None, None, ""
        for attempt in range(4):
            try:
                poi, code = api_lookup(r["id"], key)
                infocode = code
                if code == "10044":            # QPS 超限
                    time.sleep(0.6)
                    continue
                if poi is None:
                    # 高德限流时会返回 status=1 但 pois 为空，不报错误码。
                    # 因此空结果不能直接判 NOT_FOUND，必须退避重试。
                    if attempt < 3:
                        time.sleep(0.5 + attempt * 0.5)
                        continue
                    verdict = "NOT_FOUND"
                else:
                    api_name = poi.get("name", "")
                    loc = poi.get("location") or ""
                    biz = poi.get("business") or {}
                    rating = biz.get("rating")
                    if "," in loc:
                        a_lng, a_lat = (float(x) for x in loc.split(",")[:2])
                        dist = haversine((r["lng"], r["lat"]), (a_lng, a_lat))
                    same = (api_name == r["name"]) or (api_name and (api_name in r["name"] or r["name"] in api_name))
                    if not same:
                        verdict = "NAME_DIFF"
                    elif dist is not None and dist > 200:
                        verdict = "OFFSET"
                    else:
                        verdict = "PASS"
                break
            except Exception as exc:  # noqa: BLE001
                infocode = f"EXC {exc}"
                time.sleep(0.4)
        stat[verdict] += 1
        verdicts.append({
            "ID": r["id"], "名称": r["name"], "判定": verdict,
            "高德名称": api_name, "偏差米": None if dist is None else int(dist),
            "高德评分": rating, "infocode": infocode,
            "经度": r["lng"], "纬度": r["lat"], "标签": r["tags"],
        })
        if i % 100 == 0:
            print(f"  已核验 {i}/{len(rows)} ... 当前 {dict(stat)}")
        time.sleep(args.delay)

    out_csv = os.path.join(os.path.dirname(os.path.abspath(args.csv)), "核验明细.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(verdicts[0].keys()))
        w.writeheader()
        w.writerows(verdicts)

    total = len(rows)
    print("\n" + "=" * 60)
    print("【核验结果】")
    for k in ("PASS", "OFFSET", "NAME_DIFF", "NOT_FOUND", "ERROR"):
        if stat.get(k):
            print(f"  {k:11s} {stat[k]:5d}  {stat[k] / total * 100:5.1f}%")
    print(f"\n明细已写出：{out_csv}")


if __name__ == "__main__":
    main()
