# -*- coding: utf-8 -*-
"""
抓 pjsekai.com（プロジェクトセカイ攻略Wiki）「楽曲難易度表 MASTER」→ 每曲 判定 / 要素 / メモ（難所 tips）。

表格每行四列：
  曲名 | 判定(memo1 + memo2 日期/状态) | 要素(li 标签) | メモ(自由文本，写难点在哪)

输出 data/pjsekai_tips.json = {日文曲名: {level, judge, judge_note, elements:[...], tips:"..."}}

用法:
    python scripts/parse_pjsekai_tips.py            # 有缓存用缓存
    python scripts/parse_pjsekai_tips.py --refresh  # 重新下载
"""
import argparse
import html as htmlmod
import json
import os
import re
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(BASE)
DATA = os.path.join(PROJ, "data")
CACHE = os.path.join(DATA, "pjsekai_teishu_master.html")
OLD_CACHE = os.path.join(os.path.dirname(PROJ), "tmp", "teishu_probe", "pjsekai_master.html")

URL = "https://pjsekai.com/?%E6%A5%BD%E6%9B%B2%E9%9B%A3%E6%98%93%E5%BA%A6%E8%A1%A8MASTER"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def get_html(refresh=False):
    if not refresh:
        for p in (CACHE, OLD_CACHE):
            if os.path.exists(p) and os.path.getsize(p) > 500000:
                print("使用缓存:", p)
                return open(p, encoding="utf-8", errors="ignore").read()
    print("下载楽曲難易度表 MASTER…")
    req = urllib.request.Request(URL, headers={**UA, "Accept-Language": "ja,en;q=0.9"})
    doc = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "ignore")
    open(CACHE, "w", encoding="utf-8").write(doc)
    print(f"已缓存 {CACHE} ({len(doc)} 字符)")
    return doc


def text_of(frag):
    """去标签 + 解实体 + 压空白。"""
    t = re.sub(r"<br\s*/?>", " ", frag)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    doc = get_html(args.refresh)

    # 按 Lv.NN 分节
    sections, lv_pat = [], re.compile(r"<h4[^>]*>Lv\.(\d+)")
    for m in lv_pat.finditer(doc):
        nxt = lv_pat.search(doc, m.end())
        sections.append((int(m.group(1)), doc[m.end(): nxt.start() if nxt else len(doc)]))

    rows, n_elem, n_tips = {}, 0, 0
    for level, chunk in sections:
        for tr in re.findall(r"<tr>(.*?)</tr>", chunk, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) < 4:
                continue
            # 曲名：<a href="./?X">X</a>，否则 img 的 title
            m = re.search(r'<a href="\./\?[^"]*">([^<]+)</a>', tds[0])
            if not m:
                m = re.search(r'alt="([^"]+)"', tds[0])
            if not m:
                continue
            title = htmlmod.unescape(m.group(1)).strip()

            jm = re.search(r'class="memo1">(.*?)<span', tds[1], re.S)
            judge = text_of(jm.group(1)) if jm else text_of(tds[1])
            nm = re.search(r'class="memo2">(.*?)</span>', tds[1], re.S)
            judge_note = text_of(nm.group(1)) if nm else ""

            elements = [text_of(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", tds[2], re.S)]
            elements = [e for e in elements if e]

            tips = text_of(tds[3])
            if not tips or tips in ("-", "—"):
                tips = ""

            rows[title] = {
                "level": level, "judge": judge, "judge_note": judge_note,
                "elements": elements, "tips": tips,
            }
            n_elem += bool(elements)
            n_tips += bool(tips)

    print(f"解析 {len(rows)} 首（带要素 {n_elem}，带攻略メモ {n_tips}）")
    json.dump(rows, open(os.path.join(DATA, "pjsekai_tips.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)

    for k in ["アストロノーツ", "人生", "初音ミクの消失", "六兆年と一夜物語"]:
        v = rows.get(k)
        if v:
            print(f"\n[{k}] Lv{v['level']} {v['judge']} {v['judge_note']}")
            print(f"   要素: {' / '.join(v['elements']) or '—'}")
            print(f"   メモ: {v['tips'][:150] or '—'}")
    print(f"\n已存 {os.path.join(DATA, 'pjsekai_tips.json')}")


if __name__ == "__main__":
    main()
