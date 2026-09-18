# -*- coding: utf-8 -*-
"""从合并 CSV 抽取 MASTER 未 FC 清单（工程锚点）。"""
import csv
import os
import json

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

with open(os.path.join(DATA, "user_results_all_latest.csv"), encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

master_nofc = [r for r in rows if r["difficulty"] == "master" and r["fc"] != "True"]
for r in master_nofc:
    r["musicId"] = int(r["musicId"])
    r["playLevel"] = int(r["playLevel"])
    r["noteCount"] = int(r["noteCount"])
    r["highScore"] = int(r["highScore"])
    r["nPlays"] = int(r["nPlays"])
master_nofc.sort(key=lambda r: -(r["playLevel"] or 0))

print(f"MASTER 未 FC: {len(master_nofc)} 首")
from collections import Counter
print("官方星级分布:", dict(sorted(Counter(r["playLevel"] for r in master_nofc).items())))

# 存 JSON（供后续管线用）
out = os.path.join(DATA, "master_unfc_list.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(master_nofc, f, ensure_ascii=False, indent=1)
print("已存:", out)

# 存 CSV（给人看）
out_csv = os.path.join(DATA, "master_unfc_118.csv")
with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["musicId", "title_cn", "title_jp", "playLevel", "noteCount", "highScore", "bestResult", "nPlays"])
    w.writeheader()
    for r in master_nofc:
        w.writerow({k: r.get(k, "") for k in w.fieldnames})
print("已存:", out_csv)
