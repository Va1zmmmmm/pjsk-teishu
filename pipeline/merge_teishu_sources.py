# -*- coding: utf-8 -*-
"""
多源定数合并器 v2（修正独立源口径）：
  社区源（真正独立）：
    源A: B站「Project 个人差」FC 参考定数（src1_bili_teishu）
    源B: pjsekai.com 8 档 → 伪定数（p8_pseudo）
  自定数补充（非社区源，仅当 A/B 都缺时兜底）：
    源C: 物量密度 → 伪定数（noteDensityRank）
合并规则：
  - final_teishu = 社区源（A+B）的均值；社区源≥2 → 高可信；社区源=1 → 中可信；
    A+B 全缺 → 用 C 兜底并标「自定数」；全缺 → None
  - personal_diff: 社区源 A/B 均存在且差 ≥0.6 → ⚠️
"""
import json
import os
import statistics

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

unfc = json.load(open(os.path.join(DATA, "master_unfc_full.json"), encoding="utf-8"))

def srcC(r):
    """源C（审查后 v2）：复合排名 = 同星级内 (物量排名 + NPS密度排名)/2 → 档位 0.2~0.9
    外网经验：难度看密度(NPS)不看纯物量，但长曲物量=持续高压，两者各半。"""
    rank = r.get("noteDensityRank")
    if rank is None:
        return None
    pos = 0.2 + rank * 0.7
    return round(r["playLevel"] + pos, 2)

for r in unfc:
    A = r.get("src1_bili_teishu")
    A = round(float(A), 2) if isinstance(A, (int, float)) and A else None
    B = r.get("p8_pseudo")
    B = round(float(B), 2) if isinstance(B, (int, float)) and B else None
    C = srcC(r)

    community = [v for v in (A, B) if v is not None]
    if len(community) >= 2:
        r["final_teishu"] = round(sum(community) / len(community), 2)
        r["confidence"] = "高(2社区源)"
        r["personal_diff"] = "⚠️" if abs(community[0] - community[1]) >= 0.6 else ""
    elif len(community) == 1:
        r["final_teishu"] = community[0]
        r["confidence"] = "中(1社区源)"
        r["personal_diff"] = ""
    elif C is not None:
        r["final_teishu"] = C
        r["confidence"] = "低(自定数)"
        r["personal_diff"] = ""
    else:
        r["final_teishu"] = None
        r["confidence"] = "无"
        r["personal_diff"] = ""

    if r["final_teishu"] is not None:
        vals = [v for v in (A, B, C) if v is not None]
        r["teishu_interval"] = f"{min(vals):.1f}~{max(vals):.1f}" if len(vals) > 1 else f"{vals[0]:.1f}"
    else:
        r["teishu_interval"] = ""

with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)

from collections import Counter
print("可信度分布:", dict(Counter(r["confidence"] for r in unfc)))
print("个人差标记:", sum(1 for r in unfc if r["personal_diff"] == "⚠️"))
top = sorted([r for r in unfc if r["final_teishu"]], key=lambda r: -r["final_teishu"])
print("\n=== 多源定数 Top 20 ===")
for r in top[:20]:
    print(f"  {r['final_teishu']:5.2f} [{r['confidence']}] Lv{r['playLevel']} {r['title_cn'] or r['title_jp']} {r['personal_diff']}")
