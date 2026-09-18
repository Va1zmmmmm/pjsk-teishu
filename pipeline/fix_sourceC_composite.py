# -*- coding: utf-8 -*-
"""
源C 修复 v2（审查后）：
  旧：源C = 同星级纯物量排名（noteDensityRank）→ 物量小的魔王曲被低估（37级黑暗火锅 NPS 最高却排最低）
  新：源C = 同星级「物量排名 + NPS密度排名」均值（各50%）——物量=总容错/体力，NPS=单位操作强度
  并重算所有曲目的 noteDensityRank 为复合值。
外网经验依据：PJSK 谱面难度看密度不看纯物量（高 NPS 才是硬指标），但长曲物量也带来持续高压
"""
import json
import os
from collections import defaultdict

DATA = r"C:\Users\Liz\Desktop\bot\cc\pjsk\data"
unfc = json.load(open(os.path.join(DATA, "master_unfc_full.json"), encoding="utf-8"))


def rank_within(group, keyfn, reverse=False):
    """给 group 里每个元素在同组内的排名（0~1）。reverse=True 时值越大 rank 越高。"""
    valid = [r for r in group if keyfn(r) is not None]
    if len(valid) < 2:
        return {id(r): 0.5 for r in group}
    s = sorted(valid, key=lambda r: keyfn(r), reverse=reverse)
    n = len(s)
    res = {}
    for i, r in enumerate(s):
        res[id(r)] = i / (n - 1)
    return res


by_lv = defaultdict(list)
for r in unfc:
    by_lv[r["playLevel"]].append(r)

for lv, group in by_lv.items():
    note_rank = rank_within(group, lambda r: r["noteCount"], reverse=True)
    nps_rank = rank_within(group, lambda r: r.get("nps"), reverse=True)
    for r in group:
        n_r = note_rank.get(id(r), 0.5)
        p_r = nps_rank.get(id(r), 0.5)
        r["noteDensityRank"] = round((n_r + p_r) / 2, 2)  # 复合：物量+NPS 各半
        r["noteRank"] = round(n_r, 2)
        r["npsRank"] = round(p_r, 2)

with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)

print("=== 修复后 37 级（复合源C）===")
for lv in [37, 36]:
    sub = sorted([r for r in unfc if r["playLevel"] == lv], key=lambda r: -r["noteDensityRank"])
    for r in sub:
        print(f"  复合rank{r['noteDensityRank']:.2f} (物量rank{r.get('noteRank'):.2f}+NPSrank{r.get('npsRank'):.2f}) BPM{r.get('bpm_lo')}-{r.get('bpm_hi')} NPS{r.get('nps')} {r['title_cn'] or r['title_jp']}")
