# -*- coding: utf-8 -*-
"""全量未 FC 清单 = 打过未 FC（118）+ 完全没打过（75）= 193 首。
输出 master_unfc_full.json / master_unfc_full.csv，字段与单条清单一致，并标注 played 状态。
"""
import json
import os
import csv

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

musics = json.load(open(os.path.join(DATA, "cn_master_musics.json"), encoding="utf-8"))
diffs = json.load(open(os.path.join(DATA, "cn_master_musicDifficulties.json"), encoding="utf-8"))
suite = json.load(open(os.path.join(DATA, "user_suite_latest.json"), encoding="utf-8"))

# musicId -> 标题
id2cn, id2jp = {}, {}
for m in musics:
    infos = m.get("infos") or []
    id2cn[m["id"]] = infos[0].get("title", "") if infos and isinstance(infos[0], dict) else ""
    id2jp[m["id"]] = m.get("title", "")

# master 谱面信息
master_diffs = {d["musicId"]: (d["playLevel"], d["totalNoteCount"]) for d in diffs if d["musicDifficulty"] == "master"}

# 打过未 FC（从之前清单）
unfc_played = json.load(open(os.path.join(DATA, "master_unfc_with_p8.json"), encoding="utf-8"))

# 完全没打过
played_master_ids = set(r["musicId"] for r in suite["userMusicResults"] if r["musicDifficultyType"] == "master")
never_played_ids = set(master_diffs.keys()) - played_master_ids

rows = []
for r in unfc_played:
    rows.append({
        "musicId": r["musicId"], "title_cn": r["title_cn"], "title_jp": r["title_jp"],
        "playLevel": r["playLevel"], "noteCount": r["noteCount"],
        "played": True, "highScore": r["highScore"], "nPlays": r.get("nPlays", 0),
        "p8_judge": r.get("p8_judge"), "p8_pseudo": r.get("p8_pseudo"),
        "p8_pseudo_note": r.get("p8_pseudo_note", ""), "noteDensityRank": r.get("noteDensityRank"),
    })
for mid in sorted(never_played_ids):
    lv, nc = master_diffs[mid]
    rows.append({
        "musicId": mid, "title_cn": id2cn.get(mid, ""), "title_jp": id2jp.get(mid, ""),
        "playLevel": lv, "noteCount": nc,
        "played": False, "highScore": 0, "nPlays": 0,
        "p8_judge": None, "p8_pseudo": None, "p8_pseudo_note": "未打过", "noteDensityRank": None,
    })

# 未打过但 pjsekai 有判定的（补 p8）
p8 = json.load(open(os.path.join(DATA, "pjsekai_master_8level.json"), encoding="utf-8"))
p8_map = {r["title_ja"]: r for r in p8}
JUDGE_TO_POS = {"最下位−": 0.00, "最下位": 0.20, "下位": 0.40, "適正": 0.50, "上位": 0.70, "最上位": 0.90, "最上位＋": 0.95}
for r in rows:
    if r["played"]:
        continue
    e = p8_map.get(r["title_jp"])
    if e:
        r["p8_judge"] = e["judge"]
        pos = JUDGE_TO_POS.get(e["judge"])
        r["p8_pseudo"] = round(r["playLevel"] + pos, 2) if pos is not None else None
        r["p8_pseudo_note"] = "" if pos is not None else "判定困難/未定"

rows.sort(key=lambda r: (-r["playLevel"], r["title_cn"] or r["title_jp"]))

n_p8 = sum(1 for r in rows if r["p8_pseudo"] is not None)
print(f"全量未 FC: {len(rows)} 首（打过未FC {sum(1 for r in rows if r['played'])} + 没打过 {sum(1 for r in rows if not r['played'])}）")
print(f"有 p8 判定: {n_p8}, 无: {len(rows) - n_p8}")

with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
with open(os.path.join(DATA, "master_unfc_full.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("已存 master_unfc_full.json / .csv")
from collections import Counter
print("星级分布:", dict(sorted(Counter(r["playLevel"] for r in rows).items())))
