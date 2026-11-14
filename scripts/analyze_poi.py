# -*- coding: utf-8 -*-
"""分析采集到的 OSM 点位，产出可用于种子库建设的归纳报告。

用法：
    python scripts/analyze_poi.py

输出：
    data/POI采集报告.md
"""
from __future__ import annotations

import csv
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_IN = os.path.join(HERE, "data", "poi_from_osm.csv")
MD_OUT = os.path.join(HERE, "data", "POI采集报告.md")

TAG_CN = {
    "history": "历史建筑",
    "park": "公园绿地",
    "art": "文艺",
    "river": "江景滨江",
    "local": "市井烟火",
    "family": "亲子友好",
    "food": "美食小吃",
    "photo": "拍照出片",
}

# 武汉主城区经纬度大致范围（GCJ-02）
LNG_RANGE = (114.00, 114.70)
LAT_RANGE = (30.30, 30.90)


def load() -> list[dict]:
    with open(CSV_IN, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows = load()
    total = len(rows)

    tag_count: Counter = Counter()
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        tags = [t for t in r["tag_ids"].split("|") if t]
        for t in tags:
            tag_count[t] += 1
        if tags:
            by_tag[tags[0]].append(r)

    # 数据质量
    oob = []
    no_addr = 0
    name_len = []
    dup_names: Counter = Counter()
    for r in rows:
        try:
            lng, lat = float(r["lng"]), float(r["lat"])
        except ValueError:
            oob.append(r["name"])
            continue
        if not (LNG_RANGE[0] <= lng <= LNG_RANGE[1] and LAT_RANGE[0] <= lat <= LAT_RANGE[1]):
            oob.append(r["name"])
        if not r["address"].strip():
            no_addr += 1
        name_len.append(len(r["name"]))
        dup_names[r["name"]] += 1
    dups = [(n, c) for n, c in dup_names.most_common(10) if c > 1]

    lines: list[str] = []
    add = lines.append

    add("# 武汉三镇点位采集报告")
    add("")
    add("> 数据来源：OpenStreetMap（Overpass API），ODbL 许可，可自由使用与二次加工，"
        "署名即可。采集脚本见 `scripts/collect_osm_poi.py`。")
    add("")
    add("## 一、总体情况")
    add("")
    add(f"- 采集点位：**{total} 条**")
    add(f"- 覆盖标签：{len(tag_count)} 类")
    add(f"- 地址缺失：{no_addr} 条（{no_addr / total * 100:.0f}%）——需要补全")
    add(f"- 坐标越界（不在武汉范围）：{len(oob)} 条")
    add(f"- 名称长度：最短 {min(name_len)} 字，最长 {max(name_len)} 字，"
        f"平均 {sum(name_len) / len(name_len):.1f} 字")
    add("")
    add("## 二、按兴趣标签分布")
    add("")
    add("| 标签 | 代码 | 点位数 | 占比 |")
    add("|---|---|---|---|")
    for tag, cnt in tag_count.most_common():
        add(f"| {TAG_CN.get(tag, tag)} | `{tag}` | {cnt} | {cnt / total * 100:.1f}% |")
    add("")

    add("## 三、各标签样例（每类最多 8 条）")
    add("")
    for tag, items in by_tag.items():
        add(f"### {TAG_CN.get(tag, tag)}（{len(items)} 条）")
        add("")
        add("| 名称 | 经纬度 | 地址 | 默认停留 |")
        add("|---|---|---|---|")
        for r in items[:8]:
            addr = r["address"] or "—"
            add(f"| {r['name']} | {r['lng']}, {r['lat']} | {addr} | {r['stay_minutes']} 分钟 |")
        add("")

    if dups:
        add("## 四、重名点位（需人工区分）")
        add("")
        add("| 名称 | 出现次数 |")
        add("|---|---|")
        for n, c in dups:
            add(f"| {n} | {c} |")
        add("")

    add("## 五、这份数据能直接用吗")
    add("")
    add("**可以直接用的字段**：名称、坐标（已转 GCJ-02）、类别、OSM 溯源 ID。")
    add("")
    add("**必须人工补齐的字段**：")
    add("")
    add("| 字段 | 为什么必须人工 | 怎么补 |")
    add("|---|---|---|")
    add("| `address` | 缺失率高，OSM 不强制填 | 高德逆地理编码按坐标反查 |")
    add("| `reason` | OSM 没有“值不值得走一趟”的评价 | 写一句话入选理由 |")
    add("| `stay_minutes` | 现在是按类别的默认值 | 按实际参观点位修正 |")
    add("| `open_time` | OSM 覆盖不全 | 高德 POI 详情的 `business.opentime` |")
    add("| `tag_ids` | OSM 标签是功能分类，不含“文艺”“出片” | 人工判断，或按关键词规则初筛 |")
    add("| `verified_*` | 无 | 逐点在高德地图按名称搜索核验 |")
    add("")
    add("## 六、与本项目的适配建议")
    add("")
    add("1. **不要直接用 OSM 标签当兴趣标签**。OSM 的 `tourism=museum` 只说明它是博物馆，"
        "不说明它“适合拍照”。兴趣标签必须人工判断后写入 `tag_ids`。")
    add("2. **地址一律用高德逆地理补**。OSM 的地址字段在武汉覆盖率很低，"
        "而我们的分享页与卡片都要展示地址。")
    add("3. **坐标已经是 GCJ-02**，可直接入库；但入库前建议用高德"
        "「坐标转换」或 POI 搜索抽样比对 3–5 个点位，确认没有整体偏移。")
    add("4. **优先使用“历史建筑”与“公园绿地”两类**。这两类 OSM 覆盖最好、"
        "且客观属性强（是不是文保单位、是不是公园），人工判断成本最低。")
    add("5. **“美食小吃”“市井烟火”靠 OSM 不可行**。这类点位需要真实的店名与营业状态，"
        "OSM 覆盖率低且更新慢，必须用高德 POI 检索 + 人工筛选。")
    add("")
    add("## 七、建议的补全流程")
    add("")
    add("1. 按标签分层抽样，每类先挑 20 个候选（合计约 160）")
    add("2. 在高德地图里逐点搜名称，确认存在、地址正确、仍在营业")
    add("3. 写 `reason`（一句话）、修正 `stay_minutes`、填入 `tag_ids`")
    add("4. 填 `verified_by` 与 `verified_at`，`status` 从“待复核”改为“有效”")
    add("5. 未通过核验的置为“已关闭”，不参与召回")
    add("")

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"写出报告 -> {MD_OUT}")
    print(f"点位总数 {total}，标签 {len(tag_count)} 类，地址缺失 {no_addr} 条，越界 {len(oob)} 条")
    for tag, cnt in tag_count.most_common():
        print(f"  {TAG_CN.get(tag, tag):8s} {cnt}")


if __name__ == "__main__":
    main()
