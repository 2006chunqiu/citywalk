"""从高德拉取武汉 POI，生成 data/poi.csv（种子库）。

字段与 app/algo/scoring.Poi 对齐，columns:
    poi_id,name,address,lng,lat,typecode,tag_ids,rating,stay_minutes,source,type_name

用法：
    # 1) 用自己的高德 Web 服务 Key（推荐，配额算自己的）
    export AMAP_WEB_KEYS=你的key
    python backend/scripts/build_poi.py

    # 2) 暂时没有 Key：走团队已部署的代理（只读，注意别把配额打满）
    python backend/scripts/build_poi.py --base https://wuhan-citywalk.netlify.app/api/amapgeo

设计约束（对齐方案 4.(7) 防 AI 幻觉）：
    本脚本输出的每一个名称、地址、坐标、分类码都直接来自高德返回，
    不做任何改写、不补任何"想当然"的点位。锚点坐标也走地理编码拿，
    脚本里不手写经纬度。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "poi.csv"

# 扫街锚点：只写地名，坐标一律用地理编码解析
ANCHORS = [
    "昙华林",
    "粮道街",
    "黄鹤楼",
    "首义广场",
    "楚河汉街",
    "武汉大学",
    "江汉路步行街",
    "黎黄陂路",
    "汉口江滩",
    "吉庆街",
    "归元寺",
    "汉阳造艺术区",
    "东湖梨园",
    "青山江滩",
]

# 标签 -> 高德分类码（与 app/services/tags_data.py 保持一致）
TAG_TYPECODES = {
    "art": ["140400", "140300", "050500"],
    "park": ["110100", "110200"],
    "history": ["110200", "140200"],
    "food": ["050100", "050300", "050700"],
    "river": ["110200"],
    "local": ["120000", "070000"],
    "photo": [],
    "family": ["110100", "140500", "140100"],
}

# 稀疏标签补搜：周边检索捞不到的点，用关键词搜一遍（打上的标签是人工指定的）
SWEEP = {
    "local": ["菜市场", "花鸟市场", "老街", "过早", "夜市"],
    "photo": ["观景台", "涂鸦", "天台", "长江大桥"],
    "history": ["旧址", "故居", "会馆", "教堂", "洋行"],
}
SWEEP_MIN = 18  # 某标签少于这个数就补搜

# 连锁品牌不进种子库：City Walk 要的是能停下来看的独立小店
CHAIN_BLACKLIST = (
    "瑞幸", "星巴克", "COTTI", "库迪", "蜜雪冰城", "喜茶", "奈雪的茶",
    "茶百道", "古茗", "沪上阿姨", "幸运咖", "益禾堂", "华莱士",
    "肯德基", "麦当劳", "德克士", "汉堡王", "必胜客", "7-ELEVEn", "Today",
)

# 明显不是"能走进去看的点"的业态词，直接从种子库剔除
JUNK_WORDS = (
    "营销中心", "售楼", "纹眉", "美甲", "美发", "理发", "美容", "整形",
    "口腔", "牙科", "药房", "银行", "营业厅", "中介", "洗衣", "干洗",
    "宠物医院", "快印", "图文", "五金", "建材", "招聘", "公司",
    # 高德会把会展中心/写字楼挂到 140300（美术馆）这类码下，靠业态词兜住
    "会展中心", "会议中心", "写字楼", "商务中心", "产业园", "停车场",
    "加油站", "充电站", "售票处", "出入口", "存包", "服务台", "检票",
)

# 关键词优先于分类码：高德的 110200 同时是公园/名胜/老建筑，只看码会串味
# 注意：这里刻意不用"广场""公馆"这类宽词，它们会把商场和住宅楼盘带进来
KEYWORD_TAGS = [
    ("river", ("江滩", "码头", "轮渡", "江景", "滨江", "长江", "汉江")),
    ("history", ("旧址", "故居", "遗址", "纪念馆", "会馆", "教堂", "洋行", "里份", "红楼", "起义", "辛亥")),
    ("park", ("公园", "绿道", "湿地", "植物园", "湖滨", "草坪")),
    ("local", ("菜市场", "花鸟市场", "老街", "里份", "巷子", "过早", "夜市")),
    ("art", ("书店", "书局", "美术馆", "画廊", "艺术", "咖啡", "文创")),
    ("food", ("小吃", "热干面", "豆皮", "面馆", "烧烤", "米粉", "过早", "夜市", "汤包", "糊汤")),
    ("family", ("博物馆", "科技馆", "少儿", "亲子", "动物园", "游乐", "图书城")),
    ("photo", ("观景", "天台", "涂鸦", "打卡", "大桥")),
]

# 分类码兜底：只在关键词没命中时使用。
# 刻意不收 120000 / 070000——那两个码里全是写字楼、营销中心、美容店。
TYPECODE_TAGS = {
    "140400": ("art",),
    "140300": ("art",),
    "050500": ("art",),
    "140500": ("family",),
    "140100": ("family",),
    "110100": ("park", "family"),
    "110200": ("park",),
    "140200": ("history",),
    "050100": ("food",),
    "050300": ("food",),
    "050700": ("food",),
}

# 停留时长（分钟）：按标签给一个体面的估计，不是精确值
STAY_BY_TAG = {
    "art": 25,
    "park": 30,
    "history": 20,
    "food": 20,
    "river": 25,
    "local": 20,
    "photo": 15,
    "family": 40,
}

BBOX = (113.70, 114.70, 30.20, 30.90)  # 武汉主城大致范围，越界的点丢弃


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call(base: str, path: str, params: dict, key: str | None) -> dict:
    query = dict(params)
    if key:
        query["key"] = key
    query.setdefault("output", "json")
    url = f"{base.rstrip('/')}{path}?{urllib.parse.urlencode(query)}"
    try:
        return _get(url)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 请求失败 {path}: {exc}", file=sys.stderr)
        return {}


def in_bbox(lng: float, lat: float) -> bool:
    min_lng, max_lng, min_lat, max_lat = BBOX
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat


def geocode(base: str, key: str | None, name: str) -> tuple[float, float] | None:
    """地名 -> 坐标。只用高德返回的第一个武汉境内结果。"""
    data = call(base, "/v3/geocode/geo", {"address": name, "city": "武汉"}, key)
    for item in data.get("geocodes") or []:
        loc = item.get("location") or ""
        if "," not in loc:
            continue
        lng, lat = (float(x) for x in loc.split(",")[:2])
        if in_bbox(lng, lat):
            return lng, lat
    return None


def around(base: str, key: str | None, lng: float, lat: float, types: str, radius: int) -> list[dict]:
    data = call(
        base,
        "/v3/place/around",
        {
            "location": f"{lng:.6f},{lat:.6f}",
            "types": types,
            "radius": str(radius),
            "offset": "25",
            "page": "1",
            "extensions": "all",
        },
        key,
    )
    return data.get("pois") or []


def text_search(base: str, key: str | None, keywords: str, page: int = 1) -> list[dict]:
    data = call(
        base,
        "/v3/place/text",
        {
            "keywords": keywords,
            "city": "武汉",
            "citylimit": "true",
            "offset": "25",
            "page": str(page),
            "extensions": "all",
        },
        key,
    )
    return data.get("pois") or []


def infer_tags(name: str, type_str: str, typecode: str) -> tuple[str, ...]:
    """先看名称/类型关键词，再退回分类码。"""
    haystack = f"{name} {type_str}"
    tags: list[str] = []
    for tag, words in KEYWORD_TAGS:
        if any(w in haystack for w in words):
            tags.append(tag)
    if not tags:
        tags.extend(TYPECODE_TAGS.get(typecode, ()))
    return tuple(dict.fromkeys(tags))


def stay_minutes(tags: tuple[str, ...]) -> int:
    if not tags:
        return 15
    return max(STAY_BY_TAG.get(t, 15) for t in tags)


def is_chain(name: str) -> bool:
    return any(brand.lower() in name.lower() for brand in CHAIN_BLACKLIST)


def is_junk(name: str, type_str: str) -> bool:
    haystack = f"{name} {type_str}"
    return any(w in haystack for w in JUNK_WORDS)


def normalize(poi: dict, forced_tag: str | None = None) -> dict | None:
    """把一条高德原始 POI 洗成 CSV 行；不合法返回 None。"""
    loc = poi.get("location") or ""
    if "," not in loc:
        return None
    lng, lat = (float(x) for x in loc.split(",")[:2])
    if not in_bbox(lng, lat):
        return None
    name = (poi.get("name") or "").strip()
    if not name or is_chain(name):
        return None
    type_str = poi.get("type") or ""
    if is_junk(name, type_str):
        return None
    typecode = (poi.get("typecode") or "").split("|")[0]
    tags = list(infer_tags(name, type_str, typecode))
    if forced_tag and forced_tag not in tags:
        tags.append(forced_tag)
    if not tags:
        return None
    biz = poi.get("biz_ext") or {}
    rating_raw = biz.get("rating")
    try:
        rating = float(rating_raw) if rating_raw not in (None, "", []) else None
    except (TypeError, ValueError):
        rating = None
    return {
        "poi_id": poi.get("id") or f"{name}_{lng:.5f}_{lat:.5f}",
        "name": name,
        "address": poi.get("address") or "",
        "lng": round(lng, 6),
        "lat": round(lat, 6),
        "typecode": typecode,
        "tag_ids": "|".join(dict.fromkeys(tags)),
        "rating": "" if rating is None else round(rating, 1),
        "stay_minutes": stay_minutes(tuple(tags)),
        "source": "seed",
        "type_name": type_str.split(";")[-1] if type_str else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://restapi.amap.com", help="高德基址，或团队代理地址")
    ap.add_argument("--key", default=None, help="高德 Web 服务 Key；默认读环境变量 AMAP_WEB_KEYS 的第一个")
    ap.add_argument("--radius", type=int, default=2200)
    ap.add_argument("--sleep", type=float, default=0.15, help="每次请求间隔，避免触发并发限制")
    ap.add_argument("--max", type=int, default=240, help="最终保留条数上限")
    args = ap.parse_args()

    key = args.key
    if key is None:
        keys = [x.strip() for x in (os.getenv("AMAP_WEB_KEYS") or "").split(",") if x.strip()]
        key = keys[0] if keys else None
    if key is None and "netlify" not in args.base and "amapgeo" not in args.base:
        print("缺少 Key：请设置 AMAP_WEB_KEYS，或改用 --base 指向团队代理", file=sys.stderr)
        return 2

    collected: dict[str, dict] = {}

    def add(raw: dict, forced_tag: str | None = None) -> bool:
        row = normalize(raw, forced_tag)
        if row is None or row["poi_id"] in collected:
            return False
        collected[row["poi_id"]] = row
        return True

    print(f"基准地址：{args.base}")
    print(f"锚点 {len(ANCHORS)} 个，标签 {len(TAG_TYPECODES)} 组\n")

    for anchor in ANCHORS:
        center = geocode(args.base, key, anchor)
        time.sleep(args.sleep)
        if center is None:
            print(f"- {anchor}: 地理编码失败，跳过")
            continue
        lng, lat = center
        hit = 0
        for codes in TAG_TYPECODES.values():
            if not codes:
                continue
            for poi in around(args.base, key, lng, lat, "|".join(codes), args.radius):
                if add(poi):
                    hit += 1
            time.sleep(args.sleep)
        print(f"- {anchor} ({lng:.4f},{lat:.4f}): +{hit}")

    # 稀疏标签补搜：关键词检索，打上指定标签
    counter: dict[str, int] = {}
    for row in collected.values():
        for tag in row["tag_ids"].split("|"):
            counter[tag] = counter.get(tag, 0) + 1

    thin = {t: n for t, n in counter.items() if n < SWEEP_MIN}
    thin.update({t: 0 for t in SWEEP if t not in counter})
    if thin:
        print(f"\n补搜稀疏标签：{thin}")
    for tag in SWEEP:
        if counter.get(tag, 0) >= SWEEP_MIN:
            continue
        gained = 0
        for kw in SWEEP[tag]:
            for page in (1, 2):
                for poi in text_search(args.base, key, kw, page):
                    if add(poi, forced_tag=tag):
                        gained += 1
                time.sleep(args.sleep)
        print(f"- 补搜 {tag}: +{gained}")

    rows = list(collected.values())
    # 同名同址去重：同一店铺多个录入的常见形态
    seen: set[tuple[str, int, int]] = set()
    deduped: list[dict] = []
    for row in rows:
        fingerprint = (row["name"], int(row["lng"] * 2000), int(row["lat"] * 2000))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(row)

    # 排序：命中标签多的优先，其次评分高的；再按标签配额保证每个标签都有量
    deduped.sort(key=lambda r: (-len(r["tag_ids"].split("|")), -(r["rating"] or 3.0), r["name"]))
    kept: list[dict] = []
    kept_ids: set[str] = set()
    per_tag_cap = max(12, args.max // 8)
    per_tag: dict[str, int] = {}
    # 第一轮：每个标签先保底
    for row in deduped:
        if len(kept) >= args.max:
            break
        tags = row["tag_ids"].split("|")
        if all(per_tag.get(t, 0) >= per_tag_cap for t in tags):
            continue
        kept.append(row)
        kept_ids.add(row["poi_id"])
        for t in tags:
            per_tag[t] = per_tag.get(t, 0) + 1
    # 第二轮：剩下的按顺序补满
    for row in deduped:
        if len(kept) >= args.max:
            break
        if row["poi_id"] in kept_ids:
            continue
        kept.append(row)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "poi_id", "name", "address", "lng", "lat",
        "typecode", "tag_ids", "rating", "stay_minutes", "source", "type_name",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\n写入 {OUT} 共 {len(kept)} 条")
    counter = {}
    for row in kept:
        for tag in row["tag_ids"].split("|"):
            counter[tag] = counter.get(tag, 0) + 1
    for tag, n in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {tag:8s} {n:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
