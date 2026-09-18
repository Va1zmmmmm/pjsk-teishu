# -*- coding: utf-8 -*-
"""把 pjsekai.com 日服 8 档分类映射到用户 118 首 MASTER 未 FC（按日文曲名）。"""
import json
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

unfc = json.load(open(os.path.join(DATA, "master_unfc_list.json"), encoding="utf-8"))
p8 = json.load(open(os.path.join(DATA, "pjsekai_master_8level.json"), encoding="utf-8"))
musics = json.load(open(os.path.join(DATA, "cn_master_musics.json"), encoding="utf-8"))

# musicId -> jp title（master 数据里的 title 是日文）
id2jp = {m["id"]: m.get("title", "") for m in musics}
id2cn = {}
for m in musics:
    cn = ""
    infos = m.get("infos") or []
    if infos and isinstance(infos[0], dict):
        cn = infos[0].get("title", "") or ""
    id2cn[m["id"]] = cn

# pjsekai 8 档索引：title_ja -> list of (level, judge)（同一日文曲名可能多级？不，MASTER 每曲一级）
p8_map = {}
for r in p8:
    p8_map.setdefault(r["title_ja"], []).append(r)

# 判定排序（8档 → 序数，用于后续多源合并）
JUDGE_ORDER = ["最下位−", "最下位", "下位", "適正", "上位", "最上位", "最上位＋"]
JUDGE_RANK = {j: i for i, j in enumerate(JUDGE_ORDER)}

matched = 0
unmatched = []
for r in unfc:
    mid = int(r["musicId"])
    jp = id2jp.get(mid, "")
    entries = p8_map.get(jp, [])
    if entries:
        # 取该曲在 MASTER 的判定（entries 里 level 应等于官方星级）
        e = entries[0]
        r["p8_level"] = e["level"]
        r["p8_judge"] = e["judge"]
        r["p8_rank"] = JUDGE_RANK.get(e["judge"], -1)
        matched += 1
    else:
        unmatched.append({"musicId": mid, "title_jp": jp, "title_cn": id2cn.get(mid, "")})

print(f"118 首中匹配到 pjsekai 8 档: {matched}")
print(f"未匹配: {len(unmatched)}")
for u in unmatched:
    print(f"  - {u['title_cn'] or u['title_jp']} (id={u['musicId']})")

# 已匹配的 8 档分布
from collections import Counter
print("\n已匹配的 8 档分布:", dict(Counter(r["p8_judge"] for r in unfc if "p8_judge" in r)))

# 存增强版清单
out = os.path.join(DATA, "master_unfc_with_p8.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)
print("增强版已存:", out)
