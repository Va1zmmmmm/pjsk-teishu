# -*- coding: utf-8 -*-
"""审查准备：计算 NPS（note/秒）密度 + 速度变化标记，写入清单。"""
import json
import os
import re

DATA = r"C:\Users\Liz\Desktop\bot\cc\pjsk\data"
unfc = json.load(open(os.path.join(DATA, "master_unfc_full.json"), encoding="utf-8"))


def dur_to_sec(d):
    if not d:
        return None
    m = re.match(r"(\d+):(\d+)", str(d))
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


for r in unfc:
    sec = dur_to_sec(r.get("duration"))
    if sec and sec > 0:
        r["nps"] = round(r["noteCount"] / sec, 2)
    else:
        r["nps"] = None

# 同星级内 NPS 密度排名（更科学的"物量密度"）
from collections import defaultdict
by_lv = defaultdict(list)
for r in unfc:
    by_lv[r["playLevel"]].append(r)
for lv, group in by_lv.items():
    valid = [r for r in group if r["nps"]]
    if len(valid) < 2:
        for r in group:
            r["nps_rank"] = 0.5 if r["nps"] else None
        continue
    sorted_nps = sorted(valid, key=lambda r: r["nps"])
    n = len(sorted_nps)
    for r in valid:
        idx = sorted_nps.index(r)
        r["nps_rank"] = round(idx / (n - 1), 2)

with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)

# 报告
n_nps = sum(1 for r in unfc if r["nps"])
n_var = sum(1 for r in unfc if r.get("bpm_var"))
print(f"NPS 覆盖: {n_nps}/{len(unfc)}, 速度变化谱: {n_var} 首")
print("\n=== 各星级 NPS 最高（同星级最密）前几首 ===")
for lv in [30, 31, 32, 33, 34, 35]:
    sub = [r for r in unfc if r["playLevel"] == lv and r["nps"]]
    sub.sort(key=lambda r: -r["nps"])
    if sub:
        top3 = sub[:3]
        print(f"Lv{lv}: " + " | ".join(f"{r['title_cn'] or r['title_jp']}({r['nps']}/s,{r['noteCount']}n,{r.get('bpm_hi')}bpm)" for r in top3))
