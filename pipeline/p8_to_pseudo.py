# -*- coding: utf-8 -*-
"""
8 档分类 → 伪定数（档内位置 + 官方星级）

pjsekai.com 的 8 档是社区在【同一官方星级内】的相对难度排序（最下位~最上位），
本身没有 0.1 定数。这里做透明映射：伪定数 = 官方星级 + 档内位置。

映射表（可调参数，多源合并时校准）：
  最下位−   -> 0.00   （罕见）
  最下位    -> 0.20
  下位      -> 0.40
  適正      -> 0.50
  上位      -> 0.70
  最上位    -> 0.90
  最上位＋  -> 0.95   （罕见）
  判定困難  -> None    （个人差大，不合成）
  -         -> None    （未定）
"""
import json
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

JUDGE_TO_POS = {
    "最下位−": 0.00,
    "最下位": 0.20,
    "下位": 0.40,
    "適正": 0.50,
    "上位": 0.70,
    "最上位": 0.90,
    "最上位＋": 0.95,
}

unfc = json.load(open(os.path.join(DATA, "master_unfc_with_p8.json"), encoding="utf-8"))

n_syn = 0
n_skip = 0
for r in unfc:
    j = r.get("p8_judge")
    pos = JUDGE_TO_POS.get(j)
    lv = r.get("playLevel")
    if pos is None or lv is None:
        r["p8_pseudo"] = None
        r["p8_pseudo_note"] = "判定困難/未定" if j in ("判定困難", "-") else "缺判定"
        n_skip += 1
    else:
        r["p8_pseudo"] = round(int(lv) + pos, 2)
        r["p8_pseudo_note"] = ""
        n_syn += 1

print(f"合成伪定数: {n_syn}, 跳过: {n_skip}")
print("跳过明细:", [(r["title_cn"] or r["title_jp"], r.get("p8_judge")) for r in unfc if r["p8_pseudo"] is None])

# 按伪定数降序看前 15
top = sorted([r for r in unfc if r["p8_pseudo"]], key=lambda r: -r["p8_pseudo"])
print("\n=== 伪定数 Top 15（最难的未 FC）===")
for r in top[:15]:
    print(f"  {r['p8_pseudo']:5.2f}  Lv{r['playLevel']}  {r['title_cn'] or r['title_jp']}  [{r.get('p8_judge')}]")

out = os.path.join(DATA, "master_unfc_with_p8.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)
print("\n已更新:", out)
