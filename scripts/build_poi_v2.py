# -*- coding: utf-8 -*-
"""把 1377 条种子库转成后端可直接加载的 poi_v2.csv。

转换内容：
  1. 列名对齐 poi_repo 的期望（poi_id/name/lng/lat/typecode/tag_ids/rating/stay_minutes/source/type_name/address）
  2. 标签映射：25 个中文标签词 → 8 个 tagId，再叠加名称规则补 river/photo/family
  3. 用高德 POI 详情接口补 rating / typecode / type_name / address（限速 + 退避）
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

SRC = r"C:\Users\wangl\Documents\xwechat_files\wxid_9pks8joaystq22_ca5c\msg\file\2026-11\种子库(1).csv"
OUT = r"C:\Users\wangl\Documents\deepseek-harness\default-workspace\citywalk\data\poi_v2.csv"
KEY = os.getenv("AMAP_WEB_KEYS", "").split(",")[0]
API = "https://restapi.amap.com/v5/place/detail"

# 标签组合 → tagId（按新库的 14 种组合）
COMBO_MAP: dict[str, list[str]] = {
    "文化|书香": ["art"],
    "自然|风景": ["park"],
    "美食|餐饮": ["food"],
    "市井|购物": ["local"],
    "红色|文博": ["history"],
    "文博|展览": ["art", "history"],
    "休闲|娱乐": ["family"],
    "城市|街区": ["local"],
    "古刹|人文": ["history"],
    "生活|服务": ["local"],
    "城市|其他": [],
    "住宿|休憩": [],
    "生活|医疗": [],
    "交通|出行": [],
}

# 单个标签词 → tagId（组合表没命中时的兜底）
WORD_MAP: dict[str, list[str]] = {
    "文化": ["art"], "书香": ["art"], "文博": ["art", "history"], "展览": ["art", "history"],
    "自然": ["park"], "风景": ["park"], "美食": ["food"], "餐饮": ["food"],
    "市井": ["local"], "购物": ["local"], "街区": ["local"], "服务": ["local"],
    "红色": ["history"], "古刹": ["history"], "人文": ["history"],
    "休闲": ["family"], "娱乐": ["family"],
}

# 名称关键词规则：补 COMBO_MAP 覆盖不到的标签
NAME_RULES: list[tuple[str, list[str]]] = [
    ("river", ["江滩", "长江", "汉江", "码头", "轮渡", "滨江", "江景", "大桥", "渡口", "江畔", "湖滨"]),
    ("photo", ["观景", "天台", "摩天轮", "夜景", "打卡", "灯塔", "桥头", "夜景", "艺术区", "涂鸦", "出片"]),
    ("family", ["儿童", "亲子", "乐园", "动物园", "科技馆", "海洋", "游乐园", "遛娃", "童话"]),
    ("local", ["市场", "菜场", "老街", "里份", "巷", "夜市", "集市"]),
    ("history", ["旧址", "故居", "纪念馆", "纪念碑", "会址", "遗址", "古刹", "寺", "教堂"]),
    ("food", ["咖啡", "茶馆", "餐厅", "小吃", "热干面", "豆皮", "过早", "面馆", "火锅"]),
    ("park", ["公园", "绿道", "湿地", "植物园", "风景区", "山"]),
    ("art", ["书店", "图书馆", "美术馆", "博物馆", "画廊", "艺术", "文创", "剧院"]),
]

# 停留时长（分钟）按首个 tagId
STAY = {"art": 15, "park": 15, "history": 10, "food": 20,
        "river": 15, "local": 10, "photo": 10, "family": 15}


def norm_combo(tag_text: str) -> str:
    parts = [p.strip() for p in re.split(r"[|、]", tag_text) if p.strip()]
    return "|".join(parts)


def map_tags(tag_text: str, name: str) -> list[str]:
    combo = norm_combo(tag_text)
    tags: list[str] = list(COMBO_MAP.get(combo, []))
    if not tags:
        for w in combo.split("|"):
            tags += WORD_MAP.get(w, [])
    for tag, words in NAME_RULES:
        if any(w in name for w in words) and tag not in tags:
            tags.append(tag)
    # 去重保序
    seen: set[str] = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def lookup(pid: str) -> dict | None:
    q = urllib.parse.urlencode({"id": pid, "key": KEY, "output": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "citywalk-import/0.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
    pois = d.get("pois") or []
    return pois[0] if pois else None


def main() -> None:
    if not KEY:
        print("缺少 AMAP_WEB_KEYS")
        sys.exit(1)
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    print(f"源数据 {len(rows)} 条，开始补全字段…")

    out: list[dict] = []
    stat = Counter()
    for i, r in enumerate(rows, 1):
        pid = r["ID"].strip()
        name = r["名称"].strip()
        tags = map_tags(r["标签"], name)

        poi = None
        for attempt in range(4):
            try:
                poi = lookup(pid)
                if poi is None:
                    time.sleep(0.5 + attempt * 0.5)
                    continue
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.4)
        time.sleep(0.42)

        if poi:
            loc = poi.get("location") or ""
            typecode = str(poi.get("typecode") or "")
            type_full = str(poi.get("type") or "")
            biz = poi.get("business") or {}
            rating = biz.get("rating")
            out.append({
                "poi_id": pid,
                "name": poi.get("name") or name,
                "address": poi.get("address") or "",
                "lng": loc.split(",")[0] if "," in loc else r["经度"],
                "lat": loc.split(",")[1] if "," in loc else r["纬度"],
                "typecode": typecode,
                "tag_ids": "|".join(tags),
                "rating": rating if rating not in (None, "", []) else "",
                "stay_minutes": STAY.get(tags[0] if tags else "", 10),
                "source": "seed",
                "type_name": type_full.split(";")[-1] if type_full else "",
                "reason": r["特色"].strip(),
            })
            stat["ok"] += 1
        else:
            out.append({
                "poi_id": pid, "name": name, "address": "",
                "lng": r["经度"], "lat": r["纬度"], "typecode": "",
                "tag_ids": "|".join(tags), "rating": "",
                "stay_minutes": STAY.get(tags[0] if tags else "", 10),
                "source": "seed", "type_name": "", "reason": r["特色"].strip(),
            })
            stat["fallback"] += 1

        if i % 200 == 0:
            print(f"  {i}/{len(rows)}  {dict(stat)}", flush=True)

    fields = ["poi_id", "name", "address", "lng", "lat", "typecode", "tag_ids",
              "rating", "stay_minutes", "source", "type_name", "reason"]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    tag_cnt = Counter(t for row in out for t in row["tag_ids"].split("|") if t)
    rated = sum(1 for r in out if r["rating"] != "")
    print(f"\n完成 -> {OUT}")
    print(f"  总 {len(out)} 条，补全成功 {stat['ok']}，回退 {stat['fallback']}")
    print(f"  有评分 {rated} 条（{rated/len(out)*100:.0f}%）")
    print("  标签分布：", dict(tag_cnt.most_common()))
    empty = sum(1 for r in out if not r["tag_ids"])
    print(f"  空标签 {empty} 条")


if __name__ == "__main__":
    main()
