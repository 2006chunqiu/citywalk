# -*- coding: utf-8 -*-
"""分析种子库核验明细：统计 PASS / NOT_FOUND 的分布特征。"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else r"data\种子库核验明细.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))

nf = [r for r in rows if r["判定"] == "NOT_FOUND"]
ok = [r for r in rows if r["判定"] == "PASS"]
other = [r for r in rows if r["判定"] not in ("PASS", "NOT_FOUND")]

print(f"总 {len(rows)}   PASS {len(ok)}   NOT_FOUND {len(nf)}   其他 {len(other)}")
print()

print("--- NOT_FOUND 的标签分布 ---")
c = Counter()
for r in nf:
    for t in re.split(r"[|、,，/]", r["标签"]):
        t = t.strip()
        if t:
            c[t] += 1
for k, v in c.most_common(12):
    print(f"  {k:8s} {v}")

print()
print("--- NOT_FOUND 名称里的关键词 ---")
kw = Counter()
keys = ["图书馆", "市场", "咖啡", "书店", "公园", "纪念馆", "旧址", "中心", "广场", "店", "学校", "大学"]
for r in nf:
    for k in keys:
        if k in r["名称"]:
            kw[k] += 1
for k, v in kw.most_common():
    print(f"  {k:6s} {v}")

print()
print("--- NOT_FOUND 样例（前 15 条）---")
for r in nf[:15]:
    print(f"  {r['名称'][:28]:<30} {r['ID']}")

print()
print("--- 对比：PASS 里也含这些关键词的比例 ---")
ok_kw = Counter()
for r in ok:
    for k in keys:
        if k in r["名称"]:
            ok_kw[k] += 1
for k in keys:
    a, b = kw.get(k, 0), ok_kw.get(k, 0)
    if a or b:
        total = a + b
        print(f"  {k:6s} NOT_FOUND {a:4d} / 合计 {total:4d} = {a/total*100:5.1f}%")
