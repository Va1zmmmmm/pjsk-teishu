# -*- coding: utf-8 -*-
"""v2 解析萌百 BPM：支持区间/小数，标题提取去 span。BPM 存 min/max（区间=速度变化谱面）。

⚠️ 2026-09-27 修：原版把 HTML 缓存路径写死在 cc/tmp/haruki_probe/，而 cc/tmp 被 .stignore
   排除跨机同步 + 会被清理 → 缓存一旦没了这一步必 FileNotFoundError，整条 refresh_all 断在这里。
   改为与 parse_moegirl_names.py 同一套解析顺序：data 缓存 → tmp 缓存 → 现下载并缓存到 data。
"""
import re
import json
import os
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")
CACHE = os.path.join(DATA, "moegirl_songs.html")
TMP_CACHE = os.path.join(os.path.dirname(os.path.dirname(BASE)), "tmp", "haruki_probe", "moegirl_songs.html")
URL = "https://zh.moegirl.org.cn/%E4%B8%96%E7%95%8C%E8%AE%A1%E5%88%92_%E7%BC%A4%E7%BA%B7%E8%88%9E%E5%8F%B0%EF%BC%81_feat._%E5%88%9D%E9%9F%B3%E6%9C%AA%E6%9D%A5/%E6%AD%8C%E6%9B%B2"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def get_html():
    for p in (CACHE, TMP_CACHE):
        if os.path.exists(p) and os.path.getsize(p) > 100000:
            print("使用缓存:", p)
            return open(p, encoding="utf-8", errors="ignore").read()
    print("下载萌娘百科歌曲表…")
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    with open(CACHE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已缓存: {CACHE} ({len(html)} 字符)")
    return html


html = get_html()
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

# ⚠️ 防降级护栏：页面改版/抓了一半时解析数会暴跌，此时**保留旧文件**而不是覆盖
OLD = os.path.join(DATA, "moegirl_bpm.json")
if len(seen) < 500 and os.path.exists(OLD):
    print(f"⚠️ 本次只解析出 {len(seen)} 首（<500）→ 判定页面异常，保留旧 {os.path.basename(OLD)} 不覆盖")
    seen = json.load(open(OLD, encoding="utf-8"))
else:
    with open(OLD, "w", encoding="utf-8") as f:
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
