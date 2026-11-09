# -*- coding: utf-8 -*-
"""公开构建唯一入口：只读仓内公开数据/模板，产出公开页与 receipt。

用法（在仓库根目录执行）：
    python pipeline/build_public.py --now 2026-11-09T19:04:00 \
        --generated "2026-11-09 19:04" \
        --out web/index.html --receipt out/build-receipt.json \
        [--audit out/build-audit.json]

约束：
- --now 为 Asia/Shanghai 本地 ISO 时间，决定「未实装」判定；必填。
- --generated 为页面 meta.generated 展示文本；不给则由 --now 推导。
- 确定性：不调用 datetime.now()/time.time() 决定数据或元信息。
- 只读白名单 ALLOWED_READS：仓内其余文件一律拒绝读取。
- --audit：安装 sys.addaudithook 记录进程实际 open 的文件路径，
  汇总写入 receipt，完整清单写入该 JSON；进程内无法移除 hook，
  因此验证请在新子进程中执行。

数据来源（全部为公开数据）：
  data/cn_master_musics.json, data/cn_master_musicDifficulties.json,
  data/jp_master_musics.json, data/pjsekai_master_8level.json,
  data/moegirl_bpm.json, data/moegirl_names.json,
  data/pjsekai_tips.json, data/pjsekai_tips_zh.json, data/pjsk_glossary.json,
  data/expert/pjsekai_expert_8level.json, data/expert/pjsekai_expert_tips.json,
  data/expert/pjsekai_expert_tips_zh.json；
模板/代码：web/_base_template.html, web/stats_by_difficulty.js,
  pipeline/expert_template.py。
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 本工具自身是生成物，不需要 .pyc，避免把字节码缓存混进输入清单。
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))

# 允许读取的仓内文件（相对仓库根、POSIX 形式）。expert_template.apply() 会
# 读 web/stats_by_difficulty.js；pipeline/expert_template.py 由 import 读取。
# pipeline/build_public.py 自身只为算 receipt 里的 tool_sha256 而读取，不算数据输入。
INPUT_READS = (
    "data/cn_master_musics.json",
    "data/cn_master_musicDifficulties.json",
    "data/jp_master_musics.json",
    "data/pjsekai_master_8level.json",
    "data/moegirl_bpm.json",
    "data/moegirl_names.json",
    "data/pjsekai_tips.json",
    "data/pjsekai_tips_zh.json",
    "data/pjsk_glossary.json",
    "data/expert/pjsekai_expert_8level.json",
    "data/expert/pjsekai_expert_tips.json",
    "data/expert/pjsekai_expert_tips_zh.json",
    "web/_base_template.html",
    "web/stats_by_difficulty.js",
    "pipeline/expert_template.py",
)
ALLOWED_READS = INPUT_READS + ("pipeline/build_public.py",)
ALLOWED_READS_SET = frozenset(ALLOWED_READS)

# 不允许打开的私人路径特征（只用于审计断言，不读取其内容）。
FORBIDDEN_PATTERNS = (
    "user_suite_latest.json",
    "user_results_all_latest.csv",
    "analysis",
    "master_all.json",
    "charts_all.json",
    "state.json",
    "state\\",  # 兼容 Windows 路径分隔符
)

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
VS_SUFFIX = "_バーチャル・シンガーver."
JUDGE_TO_POS = {"最下位−": 0.00, "最下位": 0.20, "下位": 0.40, "適正": 0.50,
                "上位": 0.70, "最上位": 0.90, "最上位＋": 0.95}
GAP_JUDGE = {"判定困難", "-"}

_OPENED = []


def _install_audit_hook():
    """记录每个 open/os.open 事件（path, mode, flags）。"""
    def hook(event, args):
        if event not in ("open", "os.open"):
            return
        try:
            raw = os.fspath(args[0])
        except (TypeError, IndexError):
            return
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        mode = args[1] if len(args) > 1 else None
        try:
            abspath = os.path.abspath(raw)
        except (TypeError, ValueError):
            abspath = str(raw)
        _OPENED.append({"event": event, "path": abspath, "mode": str(mode)})

    sys.addaudithook(hook)


def _read_text(rel):
    """按文本模式读取（通用换行），与 expert_template 的换行假设保持一致。"""
    if rel not in ALLOWED_READS_SET:
        raise SystemExit("[build_public] 拒绝读取非白名单文件: %r" % (rel,))
    with open(ROOT / rel, encoding="utf-8") as f:
        return f.read()


def _load_json(rel):
    if rel not in ALLOWED_READS_SET:
        raise SystemExit("[build_public] 拒绝读取非白名单文件: %r" % (rel,))
    with open(ROOT / rel, encoding="utf-8-sig") as f:
        return json.load(f)


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def norm(s):
    return re.sub(r"[^0-9a-z\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+", "", (s or "").lower())


def variants(t):
    t = html.unescape((t or "").strip())
    out = [t]
    if VS_SUFFIX in t:
        out.append(t.replace(VS_SUFFIX, ""))
    out.append(t + VS_SUFFIX)
    return out


def dur_to_sec(d):
    m = re.match(r"(\d+):(\d+)", str(d or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def index_tips(d):
    exact, idx = {}, {}
    for k, v in d.items():
        for t in variants(k):
            exact.setdefault(t, v)
            idx.setdefault(norm(t), v)
    return exact, idx


def index_list(records, keyfn):
    exact, idx = {}, {}
    for rec in records:
        for v in variants(keyfn(rec)):
            exact.setdefault(v, rec)
            idx.setdefault(norm(v), rec)
    return exact, idx


def find(exact, idx, titles):
    for t in titles:
        for v in variants(t):
            hit = exact.get(v) or idx.get(norm(v))
            if hit:
                return hit
    return None


def rank_within(group, keyfn):
    valid = [r for r in group if keyfn(r) is not None]
    res = {}
    n = len(valid)
    if n < 2:
        for r in group:
            res[id(r)] = 0.5 if keyfn(r) is not None else None
        return res
    ordered = sorted(valid, key=lambda r: (-keyfn(r), r["musicId"]))
    for i, r in enumerate(ordered):
        res[id(r)] = i / (n - 1)
    return res


def available_at(music):
    """国服可玩时间取 publishedAt；releasedAt 是歌曲原始发行时间。"""
    return music.get("publishedAt") or music.get("releasedAt") or 0


def available_date(music):
    stamp = available_at(music)
    return datetime.fromtimestamp(stamp / 1000, CN_TZ).strftime("%Y-%m-%d") if stamp else ""


def build(now_ms):
    sys.path.insert(0, str(ROOT / "pipeline"))
    import expert_template  # 延迟到审计 hook 生效后导入，便于审计其源文件读取

    musics_raw = _load_json("data/cn_master_musics.json")
    musics = {m["id"]: m for m in musics_raw}
    diffs = _load_json("data/cn_master_musicDifficulties.json")
    jp = {m["id"]: m for m in _load_json("data/jp_master_musics.json")}
    jp_title = {i: html.unescape((m.get("title") or "")).strip() for i, m in jp.items()}
    p8m = _load_json("data/pjsekai_master_8level.json")
    bpm_db = _load_json("data/moegirl_bpm.json")
    names = _load_json("data/moegirl_names.json")
    tips = _load_json("data/pjsekai_tips.json")
    tips_zh = _load_json("data/pjsekai_tips_zh.json")
    expert_b = _load_json("data/expert/pjsekai_expert_8level.json")
    expert_tips = _load_json("data/expert/pjsekai_expert_tips.json")
    expert_zh = _load_json("data/expert/pjsekai_expert_tips_zh.json")
    glossary = _load_json("data/pjsk_glossary.json")
    elem_map = glossary.get("elements") or {}

    p8_exact, p8_map = index_list(p8m, lambda e: e.get("title_ja"))
    tips_exact, tips_idx = index_tips(tips)
    zh_exact, zh_idx = index_tips(tips_zh)
    bpm_exact, bpm_idx = {}, {}
    for k, v in bpm_db.items():
        bpm_exact.setdefault(k, v)
        bpm_idx.setdefault(norm(k), v)
    eb_exact, eb_idx = index_list(expert_b, lambda e: e.get("title_ja"))
    et_index = index_tips(expert_tips)
    ez_index = index_tips(expert_zh)

    # ---------- MASTER rows ----------
    rows = []
    for d in diffs:
        if d["musicDifficulty"] != "master":
            continue
        mid = d["musicId"]
        m = musics.get(mid, {})
        infos = m.get("infos") or []
        title_cn = html.unescape((infos[0].get("title", "") if infos and isinstance(infos[0], dict) else "") or "").strip()
        title_jp = html.unescape((m.get("title") or "")).strip()
        jt = jp_title.get(mid)
        if jt and not KANA.search(title_jp):
            title_jp = jt
        rel = available_at(m)
        unreleased = bool(rel and rel > now_ms)
        r = {"musicId": mid, "title_jp": title_jp, "title_cn": title_cn,
             "playLevel": d["playLevel"], "noteCount": d["totalNoteCount"],
             "releasedAt": rel, "released_at": available_date(m), "unreleased": unreleased,
             "assetbundleName": m.get("assetbundleName", "")}
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
        pe = find(p8_exact, p8_map, [title_jp, title_cn])
        if pe:
            r["p8_judge"] = pe.get("judge")
            pos = JUDGE_TO_POS.get(pe.get("judge"))
            r["p8_pseudo"] = round(r["playLevel"] + pos, 2) if pos is not None else None
            r["p8_pseudo_note"] = "" if pos is not None else "判定困難/未定"
        else:
            r["p8_judge"] = None
            r["p8_pseudo"] = None
            r["p8_pseudo_note"] = "无日服数据"
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
        t = find(tips_exact, tips_idx, [title_jp, title_cn])
        z = find(zh_exact, zh_idx, [title_jp, title_cn])
        if t:
            r["tips_elements"] = t.get("elements") or []
            r["tips_memo"] = t.get("tips") or ""
            r["tips_judge_note"] = t.get("judge_note") or ""
        else:
            r["tips_elements"] = []
            r["tips_memo"] = ""
            r["tips_judge_note"] = ""
        if z and z.get("memo"):
            r["tips_elements_zh"] = z.get("elements") or r["tips_elements"]
            r["tips_memo_zh"] = z.get("memo") or ""
        else:
            r["tips_elements_zh"] = r["tips_elements"]
            r["tips_memo_zh"] = r["tips_memo"]
        r["difficulty"] = "master"
        r["id"] = mid
        r["lv"] = r["playLevel"]
        r["notes"] = r["noteCount"]
        r["unrel"] = bool(r.get("unreleased"))
        r["teishu"] = None
        r["elems"] = r["tips_elements_zh"]
        r["tips"] = r["tips_memo_zh"]
        r["tipsNote"] = r["tips_judge_note"]
        rows.append(r)
    rows.sort(key=lambda r: (-r["playLevel"], r["title_cn"] or r["title_jp"]))
    meta = {r["musicId"]: r for r in rows}

    # ---------- EXPERT rows ----------
    for d in diffs:
        if d["musicDifficulty"] != "expert":
            continue
        mid = int(d["musicId"])
        src_music = musics.get(mid, {})
        m = meta.get(mid)
        if m:
            title_jp = m.get("title_jp") or src_music.get("title") or ""
            title_cn = m.get("title_cn") or ""
            alias = m.get("cn_alias") or ""
            name_display = m.get("name_display") or title_cn or title_jp
            abn = m.get("assetbundleName") or src_music.get("assetbundleName") or "noimg"
            unrel = bool(m.get("unreleased"))
            rel = m.get("releasedAt")
            reldate = m.get("released_at") or ""
            bpm_lo, bpm_hi, duration = m.get("bpm_lo"), m.get("bpm_hi"), m.get("duration")
            bpm_var = bool(m.get("bpm_var"))
        else:
            infos = src_music.get("infos") or []
            title_jp = src_music.get("title") or ""
            title_cn = (infos[0].get("title") if infos and isinstance(infos[0], dict) else "") or ""
            alias = ""
            name_display = title_cn or title_jp
            abn = src_music.get("assetbundleName") or "noimg"
            rel = available_at(src_music)
            unrel = bool(rel and rel > now_ms)
            reldate = available_date(src_music)
            bpm_lo = bpm_hi = duration = None
            bpm_var = False
        lv = int(d["playLevel"])
        notes = int(d["totalNoteCount"])
        sec = dur_to_sec(duration)
        nps = round(notes / sec, 2) if sec else None
        e8 = find(eb_exact, eb_idx, [title_jp, title_cn])
        if e8:
            judge = e8.get("judge")
            pos = JUDGE_TO_POS.get(judge)
            p8_pseudo = round(lv + pos, 2) if pos is not None else None
            p8_note = "" if pos is not None else "判定困難/未定"
        else:
            judge, p8_pseudo, p8_note = None, None, "无EXPERT社区数据"
        t = find(et_index[0], et_index[1], [title_jp, title_cn])
        z = find(ez_index[0], ez_index[1], [title_jp, title_cn])
        raw_elems = (t or {}).get("elements") or (t or {}).get("elements_ja") or []
        elems_zh = [elem_map.get(e, e) for e in raw_elems]
        memo_zh = ""
        if z and z.get("memo"):
            memo_zh = z["memo"]
            if z.get("elements_zh") or z.get("elements"):
                elems_zh = list(z.get("elements_zh") or z["elements"])
        elif t and t.get("memo_zh"):
            memo_zh = t["memo_zh"]
        name_basis = "official" if (title_cn and not KANA.search(title_cn)) else ("alias" if alias else "official")
        rows.append({
            "id": "expert:%d" % mid, "musicId": mid, "difficulty": "expert",
            "title_jp": title_jp, "title_cn": title_cn, "name_display": name_display,
            "cn_alias": alias, "name_basis": name_basis,
            "playLevel": lv, "noteCount": notes, "releasedAt": rel, "released_at": reldate,
            "unreleased": unrel, "assetbundleName": abn,
            "played": False, "fc": False, "ap": False, "highScore": 0, "nPlayModes": 0,
            "p8_judge": judge, "p8_pseudo": p8_pseudo, "p8_pseudo_note": p8_note,
            "bpm_lo": bpm_lo, "bpm_hi": bpm_hi, "duration": duration, "bpm_var": bpm_var,
            "nps": nps, "tips_elements_zh": elems_zh, "tips_memo_zh": memo_zh,
            "tips_judge_note": (t or {}).get("judge_note") or "",
            "tips_translated": bool(z and z.get("memo")),
            "disp": name_display, "abn": abn, "lv": lv, "notes": notes,
            "teishu": None, "unrel": unrel, "elems": elems_zh, "tips": memo_zh,
            "tipsNote": (t or {}).get("judge_note") or "",
        })

    # ---------- density ranks + 定数 ----------
    groups = defaultdict(list)
    for r in rows:
        groups[(r["difficulty"], r["lv"])].append(r)
    for (diff, lv), group in groups.items():
        nr = rank_within(group, lambda r: r["notes"] if r["notes"] is not None else None)
        pr = rank_within(group, lambda r: r["nps"])
        for r in group:
            a, b = nr.get(id(r)), pr.get(id(r))
            r["noteRank"] = round(a, 2) if a is not None else None
            r["npsRank"] = round(b, 2) if b is not None else None
            r["noteDensityRank"] = round((a + b) / 2, 2) if (a is not None and b is not None) else None
    for r in rows:
        lv = r["lv"]
        dr = r.get("noteDensityRank")
        B = r.get("p8_pseudo")
        C = round(lv + (0.2 + dr * 0.7), 2) if dr is not None else None
        if B is not None:
            r["final_teishu"], r["confidence"], r["teishu_src"] = B, "中(1社区源)", "B"
        elif C is not None:
            r["final_teishu"], r["confidence"], r["teishu_src"] = C, "低(自定数)", "C"
        else:
            r["final_teishu"], r["confidence"], r["teishu_src"] = None, "缺(无定数)", None
        r["teishu"] = r["final_teishu"]
        vals = [v for v in (B, C) if v is not None]
        r["teishu_interval"] = (f"{min(vals):.1f}~{max(vals):.1f}" if len(vals) > 1
                                else (f"{vals[0]:.1f}" if vals else ""))
        r["gap_class"] = None
        if r["teishu_src"] == "C":
            if r.get("p8_judge") in GAP_JUDGE or r.get("p8_pseudo_note") == "判定困難/未定":
                r["gap_class"] = "判定困難(社区无共识)"
            else:
                r["gap_class"] = ("无EXPERT社区数据(自定数兜底)"
                                  if r["difficulty"] == "expert" else "无日服数据(估算)")
        elif r["teishu_src"] is None:
            r["gap_class"] = "缺源：无社区分档且无NPS"
    return rows, expert_template


def _conf(c):
    return (c or "").replace("(1社区源)", "").replace("(2社区源)", "").replace("(自定数)", "") or "无"


def payload(rows, generated):
    songs = []
    for r in rows:
        songs.append({
            "id": r["id"], "chartId": r["id"], "musicId": r["musicId"],
            "difficulty": r["difficulty"],
            "disp": r.get("name_display") or r.get("title_cn") or r.get("title_jp") or "",
            "cn": r.get("title_cn") or "", "jp": r.get("title_jp") or "",
            "alias": r.get("cn_alias") or "", "basis": r.get("name_basis") or "official",
            "unrel": bool(r.get("unreleased")), "reldate": r.get("released_at") or "",
            "lv": r["lv"], "notes": r["notes"],
            "p8": r.get("p8_judge") or "", "p8n": r.get("p8_pseudo"),
            "teishu": r.get("final_teishu"), "iv": r.get("teishu_interval") or "",
            "conf": _conf(r.get("confidence")), "src": r.get("teishu_src") or "",
            "gap": r.get("gap_class") or "",
            "abn": r.get("assetbundleName") or "noimg",
            "bpm": [r["bpm_lo"], r["bpm_hi"]] if r.get("bpm_lo") else None,
            "bpmVar": bool(r.get("bpm_var")), "dur": r.get("duration") or "",
            "nps": r.get("nps"), "nr": r.get("noteRank"), "pr": r.get("npsRank"),
            "dr": r.get("noteDensityRank"),
            "elems": r.get("tips_elements_zh") or [],
            "tips": r.get("tips_memo_zh") or "",
            "tipsNote": r.get("tips_judge_note") or "",
            "tipsSrc": "EXPERT" if r["difficulty"] == "expert" else "MASTER",
        })
    live = [r for r in rows if not r["unrel"]]
    meta = {
        "snapshot": "", "generated": generated,
        "totalCharts": len(rows),
        "totalMaster": sum(1 for r in rows if r["difficulty"] == "master"),
        "totalExpert": sum(1 for r in rows if r["difficulty"] == "expert"),
        "releasedCharts": len(live),
        "releasedMaster": sum(1 for r in live if r["difficulty"] == "master"),
        "releasedExpert": sum(1 for r in live if r["difficulty"] == "expert"),
        "unreleased": len(rows) - len(live),
        "missingTeishu": sum(1 for r in rows if r["final_teishu"] is None),
        "expertCommunity": sum(1 for r in rows if r["difficulty"] == "expert" and r.get("teishu_src") == "B"),
        "expertTips": sum(1 for r in rows if r["difficulty"] == "expert" and bool(r.get("tips_elements_zh"))),
        "bpmVar": sum(1 for r in live if r["bpm_var"]),
        "aliased": sum(1 for r in live if r.get("name_basis") == "alias"),
        "withTips": sum(1 for r in live if r.get("tips_memo_zh")),
        "public": True,
    }
    return {"meta": meta, "songs": songs}


def _audit_report(now_arg, generated, out_abs, receipt_abs, audit_abs):
    """把 open 事件归类：仓内读取 / 仓内写入 / 仓外读取 / 仓外写入 / 违例。"""
    write_targets = {os.path.normcase(os.path.abspath(p)) for p in (out_abs, receipt_abs) if p}
    if audit_abs:
        write_targets.add(os.path.normcase(os.path.abspath(audit_abs)))
    pycache_suffixes = (".pyc", ".pyo")

    repo_reads, repo_writes, outside_reads, outside_writes = [], [], [], []
    for ev in _OPENED:
        p = ev["path"]
        key = os.path.normcase(p)
        mode = (ev.get("mode") or "").lower()
        is_write = mode in ("w", "wb", "a", "ab", "x", "xb") or key in write_targets
        try:
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            inside = not rel.startswith("../")
        except ValueError:
            rel, inside = p, False
        if inside:
            if is_write:
                repo_writes.append(rel)
            else:
                repo_reads.append(rel)
        elif is_write:
            outside_writes.append(p)
        else:
            outside_reads.append(p)

    # 仓内读取去重；忽略 __pycache__ 字节码缓存（不写缓存时不会出现）。
    repo_reads_uniq = sorted({r for r in repo_reads if not r.endswith(pycache_suffixes)})
    unexpected = sorted(set(repo_reads_uniq) - set(ALLOWED_READS))
    forbidden = []
    for ev in _OPENED:
        low = ev["path"].replace("/", "\\").lower()
        for pat in FORBIDDEN_PATTERNS:
            pat_low = pat.replace("/", "\\").lower()
            if pat_low in low:
                forbidden.append(ev["path"])
                break
    return {
        "enabled": True,
        "now": now_arg,
        "generated": generated,
        "opens_total": len(_OPENED),
        "repo_reads": repo_reads_uniq,
        "repo_writes": sorted(set(repo_writes)),
        "outside_reads": sorted(set(outside_reads)),
        "outside_writes": sorted(set(outside_writes)),
        "unexpected_repo_reads": unexpected,
        "forbidden_hits": sorted(set(forbidden)),
    }


def main():
    ap = argparse.ArgumentParser(description="公开页构建（public-only）")
    ap.add_argument("--now", required=True,
                    help="Asia/Shanghai 本地 ISO 时间，如 2026-11-09T19:04:00")
    ap.add_argument("--generated", default=None,
                    help='页面 meta.generated，如 "2026-11-09 19:04"；缺省由 --now 推导')
    ap.add_argument("--out", required=True, help="输出页面路径")
    ap.add_argument("--receipt", required=True, help="输出 receipt JSON 路径")
    ap.add_argument("--audit", default=None, help="输出完整文件打开审计 JSON 路径")
    args = ap.parse_args()

    now = datetime.fromisoformat(args.now)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CN_TZ)
    else:
        now = now.astimezone(CN_TZ)
    now_ms = int(now.timestamp() * 1000)
    generated = args.generated if args.generated is not None else now.strftime("%Y-%m-%d %H:%M")

    if args.audit:
        _install_audit_hook()

    rows, expert_template = build(now_ms)
    data = payload(rows, generated)

    tpl_text = _read_text("web/_base_template.html")
    tpl = expert_template.apply(tpl_text)
    page = tpl.replace("/*__PAYLOAD__*/",
                       json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    out_path = Path(args.out)
    receipt_path = Path(args.receipt)
    audit_path = Path(args.audit) if args.audit else None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)

    page_bytes = page.encode("utf-8")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    report = None
    if args.audit:
        report = _audit_report(args.now, generated,
                               str(out_path.resolve()), str(receipt_path.resolve()),
                               str(audit_path.resolve()))

    inputs = [{"path": rel, "bytes": (ROOT / rel).stat().st_size,
               "sha256": _sha256_file(ROOT / rel)} for rel in INPUT_READS]
    meta = data["meta"]
    receipt = {
        "tool": "pipeline/build_public.py",
        "tool_sha256": _sha256_file(Path(__file__).resolve()),
        "repo_root": ROOT.name,
        "now": args.now,
        "now_ms": now_ms,
        "generated": generated,
        "output": {"path": Path(args.out).as_posix(), "bytes": len(page_bytes),
                   "sha256": _sha256_bytes(page_bytes)},
        "meta": meta,
        "counts": {"charts": len(data["songs"]),
                   "master": meta["totalMaster"], "expert": meta["totalExpert"]},
        "inputs": inputs,
    }
    if report is not None:
        receipt["audit"] = report

    with open(receipt_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)
        f.write("\n")

    if audit_path is not None:
        with open(audit_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"tool": "pipeline/build_public.py", "opens": _OPENED},
                      f, ensure_ascii=False, indent=1)
            f.write("\n")

    print("wrote", args.out, len(page_bytes), "bytes; charts:", len(data["songs"]),
          "; master:", meta["totalMaster"], "; expert:", meta["totalExpert"])
    if report is not None:
        print("audit: repo_reads=%d outside_reads=%d unexpected=%d forbidden=%d"
              % (len(report["repo_reads"]), len(report["outside_reads"]),
                 len(report["unexpected_repo_reads"]), len(report["forbidden_hits"])))
        if report["unexpected_repo_reads"] or report["forbidden_hits"]:
            print("ERROR: audit violation", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
