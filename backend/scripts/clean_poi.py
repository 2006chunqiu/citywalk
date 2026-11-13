"""离线清洗已有的 data/poi.csv：不联网，只重跑标签规则。

用途：build_poi.py 拉过一次之后，如果发现标签规则有问题（比如"营销中心"被
贴成市井烟火），不用重新拉高德，直接清洗现有 CSV 就行。

规则与 build_poi.py 完全共用，避免两套标准打架。
用法：
    python backend/scripts/clean_poi.py            # 原地清洗
    python backend/scripts/clean_poi.py --dry-run  # 只看会删多少，不写盘
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "poi.csv"

FIELDS = [
    "poi_id", "name", "address", "lng", "lat",
    "typecode", "tag_ids", "rating", "stay_minutes", "source", "type_name",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from build_poi import infer_tags, is_chain, is_junk, stay_minutes

    rows = list(csv.DictReader(CSV_PATH.open("r", encoding="utf-8-sig", newline="")))
    before = len(rows)

    kept: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    dropped = {"连锁": 0, "杂业": 0, "无标签": 0, "重复": 0}

    for row in rows:
        name = row["name"]
        type_name = row.get("type_name") or ""
        if is_chain(name):
            dropped["连锁"] += 1
            continue
        if is_junk(name, type_name):
            dropped["杂业"] += 1
            continue
        tags = infer_tags(name, type_name, row.get("typecode") or "")
        if not tags:
            dropped["无标签"] += 1
            continue
        fingerprint = (name, int(float(row["lng"]) * 2000), int(float(row["lat"]) * 2000))
        if fingerprint in seen:
            dropped["重复"] += 1
            continue
        seen.add(fingerprint)
        row = dict(row)
        row["tag_ids"] = "|".join(tags)
        row["stay_minutes"] = stay_minutes(tags)
        kept.append(row)

    print(f"{before} 条 -> {len(kept)} 条；剔除：{dropped}")
    counter: dict[str, int] = {}
    for row in kept:
        for tag in row["tag_ids"].split("|"):
            counter[tag] = counter.get(tag, 0) + 1
    for tag, n in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {tag:8s} {n:3d}")

    if args.dry_run:
        return 0

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept)
    print(f"已写回 {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
