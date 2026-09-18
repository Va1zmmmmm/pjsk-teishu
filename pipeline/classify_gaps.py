# -*- coding: utf-8 -*-
"""
11 首缺社区源曲目的严谨标注（2026-09-09）：
  分类1「判定困難」：p8 表明确标注判定困難/未定 → 社区无共识定数，如实标注，不硬套
  分类2「无日服数据」：国服原创/日服未收录 → 用物量密度自定数 + 标注估算
"""
import json
import os

DATA = r"C:\Users\Liz\Desktop\bot\cc\pjsk\data"
unfc = json.load(open(os.path.join(DATA, "master_unfc_full.json"), encoding="utf-8"))

GAP_JUDGE = {"判定困難", "-"}
CAT1, CAT2 = [], []
for r in unfc:
    if r["confidence"] != "低(自定数)":
        continue
    judge = r.get("p8_judge")
    if judge in GAP_JUDGE or r.get("p8_pseudo_note") == "判定困難/未定":
        r["gap_class"] = "判定困難(社区无共识)"
        CAT1.append(r)
    else:
        r["gap_class"] = "无日服数据(估算)"
        CAT2.append(r)

print(f"分类1 判定困難: {len(CAT1)} 首")
for r in sorted(CAT1, key=lambda x: -x["final_teishu"]):
    print(f"   {r['final_teishu']:.2f} Lv{r['playLevel']} {r['title_cn'] or r['title_jp']} (played={r['played']})")
print(f"分类2 无日服数据: {len(CAT2)} 首")
for r in sorted(CAT2, key=lambda x: -x["final_teishu"]):
    print(f"   {r['final_teishu']:.2f} Lv{r['playLevel']} {r['title_cn'] or r['title_jp']} (played={r['played']})")

with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)
print("\n已写入 gap_class")
