# -*- coding: utf-8 -*-
"""种子库坐标合理性筛查（不需要高德 Key）。

三路交叉，只找"明显离谱"的记录，不做精细判定：
  A. 地标锚点：名称里含某个知名地标，但坐标离它 > 3km
  B. 行政区词：名称里含某区名，但坐标不在该区的大致范围内
  C. 同名多点：同名记录之间相距 > 2km（可能是连锁，也可能是错录）
  D. 空间孤立：1km 内没有任何其他点（主城区内出现孤立点，多半坐标有问题）

用法：
    python scripts/audit_coords.py --csv "种子库.csv"
输出：
    终端摘要 + 同目录 `坐标可疑清单.csv`
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import Counter, defaultdict
from math import asin, cos, radians, sin, sqrt

EARTH_R = 6378137.0

# 知名地标锚点（GCJ-02，手工标定，容差 3km）
LANDMARKS: dict[str, tuple[float, float]] = {
    "武汉大学": (114.3608, 30.5387),
    "华中科技": (114.4220, 30.5130),
    "华中师范": (114.3640, 30.5170),
    "黄鹤楼": (114.3025, 30.5442),
    "东湖": (114.3560, 30.5580),
    "江汉路": (114.2895, 30.5818),
    "汉口江滩": (114.2980, 30.5900),
    "武昌站": (114.3210, 30.5300),
    "武昌火车站": (114.3210, 30.5300),
    "汉口站": (114.2550, 30.6200),
    "武汉站": (114.4250, 30.6070),
    "归元寺": (114.2560, 30.5480),
    "晴川阁": (114.2810, 30.5560),
    "户部巷": (114.3038, 30.5481),
    "昙华林": (114.3165, 30.5497),
    "楚河汉街": (114.3250, 30.5570),
    "光谷广场": (114.4000, 30.5070),
    "天河机场": (114.2080, 30.7840),
    "古德寺": (114.3090, 30.6100),
    "宝通寺": (114.3350, 30.5340),
    "汉口里": (114.2450, 30.5820),
    "中山公园": (114.2750, 30.5850),
    "解放公园": (114.2950, 30.6080),
    "沙湖": (114.3280, 30.5720),
}

# 行政区大致范围（GCJ-02，粗框，只用于抓"名字写这个区、坐标在另一个区"的情况）
DISTRICTS: dict[str, tuple[float, float, float, float]] = {
    # 名称关键词: (lng_min, lng_max, lat_min, lat_max)
    "武昌": (114.28, 114.40, 30.50, 30.58),
    "汉口": (114.24, 114.36, 30.56, 30.66),
    "汉阳": (114.18, 114.30, 30.50, 30.58),
    "青山": (114.37, 114.48, 30.57, 30.67),
    "洪山": (114.30, 114.58, 30.42, 30.58),
    "江夏": (114.15, 114.50, 30.15, 30.45),
    "黄陂": (114.20, 114.65, 30.72, 31.30),
    "新洲": (114.55, 115.05, 30.55, 31.00),
    "蔡甸": (113.90, 114.18, 30.28, 30.56),
    "东西湖": (114.05, 114.26, 30.60, 30.76),
    "汉南": (113.95, 114.18, 30.14, 30.36),
}

LANDMARK_TOL_M = 3000.0
SAME_NAME_TOL_M = 2000.0
ISOLATE_RADIUS_M = 1000.0
# 主城区框：只有落在这个框里的孤立点才提示
CORE = (114.20, 114.50, 30.45, 30.66)


def hav(a: tuple[float, float], b: tuple[float, float]) -> float:
    lng1, lat1 = a
    lng2, lat2 = b
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    h = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_R * asin(sqrt(h))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    data = []
    for r in rows:
        try:
            data.append({
                "id": r["ID"].strip(),
                "name": r["名称"].strip(),
                "lng": float(r["经度"]),
                "lat": float(r["纬度"]),
                "tags": r.get("标签", ""),
            })
        except (KeyError, ValueError):
            continue

    issues: list[dict] = []
    seen_id: set[str] = set()

    def add(r: dict, kind: str, detail: str, dist: float | None = None) -> None:
        key = r["id"] + "|" + kind
        if key in seen_id:
            return
        seen_id.add(key)
        issues.append({
            "ID": r["id"], "名称": r["name"], "类型": kind,
            "说明": detail, "距离米": None if dist is None else int(dist),
            "经度": r["lng"], "纬度": r["lat"], "标签": r["tags"],
        })

    # A. 地标锚点
    for r in data:
        for kw, anchor in LANDMARKS.items():
            if kw in r["name"]:
                d = hav((r["lng"], r["lat"]), anchor)
                if d > LANDMARK_TOL_M:
                    add(r, "A-地标偏离", f"名称含「{kw}」，但距该地标 {d/1000:.1f} 公里", d)
                break  # 只按第一个命中的地标判

    # B. 行政区词
    for r in data:
        for kw, (x1, x2, y1, y2) in DISTRICTS.items():
            if kw in r["name"]:
                if not (x1 <= r["lng"] <= x2 and y1 <= r["lat"] <= y2):
                    add(r, "B-行政区不符", f"名称含「{kw}」，但坐标不在该区大致范围内")
                break

    # C. 同名多点
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in data:
        by_name[r["name"]].append(r)
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        base = group[0]
        for other in group[1:]:
            d = hav((base["lng"], base["lat"]), (other["lng"], other["lat"]))
            if d > SAME_NAME_TOL_M:
                add(other, "C-同名远离", f"同名「{name}」相距 {d/1000:.1f} 公里", d)

    # D. 空间孤立（主城区内）
    for r in data:
        if not (CORE[0] <= r["lng"] <= CORE[1] and CORE[2] <= r["lat"] <= CORE[3]):
            continue
        near = sum(
            1 for o in data
            if o is not r and abs(o["lng"] - r["lng"]) < 0.02 and abs(o["lat"] - r["lat"]) < 0.02
            and hav((r["lng"], r["lat"]), (o["lng"], o["lat"])) < ISOLATE_RADIUS_M
        )
        if near == 0:
            add(r, "D-空间孤立", "主城区内 1 公里无任何其他点位")

    # 输出
    out = os.path.join(os.path.dirname(os.path.abspath(args.csv)), "坐标可疑清单.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ID", "名称", "类型", "说明", "距离米", "经度", "纬度", "标签"])
        w.writeheader()
        w.writerows(issues)

    kind_cnt = Counter(i["类型"] for i in issues)
    flagged = len({i["ID"] for i in issues})
    print("=" * 58)
    print(f"总条数：{len(data)}")
    print(f"可疑条数：{flagged}（{flagged/len(data)*100:.1f}%）")
    print("-" * 58)
    for k, v in kind_cnt.most_common():
        print(f"  {k:12s} {v}")
    print("\n最严重的 15 条：")
    worst = sorted(issues, key=lambda x: -(x["距离米"] or 0))[:15]
    for i in worst:
        d = f"{i['距离米']}m" if i["距离米"] is not None else "—"
        print(f"  [{i['类型']}] {i['名称'][:22]:<24} {d:>7}  {i['说明'][:40]}")
    print(f"\n清单已写出：{out}")


if __name__ == "__main__":
    main()
