# -*- coding: utf-8 -*-
"""v2 解析萌百 BPM：支持区间/小数，标题提取去 span。BPM 存 min/max（区间=速度变化谱面）。"""
import re
import json
import os

SRC = r"C:\Users\Liz\Desktop\bot\cc\tmp\haruki_probe\moegirl_songs.html"
DATA = r"C:\Users\Liz\Desktop\bot\cc\pjsk\data"

html = open(SRC, encoding="utf-8", errors="ignore").read()
head_i = html.find("MA/APD")


def clean_title(td):
    """提取显示标题：<span lang="ja">X</span> → X；去掉内部 <a> 的 title 干扰。"""
    # 优先取 <span lang="ja"> 或 lang 标记里的文本（日文名）
    m = re.search(r'<span[^>]*lang[^>]*>(.*?)</span>', td, re.S)
    if m:
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if t:
            return t
    # 否则取 <a> 文本
    t = re.sub(r"<[^>]+>", "", td).strip()
    return t


def parse_bpm(raw):
    """'74-<br>200' / '85-<span>230</span>' / '183.5' / '99-150' → (min, max)"""
    raw = re.sub(r"<[^>]+>", "", raw).strip()
    nums = re.findall(r"\d+(?:\.\d+)?", raw)
    if not nums:
        return None, None
    vals = [float(x) for x in nums]
    lo = min(vals)
    hi = max(vals)
    # 单值
    if len(vals) == 1:
        return lo, lo
    return lo, hi


rows = []
for tr in re.findall(r"<tr>(.*?)</tr>", html[head_i:], re.S):
    tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
    if len(tds) < 7:
        continue
    title = clean_title(tds[2])
    bpm_lo, bpm_hi = parse_bpm(tds[4])
    dur = re.sub(r"<[^>]+>", "", tds[5]).strip()
    if not title or bpm_lo is None:
        continue
    rows.append({"title": title, "bpm_lo": bpm_lo, "bpm_hi": bpm_hi, "duration": dur, "bpm_var": bpm_hi > bpm_lo})

seen = {}
for r in rows:
    seen.setdefault(r["title"], r)
print(f"解析 {len(rows)} 行，去重 {len(seen)} 首；其中 BPM 区间（速度变化）: {sum(1 for r in seen.values() if r['bpm_var'])} 首")

with open(os.path.join(DATA, "moegirl_bpm.json"), "w", encoding="utf-8") as f:
    json.dump(seen, f, ensure_ascii=False, indent=1)

# ---- 匹配 193 首 ----
unfc = json.load(open(os.path.join(DATA, "master_unfc_full.json"), encoding="utf-8"))
matched = 0
no_bpm = []
for r in unfc:
    cn = r["title_cn"].strip()
    jp = r["title_jp"].strip()
    b = seen.get(cn) or seen.get(jp)
    if not b and jp:
        # 去掉可能的尾标再试（如 [reunion]）
        base_jp = re.sub(r"\s*\[.*?\]\s*$", "", jp)
        b = seen.get(base_jp)
    if b:
        r["bpm_lo"] = b["bpm_lo"]
        r["bpm_hi"] = b["bpm_hi"]
        r["duration"] = b["duration"]
        r["bpm_var"] = b["bpm_var"]
        matched += 1
    else:
        r["bpm_lo"] = None
        r["bpm_hi"] = None
        r["duration"] = None
        r["bpm_var"] = False
        no_bpm.append(r)

print(f"匹配 {matched}/{len(unfc)}")
print(f"未匹配 {len(no_bpm)}:")
for r in no_bpm:
    print(f"  - {r['title_cn'] or r['title_jp']} id={r['musicId']} jp=[{r['title_jp']}]")

with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
    json.dump(unfc, f, ensure_ascii=False, indent=1)
print("已写回")
