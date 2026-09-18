# -*- coding: utf-8 -*-
"""
抓取萌娘百科「世界计划 缤纷舞台！feat. 初音未来/歌曲」表 → 曲名中/日对照。

国服歌曲名的权威来源是 cn_master_musics.json 的 infos[0].title（游戏自身本地化），
但部分曲目（尤其未实装曲）该字段仍是日文。本脚本从萌百表格的链接锚点取社区中文译名
（形如 href="...#再见宣言" → グッバイ宣言 = 再见宣言），作为「译名」补充。

输出 data/moegirl_names.json = {日文原名: 中文/英文译名}

用法:
    python scripts/parse_moegirl_names.py            # 有缓存则用缓存
    python scripts/parse_moegirl_names.py --refresh  # 重新下载页面
"""
import argparse
import json
import os
import re
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")
CACHE = os.path.join(DATA, "moegirl_songs.html")
TMP_CACHE = os.path.join(os.path.dirname(os.path.dirname(BASE)), "tmp", "haruki_probe", "moegirl_songs.html")
URL = "https://zh.moegirl.org.cn/%E4%B8%96%E7%95%8C%E8%AE%A1%E5%88%92_%E7%BC%A4%E7%BA%B7%E8%88%9E%E5%8F%B0%EF%BC%81_feat._%E5%88%9D%E9%9F%B3%E6%9C%AA%E6%9D%A5/%E6%AD%8C%E6%9B%B2"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def get_html(refresh=False):
    if not refresh:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    html = get_html(args.refresh)
    seg = html[html.find("MA/APD"):]

    names, no_frag, rows = {}, 0, 0
    for tr in re.findall(r"<tr>(.*?)</tr>", seg, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 7:
            continue
        rows += 1
        td = tds[2]
        jp_m = re.search(r"<span[^>]*lang[^>]*>(.*?)</span>", td, re.S)
        jp = re.sub(r"<[^>]+>", "", jp_m.group(1)).strip() if jp_m else re.sub(r"<[^>]+>", "", td).strip()
        if not jp:
            continue
        # 链接锚点 = 中文译名
        cn = None
        for href in re.findall(r'href="([^"]+)"', td):
            if "#" in href:
                frag = urllib.parse.unquote(href.split("#", 1)[1]).replace("_", " ").strip()
                if frag:
                    cn = frag
                    break
        if cn and cn != jp:
            names[jp] = cn
        elif not cn:
            no_frag += 1

    print(f"解析 {rows} 行；取到译名 {len(names)} 首；无锚点 {no_frag} 首")
    with open(os.path.join(DATA, "moegirl_names.json"), "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False, indent=1, sort_keys=True)

    for k in ["グッバイ宣言", "マリオネットダンサー", "悪食娘コンチータ", "シルバーコレクター",
              "あなたの空が泣くのなら", "ホワイトハッピー", "スター"]:
        print(f"  {k} -> {names.get(k, '（无）')}")
    print("已存 data/moegirl_names.json")


if __name__ == "__main__":
    main()
