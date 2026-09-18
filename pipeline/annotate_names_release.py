# -*- coding: utf-8 -*-
"""
为未 FC 清单补三项派生字段（跑在 merge_teishu_sources.py + classify_gaps.py 之后）：

1. releasedAt / unreleased —— 国服实装状态
   ⚠️ cn_master_musics.json 含「已排期但尚未实装」的未来曲目（releasedAt 是未来时间），
   这类曲目玩家不可能打过，混在「完全没打过」里会虚增清单。
2. cn_alias / name_display —— 曲名口径
   国服名权威源 = cn_master_musics.json 的 infos[0].title（游戏自身本地化）；
   该字段仍是日文时（多为未实装曲 / 部分曲目国服沿用原名），用萌百译名补齐（moegirl_names.json）。
3. quick_income —— 「✅快速收益」统一口径（在此一处算，web 与 excel 共用，避免两边漂移）
   没打过 且 已实装 且（日服 8 档为最下位/下位 或 定数 ≤ 官方星级+0.4）

用法: python scripts/annotate_names_release.py
"""
import html
import json
import os
import re
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")


def norm(s):
    """归一化用于判重：小写 + 去所有非字母数字（含中日文标点/空格）。"""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (s or "").lower())


def main():
    unfc = json.load(open(os.path.join(DATA, "master_unfc_full.json"), encoding="utf-8"))
    musics = {m["id"]: m for m in json.load(open(os.path.join(DATA, "cn_master_musics.json"), encoding="utf-8"))}
    names_path = os.path.join(DATA, "moegirl_names.json")
    aliases = json.load(open(names_path, encoding="utf-8")) if os.path.exists(names_path) else {}
    tips_path = os.path.join(DATA, "pjsekai_tips.json")
    tips = json.load(open(tips_path, encoding="utf-8")) if os.path.exists(tips_path) else {}
    tips_norm = {norm(k): v for k, v in tips.items()}
    # 中文译文（translate_tips.py 产出）；缺失时回落日文原文
    zh_path = os.path.join(DATA, "pjsekai_tips_zh.json")
    zh = json.load(open(zh_path, encoding="utf-8")) if os.path.exists(zh_path) else {}
    zh_norm = {norm(k): v for k, v in zh.items()}

    now_ms = time.time() * 1000
    n_unrel = n_alias = n_quick = n_tips = n_zh = 0

    for r in unfc:
        m = musics.get(r["musicId"], {})
        rel = m.get("releasedAt") or 0
        r["releasedAt"] = rel
        r["released_at"] = datetime.fromtimestamp(rel / 1000).strftime("%Y-%m-%d") if rel else ""
        r["unreleased"] = bool(rel and rel > now_ms)

        cn = html.unescape((r.get("title_cn") or "").strip())
        jp = html.unescape((r.get("title_jp") or "").strip())
        alias = html.unescape((aliases.get(jp) or aliases.get(cn) or "").strip())
        # 译名与国服名/日文名实质相同（忽略大小写与标点）→ 不算补充信息
        if alias and norm(alias) in (norm(cn), norm(jp)):
            alias = ""
        r["cn_alias"] = alias
        # 展示名：国服名若仍是日文（含假名）则优先用译名，否则国服名；都没有则日文名
        if cn and not KANA.search(cn):
            r["name_display"] = cn
            r["name_basis"] = "official"
        elif alias:
            r["name_display"] = alias
            r["name_basis"] = "alias"
        else:
            r["name_display"] = cn or jp
            r["name_basis"] = "official"

        tei = r.get("final_teishu")
        r["quick_income"] = bool(
            not r.get("played", True)
            and not r["unreleased"]
            and (r.get("p8_judge") in ("最下位", "下位")
                 or (tei is not None and tei <= r["playLevel"] + 0.4))
        )

        # 攻略 tips（pjsekai.com 楽曲難易度表 MASTER 的 要素 + メモ）→ 优先用中文译文
        t = tips.get(jp) or tips.get(cn) or tips_norm.get(norm(jp)) or tips_norm.get(norm(cn))
        z = zh.get(jp) or zh.get(cn) or zh_norm.get(norm(jp)) or zh_norm.get(norm(cn))
        if t:
            r["tips_elements"] = t.get("elements") or []
            r["tips_memo"] = t.get("tips") or ""
            r["tips_judge_note"] = t.get("judge_note") or ""
            r["tips_level"] = t.get("level")
        else:
            r["tips_elements"] = []
            r["tips_memo"] = ""
            r["tips_judge_note"] = ""
            r["tips_level"] = None
        if z and z.get("memo"):
            r["tips_elements_zh"] = z.get("elements") or r["tips_elements"]
            r["tips_memo_zh"] = z.get("memo") or ""
            r["tips_translated"] = True
            n_zh += 1
        else:
            # 没译文就回落日文（网页会标出来）
            r["tips_elements_zh"] = r["tips_elements"]
            r["tips_memo_zh"] = r["tips_memo"]
            r["tips_translated"] = False

        n_unrel += r["unreleased"]
        n_alias += bool(alias)
        n_quick += r["quick_income"]
        n_tips += bool(r["tips_memo"])

    with open(os.path.join(DATA, "master_unfc_full.json"), "w", encoding="utf-8") as f:
        json.dump(unfc, f, ensure_ascii=False, indent=1)

    print(f"未实装（国服未来曲目）: {n_unrel} 首")
    for r in sorted([x for x in unfc if x["unreleased"]], key=lambda x: x["releasedAt"]):
        print(f"   {r['released_at']}  Lv{r['playLevel']:2}  {r['name_display']}  (日={r['title_jp']})")
    print(f"补到萌百译名: {n_alias} 首")
    for r in [x for x in unfc if x["cn_alias"]][:20]:
        print(f"   {r['title_jp']} -> {r['cn_alias']}   [国服名={r['title_cn'] or '空'}]")
    print(f"快速收益: {n_quick} 首")
    print(f"已实装未 FC: {sum(1 for x in unfc if not x['unreleased'])} 首")
    print(f"匹配到攻略 tips: {n_tips} / {len(unfc)} 首（其中已译中文 {n_zh} 首）")
    miss = [x for x in unfc if not x["tips_memo"]]
    if miss:
        print("  无 tips 的:", [x.get("name_display") for x in miss][:12])
    untrans = [x.get("name_display") for x in unfc if x["tips_memo"] and not x["tips_translated"]]
    if untrans:
        print(f"  有日文但未译: {len(untrans)} 首", untrans[:8])


if __name__ == "__main__":
    main()
