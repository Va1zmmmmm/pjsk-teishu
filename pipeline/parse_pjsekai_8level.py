# -*- coding: utf-8 -*-
"""解析 pjsekai.com 楽曲難易度表 MASTER（日服 8 档分类）→ CSV/JSON。

结构：
  <h4 ...>Lv.25 ...</h4>  # 每级一节
  <div class="plugin-ac" ...><table class="style_table">
    <tr>
      <td class="style_td"...><a href="./?曲名">曲名</a></td>
      <td class="style_td"...><div class="memo1">判定<span class="memo2">...</span></div></td>
      ...
"""
import re
import os
import csv
import json

SRC = r"C:\Users\Liz\Desktop\bot\cc\tmp\teishu_probe\pjsekai_master.html"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

html = open(SRC, encoding="utf-8").read()

# 1. 切出每个 Lv.X 小节
sections = []  # (level, chunk)
# 找到所有 Lv.NN 标题（h4）
lv_pat = re.compile(r'<h4[^>]*>Lv\.(\d+)')
for m in lv_pat.finditer(html):
    lv = int(m.group(1))
    start = m.end()
    nxt = lv_pat.search(html, start)
    end = nxt.start() if nxt else len(html)
    sections.append((lv, html[start:end]))

# 2. 在每个小节内提取 (曲名, 判定)
rows = []
for lv, chunk in sections:
    # 每行 <tr>...</tr>
    for tr in re.findall(r'<tr>(.*?)</tr>', chunk, re.S):
        # 曲名：优先 <a href="./?曲名">曲名</a>，其次图片 alt（hash 链接的行用 alt）
        title_m = re.search(r'<a href="\./\?[^"]*">([^<]+)</a>', tr)
        alt_m = re.search(r'alt="([^"]+)"\s+title="([^"]+)"', tr)
        judge_m = re.search(r'class="memo1">([^<]+)<span', tr)
        title = None
        if title_m:
            title = title_m.group(1).strip()
        elif alt_m:
            title = alt_m.group(2).strip()
        if title and judge_m:
            judge = judge_m.group(1).strip()
            rows.append({"level": lv, "title_ja": title, "judge": judge})

print(f"解析出 {len(rows)} 行 (曲名, Lv, 判定)")
# 判定分布
from collections import Counter
print("判定分布:", dict(Counter(r["judge"] for r in rows)))
# 各级数量
print("各级数量:", dict(Counter(r["level"] for r in rows)))

# 去重（同一曲可能因 判定变化 出现多次？检查）
seen = {}
dups = 0
for r in rows:
    k = (r["level"], r["title_ja"])
    if k in seen:
        dups += 1
        seen[k].append(r["judge"])
    else:
        seen[k] = [r["judge"]]
print(f"重复 (level,title): {dups}")

# 存 CSV
out_csv = os.path.join(OUT, "pjsekai_master_8level.csv")
with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["level", "title_ja", "judge"])
    w.writeheader()
    w.writerows(rows)
print("CSV:", out_csv)

# 存 JSON
out_json = os.path.join(OUT, "pjsekai_master_8level.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print("JSON:", out_json)

# 抽样看几行
for r in rows[:5]:
    print(r)
