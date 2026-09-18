# -*- coding: utf-8 -*-
"""
生成交互式网页版定数表
- 输入：data/master_all.json（全量 MASTER 622 首清单）
        data/cn_master_musics.json（封面 assetbundleName）
        data/user_results_all_latest.csv（账号级统计）
        data/user_suite_latest.json（快照时间）
- 模板：web/_template.html（占位符 /*__PAYLOAD__*/ 注入数据）
- 封面：私用版 web/covers/<assetbundleName>.webp（fetch_covers.py 下载）；
        公共版不打包封面，用 sekai.best 远端 URL（模板里做了 cn → jp → 占位图三级兜底）

用法:
    python scripts/gen_web_view.py            # 私用版 → web/unfc_teishu.html（含个人成绩）
    python scripts/gen_web_view.py --public   # 公共工具版 → web/public/index.html（不含任何个人数据）
"""
import argparse
import csv
import json
import os
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(BASE)
DATA = os.path.join(PROJ, "data")
WEB = os.path.join(PROJ, "web")


def main():
    ap = argparse.ArgumentParser(description="生成 PJSK MASTER 定数表网页")
    ap.add_argument("--public", action="store_true",
                    help="生成公共工具版（剥离全部个人成绩字段）→ web/public/index.html")
    public = ap.parse_args().public

    all_master = json.load(open(os.path.join(DATA, "master_all.json"), encoding="utf-8"))
    diffs = json.load(open(os.path.join(DATA, "cn_master_musicDifficulties.json"), encoding="utf-8"))
    suite = json.load(open(os.path.join(DATA, "user_suite_latest.json"), encoding="utf-8"))
    rows = list(csv.DictReader(open(os.path.join(DATA, "user_results_all_latest.csv"), encoding="utf-8-sig")))

    master_ids = {d["musicId"] for d in diffs if d["musicDifficulty"] == "master"}
    mrows = [r for r in rows if r["difficulty"] == "master"]

    # 封面缺失兜底（没图就别引用不存在的文件）
    have_cover = {f[:-5] for f in os.listdir(os.path.join(WEB, "covers"))} if os.path.isdir(os.path.join(WEB, "covers")) else set()

    songs = []
    for r in all_master:
        a = r.get("assetbundleName", "")
        # 公共版不做「本地有没有这张图」的兜底——封面走远端 URL，缺图由模板的 onerror 链处理
        abn = (a or "noimg") if public else (a if a in have_cover else "noimg")
        songs.append({
            "id": r["musicId"],
            "disp": r.get("name_display") or r.get("title_cn") or r.get("title_jp") or "",
            "cn": r.get("title_cn") or "",
            "jp": r.get("title_jp") or "",
            "alias": r.get("cn_alias") or "",
            "basis": r.get("name_basis") or "official",
            "unrel": bool(r.get("unreleased")),
            "reldate": r.get("released_at") or "",
            "lv": r["playLevel"],
            "notes": r["noteCount"],
            # 注意：不再输出旧的 nPlays（那个值恒为 1/2，是 playType 记录数不是游玩次数）。
            # 游玩次数由网页端用户手工维护（localStorage）。
            "p8": r.get("p8_judge") or "",
            "p8n": r.get("p8_pseudo"),
            "teishu": r.get("final_teishu"),
            "iv": r.get("teishu_interval") or "",
            "conf": (r.get("confidence") or "").replace("(1社区源)", "").replace("(2社区源)", "").replace("(自定数)", "") or "无",
            "gap": r.get("gap_class") or "",
            "abn": abn,
            "bpm": [r["bpm_lo"], r["bpm_hi"]] if r.get("bpm_lo") else None,
            "bpmVar": bool(r.get("bpm_var")),
            "dur": r.get("duration") or "",
            "nps": r.get("nps"),
            "nr": r.get("noteRank"),
            "pr": r.get("npsRank"),
            "dr": r.get("noteDensityRank"),
            "elems": r.get("tips_elements_zh") or [],
            "tips": r.get("tips_memo_zh") or "",
            "tipsNote": r.get("tips_judge_note") or "",
        })
        if not public:
            # 个人成绩字段只进私用版：公共版必须完全不含 played/fc/ap/hs/quick/diff
            songs[-1].update({
                "played": bool(r.get("played")),
                "fc": bool(r.get("fc")),
                "ap": bool(r.get("ap")),
                "hs": r.get("highScore") or 0,
                "diff": r.get("personal_diff") or "",
                "quick": bool(r.get("quick_income")),
            })

    live = [s for s in songs if not s["unrel"]]
    if public:
        # 公共版：meta 只留「谱面库」的客观统计；个人成绩（快照时间 / FC 数 / FC 上限 /
        # 快速收益数 / 个人差）一律不进 payload —— 那些全部由浏览器端按用户导入的
        # suite 数据现算（模板里的 buildAnalysis() / applyStatus()）。
        payload = {
            "meta": {
                "public": True,
                "snapshot": "",
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "totalMaster": len(master_ids),
                "releasedMaster": len(live),
                "unreleased": len(songs) - len(live),
                "lowConf": sum(1 for s in live if s["conf"].startswith("低")),
                "lowConfAll": sum(1 for s in songs if s["conf"].startswith("低")),
                "bpmVar": sum(1 for s in live if s["bpmVar"]),
                "aliased": sum(1 for s in live if s["basis"] == "alias"),
                "withTips": sum(1 for s in live if s["tips"]),
            },
            "songs": songs,
        }
    else:
        # 玩家 FC 上限 = 已 FC 曲目里的最高定数（快速收益阈值基准）
        fc_ceil = max((s["teishu"] for s in songs if s["fc"] and s["teishu"] is not None), default=None)
        payload = {
            "meta": {
                "snapshot": datetime.fromtimestamp(suite["upload_time"]).strftime("%Y-%m-%d %H:%M"),
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "totalMaster": len(master_ids),
                "releasedMaster": len(live),
                "playedMaster": len(mrows),
                "fcMaster": sum(1 for r in mrows if r["fc"] == "True"),
                "apMaster": sum(1 for r in mrows if r["ap"] == "True"),
                "unreleased": len(songs) - len(live),
                # 低可信 = 仅源C 兜底（无日服 8 档）。全量 23 首；其中 1 首是未实装曲，
                # 故「可玩范围内的低可信」= 22 首（16 国服独占 + 6 首日服判定困難/无数据）。
                # 两个数都给出，免得口径打架（audit 2026-09-12 发现仅 22 会被误读）。
                "lowConf": sum(1 for s in live if s["conf"].startswith("低")),
                "lowConfAll": sum(1 for s in songs if s["conf"].startswith("低")),
                "fcCeil": fc_ceil,
                "quick": sum(1 for s in songs if s["quick"]),
                "bpmVar": sum(1 for s in live if s["bpmVar"]),
                "aliased": sum(1 for s in live if s["basis"] == "alias"),
                "withTips": sum(1 for s in live if s["tips"]),
            },
            "songs": songs,
        }

    tpl = open(os.path.join(WEB, "_template.html"), encoding="utf-8").read()
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ana = {}
    if public:
        out = os.path.join(WEB, "public", "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
    else:
        out = os.path.join(WEB, "unfc_teishu.html")
        # 分析数据（B50 / 苦手擅长 / 报告）单独注入，缺失时页面自动降级
        ana_path = os.path.join(DATA, "analysis.json")
        ana = json.load(open(ana_path, encoding="utf-8")) if os.path.exists(ana_path) else {}
        body = body[:-1] + ',"analysis":' + json.dumps(ana, ensure_ascii=False, separators=(",", ":")) + "}"
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl.replace("/*__PAYLOAD__*/", body))
    if public:
        print(f"公共版网页已生成: {out}  ({len(songs)} 首, {os.path.getsize(out)/1024:.0f} KB)")
        print(f"  已剥离个人成绩字段（played/fc/ap/hs/quick/diff）与 analysis；"
              f"B50/苦手分析由浏览器端按用户导入的 suite 现算")
    else:
        print(f"网页已生成: {out}  ({len(songs)} 首, {os.path.getsize(out)/1024:.0f} KB)")
        if ana:
            print(f"  B50={ana['b50']['rating']}  "
                  f"苦手{len(ana.get('weak',[]))}个/擅长{len(ana.get('strong',[]))}个标签  "
                  f"提升空间{ana.get('nGains')}首")
        else:
            print("  ⚠️ 缺 data/analysis.json，B50/报告视图将为空（跑 scripts/build_analysis.py）")
    print("meta:", payload["meta"])


if __name__ == "__main__":
    main()
