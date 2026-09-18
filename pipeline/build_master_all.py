# -*- coding: utf-8 -*-
"""
全量 MASTER 清单生成器：data/master_all.json（622 首，国服 MASTER 谱面全集）。

与未 FC 链路（build_full_unfc_list → … → annotate_names_release）并行、独立：
- 输入全部是静态数据文件（master diffs / musics / 成绩 CSV / p8 8档 / 萌百BPM·译名 / tips·译文）
- 定数：源B = 日服 8 档伪定数；源C = 同星级「物量排名+NPS排名」/2 复合（⚠️ 必须在
  全量 622 首、同星级内重排——子集变了排名就错，见 2026-09-12 交接文档）
- 攻略：pjsekai tips + 中文译文，归一化 + 「_バーチャル・シンガーver.」后缀双向剥离匹配
- 状态：fc / 打过未FC / 完全没打过 / 未实装（releasedAt 在未来，单列不混入没打过）

用法: python scripts/build_master_all.py
"""
import csv
import html
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
VS_SUFFIX = "_バーチャル・シンガーver."          # wiki 里 4 首带的虚拟歌手 ver 后缀
JUDGE_TO_POS = {"最下位−": 0.00, "最下位": 0.20, "下位": 0.40, "適正": 0.50,
                "上位": 0.70, "最上位": 0.90, "最上位＋": 0.95}
GAP_JUDGE = {"判定困難", "-"}


def norm(s):
    """归一化匹配：小写 + 去空格/标点等分隔符。
    ⚠️ 必须保留假名 \\u3040-\\u30ff——纯假名曲名（テオ 等）若被剥成空串，
    会全部撞到同一个索引键串数据（2026-09-12 实测踩坑）。"""
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", (s or "").lower())


def variants(t):
    """一个标题的全部匹配形态：原文 / 剥后缀 / 加后缀。"""
    t = html.unescape((t or "").strip())
    out = [t]
    if VS_SUFFIX in t:
        out.append(t.replace(VS_SUFFIX, ""))
    out.append(t + VS_SUFFIX)
    return out


def dur_to_sec(d):
    m = re.match(r"(\d+):(\d+)", str(d or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def rank_within(group, keyfn, reverse=False):
    """同组内排名 0~1（reverse=True 值越大 rank 越高）；有效样本 <2 时全部取 0.5。"""
    valid = [r for r in group if keyfn(r) is not None]
    res = {}
    if len(valid) < 2:
        for r in group:
            res[id(r)] = 0.5 if keyfn(r) is not None else None
        return res
    s = sorted(valid, key=keyfn, reverse=reverse)
    n = len(s)
    for i, r in enumerate(s):
        res[id(r)] = i / (n - 1)
    return res


def main():
    musics_raw = json.load(open(os.path.join(DATA, "cn_master_musics.json"), encoding="utf-8"))
    diffs = json.load(open(os.path.join(DATA, "cn_master_musicDifficulties.json"), encoding="utf-8"))
    mrows = list(csv.DictReader(open(os.path.join(DATA, "user_results_all_latest.csv"), encoding="utf-8-sig")))
    p8 = json.load(open(os.path.join(DATA, "pjsekai_master_8level.json"), encoding="utf-8"))
    bpm_db = json.load(open(os.path.join(DATA, "moegirl_bpm.json"), encoding="utf-8"))
    names = json.load(open(os.path.join(DATA, "moegirl_names.json"), encoding="utf-8"))
    tips = json.load(open(os.path.join(DATA, "pjsekai_tips.json"), encoding="utf-8"))
    tips_zh = json.load(open(os.path.join(DATA, "pjsekai_tips_zh.json"), encoding="utf-8"))

    musics = {m["id"]: m for m in musics_raw}

    # ---- 成绩（CSV，master 行）----
    # ⚠️ nPlays 这个名字是错的（2026-09-12 查实）：haruki_pipeline 当初把
    #    suite 里 (曲,难度) 的「记录条数」当成了游玩次数，但那个条数其实是
    #    playType 的个数——每个组合最多 2 条（solo 一条 + multi 一条），
    #    所以 nPlays 恒为 1 或 2，根本不是游玩次数。官方公开 API 不提供游玩次数。
    #    这里改名为 nPlayModes 如实表达含义；游玩次数由用户在网页上手工维护。
    res = {}
    for r in mrows:
        if r["difficulty"] != "master":
            continue
        res[int(r["musicId"])] = {
            "played": True,
            "fc": r["fc"] == "True",
            "ap": r["ap"] == "True",
            "highScore": int(r["highScore"] or 0),
            "nPlayModes": int(r["nPlays"] or 0),
        }

    # ---- p8 8 档：先精确后归一化，后缀剥离双向 ----
    p8_exact, p8_map = {}, {}
    for e in p8:
        for v in variants(e.get("title_ja")):
            p8_exact.setdefault(v, e)
            p8_map.setdefault(norm(v), e)

    # ---- tips / 译文索引（同规则）----
    def index_tips(d):
        exact, idx = {}, {}
        for k, v in d.items():
            for t in variants(k):
                exact.setdefault(t, v)
                idx.setdefault(norm(t), v)
        return exact, idx
    tips_exact, tips_idx = index_tips(tips)
    zh_exact, zh_idx = index_tips(tips_zh)

    # ---- 萌百 BPM 索引（先精确后归一化）----
    bpm_exact, bpm_idx = {}, {}
    for k, v in bpm_db.items():
        bpm_exact.setdefault(k, v)
        bpm_idx.setdefault(norm(k), v)

    now_ms = time.time() * 1000
    rows = []
    for d in diffs:
        if d["musicDifficulty"] != "master":
            continue
        mid = d["musicId"]
        m = musics.get(mid, {})
        infos = m.get("infos") or []
        title_cn = html.unescape((infos[0].get("title", "") if infos and isinstance(infos[0], dict) else "") or "").strip()
        title_jp = html.unescape((m.get("title") or "")).strip()
        rel = m.get("releasedAt") or 0
        unreleased = bool(rel and rel > now_ms)

        r = {
            "musicId": mid,
            "title_jp": title_jp,
            "title_cn": title_cn,
            "playLevel": d["playLevel"],
            "noteCount": d["totalNoteCount"],
            "releasedAt": rel,
            "released_at": datetime.fromtimestamp(rel / 1000).strftime("%Y-%m-%d") if rel else "",
            "unreleased": unreleased,
            "assetbundleName": m.get("assetbundleName", ""),
        }
        sc = res.get(mid) or {"played": False, "fc": False, "ap": False, "highScore": 0, "nPlayModes": 0}
        r.update(sc)

        # ---- 曲名口径：国服名 > 萌百译名 > 日文名 ----
        alias = html.unescape((names.get(title_jp) or names.get(title_cn) or "")).strip()
        if alias and norm(alias) in (norm(title_cn), norm(title_jp)):
            alias = ""
        r["cn_alias"] = alias
        if title_cn and not KANA.search(title_cn):
            r["name_display"] = title_cn
            r["name_basis"] = "official"
        elif alias:
            r["name_display"] = alias
            r["name_basis"] = "alias"
        else:
            r["name_display"] = title_cn or title_jp
            r["name_basis"] = "official"

        # ---- p8 8 档 → 伪定数 ----
        def lookup(exact, idx):
            for v in variants(title_jp) + variants(title_cn):
                e = exact.get(v) or idx.get(norm(v))
                if e:
                    return e
            return None
        pe = lookup(p8_exact, p8_map)
        if pe:
            r["p8_judge"] = pe.get("judge")
            pos = JUDGE_TO_POS.get(pe.get("judge"))
            r["p8_pseudo"] = round(r["playLevel"] + pos, 2) if pos is not None else None
            r["p8_pseudo_note"] = "" if pos is not None else "判定困難/未定"
        else:
            r["p8_judge"] = None
            r["p8_pseudo"] = None
            r["p8_pseudo_note"] = "无日服数据"

        # ---- BPM / 时长 / NPS ----
        b = (bpm_exact.get(title_cn) or bpm_exact.get(title_jp)
             or bpm_idx.get(norm(title_cn)) or bpm_idx.get(norm(title_jp)))
        if not b and title_jp:
            base_jp = re.sub(r"\s*\[.*?\]\s*$", "", title_jp)
            b = bpm_exact.get(base_jp) or bpm_idx.get(norm(base_jp))
        if b:
            r["bpm_lo"], r["bpm_hi"] = b["bpm_lo"], b["bpm_hi"]
            r["duration"] = b["duration"]
            r["bpm_var"] = b["bpm_var"]
        else:
            r["bpm_lo"] = r["bpm_hi"] = r["duration"] = None
            r["bpm_var"] = False
        sec = dur_to_sec(r["duration"])
        r["nps"] = round(r["noteCount"] / sec, 2) if sec else None

        # ---- 攻略（先精确后归一化 + 后缀剥离；中文优先，缺译标注暂无）----
        def lookup2(exact, idx):
            for v in variants(title_jp) + variants(title_cn):
                e = exact.get(v) or idx.get(norm(v))
                if e:
                    return e
            return None
        t = lookup2(tips_exact, tips_idx)
        z = lookup2(zh_exact, zh_idx)
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
        else:
            r["tips_elements_zh"] = r["tips_elements"]
            r["tips_memo_zh"] = r["tips_memo"]
            r["tips_translated"] = False

        rows.append(r)

    # ---- 源C 复合排名：⚠️ 全量 622 首、同星级内重排 ----
    by_lv = defaultdict(list)
    for r in rows:
        by_lv[r["playLevel"]].append(r)
    for lv, group in by_lv.items():
        note_rank = rank_within(group, lambda r: r["noteCount"], reverse=True)
        nps_rank = rank_within(group, lambda r: r["nps"], reverse=True)
        for r in group:
            n_r, p_r = note_rank.get(id(r)), nps_rank.get(id(r))
            r["noteRank"] = round(n_r, 2) if n_r is not None else None
            r["npsRank"] = round(p_r, 2) if p_r is not None else None
            r["noteDensityRank"] = round((n_r + p_r) / 2, 2) if (n_r is not None and p_r is not None) else None

    # ---- 多源合并：源A（B站表）验证码墙缺位，社区源 = 源B；C 兜底 ----
    for r in rows:
        B = r["p8_pseudo"]
        C = round(r["playLevel"] + (0.2 + r["noteDensityRank"] * 0.7), 2) if r["noteDensityRank"] is not None else None
        if B is not None:
            r["final_teishu"] = B
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
        vals = [v for v in (B, C) if v is not None]
        r["teishu_interval"] = f"{min(vals):.1f}~{max(vals):.1f}" if len(vals) > 1 else (f"{vals[0]:.1f}" if vals else "")

        # 缺源分类（仅低可信）
        r["gap_class"] = None
        if r["confidence"] == "低(自定数)":
            r["gap_class"] = ("判定困難(社区无共识)"
                              if r["p8_judge"] in GAP_JUDGE or r["p8_pseudo_note"] == "判定困難/未定"
                              else "无日服数据(估算)")

    # ---- 玩家 FC 上限 = 已 FC 曲目里的最高定数 ----
    # 用于「快速收益」判定：必须拿玩家自己的水平线当基准。
    # ⚠️ 2026-09-11 修的 bug：旧规则「定数 ≤ 官方星级+0.4」是拿曲子跟它自己的星级比，
    #    完全没考虑玩家水平，导致 Lv34 的曲（定数 34.2）被标成快速收益——
    #    而玩家 FC 上限只有 31.7，那首高他 2.5，根本打不过（用户实测反馈）。
    fc_ceil = max((r["final_teishu"] for r in rows if r["fc"] and r["final_teishu"] is not None),
                  default=None)
    QUICK_MARGIN = 0.3      # 留一点挑战余量；调紧改小、调松改大
    for r in rows:
        r["quick_income"] = bool(
            not r["played"] and not r["unreleased"]
            and fc_ceil is not None and r["final_teishu"] is not None
            and r["final_teishu"] <= fc_ceil + QUICK_MARGIN)

    rows.sort(key=lambda r: (-r["playLevel"], r["title_cn"] or r["title_jp"]))

    with open(os.path.join(DATA, "master_all.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    # ---- 报告 ----
    n_fc = sum(1 for r in rows if r["fc"])
    n_tried = sum(1 for r in rows if r["played"] and not r["fc"])
    n_never = sum(1 for r in rows if not r["played"] and not r["unreleased"])
    n_unrel = sum(1 for r in rows if r["unreleased"])
    n_p8 = sum(1 for r in rows if r["p8_pseudo"] is not None)
    n_bpm = sum(1 for r in rows if r["bpm_lo"])
    n_tips = sum(1 for r in rows if r["tips_memo"])
    n_zh = sum(1 for r in rows if r["tips_translated"])
    print(f"全量 MASTER: {len(rows)} 首")
    print(f"状态: 已FC {n_fc} / 打过未FC {n_tried} / 没打过 {n_never} / 未实装 {n_unrel}")
    print(f"p8 8档: {n_p8}/{len(rows)}   BPM: {n_bpm}/{len(rows)}")
    print(f"攻略: 有tips {n_tips}/{len(rows)}，已译中文 {n_zh}（tips 覆盖口径=有 tips 或有要素标签）")
    cov = sum(1 for r in rows if r["tips_memo"] or r["tips_elements"])
    print(f"攻略覆盖（memo或要素）: {cov}/{len(rows)}")
    miss = [r for r in rows if not (r["tips_memo"] or r["tips_elements"])]
    for r in miss:
        flag = "✓国服独占" if r["musicId"] >= 11000 else "⚠️非独占!"
        print(f"   缺攻略 {flag} id={r['musicId']} Lv{r['playLevel']} {r['name_display']}")
    no_p8 = [r for r in rows if r["p8_pseudo"] is None]
    if no_p8:
        print(f"无 p8 判定 {len(no_p8)} 首:", [(r['musicId'], r['name_display']) for r in no_p8][:20])
    print("星级分布:", dict(sorted(Counter(r["playLevel"] for r in rows).items())))
    print(f"\n玩家 FC 上限 = {fc_ceil}（快速收益阈值 = 上限 + {QUICK_MARGIN} = "
          f"{round(fc_ceil + QUICK_MARGIN, 2) if fc_ceil else '—'}）")
    q = sorted([r for r in rows if r["quick_income"]], key=lambda x: -x["final_teishu"])
    print(f"快速收益 {len(q)} 首（全部应为没打过且定数≤阈值）:")
    for r in q:
        print(f"   Lv{r['playLevel']:2} 定数{r['final_teishu']:5.2f}  {r['name_display']}")
    over = [r for r in q if r["final_teishu"] > fc_ceil + QUICK_MARGIN + 1e-9]
    if over:
        print("  ⚠️ 越界（不该出现）:", over)


if __name__ == "__main__":
    main()
