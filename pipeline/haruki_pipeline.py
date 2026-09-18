# -*- coding: utf-8 -*-
"""
PJSK 国服数据管线（公开版）
- 登录 haruki.seiunx.com（Kratos 浏览器流）→ 拉取你的 suite 成绩数据 → 合并国服 master → CSV

⚠️ 这个脚本是**给自己重建数据集**用的，网页工具本身完全不需要它
   （网页在浏览器里读你手动导入的 suite JSON，不联网、不登录）。
   它需要你自己的 haruki 账号凭据 —— 凭据只从环境变量或 credentials.json 读，
   不写死在代码里，也不许提交进仓库。

凭据来源（二选一）：
  A. 环境变量
       HARUKI_EMAIL / HARUKI_PASSWORD / HARUKI_UID / HARUKI_SERVER（默认 cn）
  B. pipeline/credentials.json（已在 .gitignore 里）
       {"email": "...", "password": "...", "game_user_id": "...", "server": "cn"}

用法:
    python pipeline/haruki_pipeline.py --suite   # 只拉 suite 快照
    python pipeline/haruki_pipeline.py --merge   # 只用本地数据重算合并 CSV
    python pipeline/haruki_pipeline.py --both    # 拉取 + 合并（默认）
"""
import argparse
import csv
import http.cookiejar
import json
import os
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")

AUTH_BASE = "https://toolbox-auth.haruki.seiunx.com"
API_BASE = "https://toolbox-api-cdn.haruki.seiunx.com"


def load_credentials():
    """凭据：先看环境变量，再看 pipeline/credentials.json。二者都没有就明确报错。"""
    cred_path = os.path.join(BASE, "credentials.json")
    local = {}
    if os.path.exists(cred_path):
        with open(cred_path, encoding="utf-8") as f:
            local = json.load(f)
    cred = {
        "email": os.environ.get("HARUKI_EMAIL") or local.get("email", ""),
        "password": os.environ.get("HARUKI_PASSWORD") or local.get("password", ""),
        "game_user_id": os.environ.get("HARUKI_UID") or local.get("game_user_id", ""),
        "server": os.environ.get("HARUKI_SERVER") or local.get("server", "cn"),
    }
    missing = [k for k in ("email", "password", "game_user_id") if not cred[k]]
    if missing:
        raise SystemExit(
            "缺少 haruki 凭据：" + "、".join(missing) + "\n"
            "请设置环境变量 HARUKI_EMAIL / HARUKI_PASSWORD / HARUKI_UID（可选 HARUKI_SERVER），\n"
            "或写一份 pipeline/credentials.json（该文件已被 .gitignore 排除）。"
        )
    return cred


def _opener_with_cookies():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)), cj


def login(cred):
    """Kratos browser-flow 登录，返回带 session cookie 的 opener。"""
    opener, cj = _opener_with_cookies()
    req = urllib.request.Request(
        f"{AUTH_BASE}/self-service/login/browser",
        headers={"Accept": "application/json", "User-Agent": "pjsk-pipeline/1.0"},
    )
    flow = json.loads(opener.open(req, timeout=20).read().decode("utf-8"))
    csrf = ""
    for n in flow["ui"]["nodes"]:
        if n["attributes"].get("name") == "csrf_token":
            csrf = n["attributes"].get("value", "")
    action = flow["ui"]["action"]
    form = urllib.parse.urlencode({
        "csrf_token": csrf,
        "identifier": cred["email"],
        "password": cred["password"],
        "method": "password",
    }).encode()
    req2 = urllib.request.Request(
        action,
        data=form,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "pjsk-pipeline/1.0",
        },
    )
    return opener.open(req2, timeout=20) and opener


def fetch_suite(opener, out_path, uid, server):
    url = f"{API_BASE}/public/{server}/suite/{uid}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    body = opener.open(req, timeout=120).read()
    with open(out_path, "wb") as f:
        f.write(body)
    return len(body)


def merge(out_csv):
    def load(p):
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)

    suite = load(os.path.join(DATA, "user_suite_latest.json"))
    musics = load(os.path.join(DATA, "cn_master_musics.json"))
    diffs = load(os.path.join(DATA, "cn_master_musicDifficulties.json"))

    PR = {"full_perfect": 3, "full_combo": 2, "clear": 1, "not_clear": 0}
    best = {}
    for r in suite["userMusicResults"]:
        key = (r["musicId"], r["musicDifficultyType"])
        score = PR.get(r.get("playResult"), 0)
        rec = {
            "highScore": r.get("highScore", 0),
            "fc": bool(r.get("fullComboFlg")),
            "ap": bool(r.get("fullPerfectFlg")),
            "pr": r.get("playResult", "?"),
            "pr_rank": score,
        }
        if key not in best:
            rec["n_plays"] = 1
            best[key] = rec
        else:
            cur = best[key]
            cur["n_plays"] += 1
            if score > cur["pr_rank"]:
                cur["highScore"] = rec["highScore"]
                cur["pr"] = rec["pr"]
                cur["pr_rank"] = score
            cur["highScore"] = max(cur["highScore"], rec["highScore"])
            cur["fc"] = cur["fc"] or rec["fc"]
            cur["ap"] = cur["ap"] or rec["ap"]

    title_map = {}
    for m in musics:
        cn = ""
        infos = m.get("infos") or []
        if infos and isinstance(infos[0], dict):
            cn = infos[0].get("title", "") or ""
        title_map[m["id"]] = {"jp": m.get("title", ""), "cn": cn}

    lv_map = {(d["musicId"], d["musicDifficulty"]): (d["playLevel"], d["totalNoteCount"])
              for d in diffs}

    rows = []
    for (mid, diff), rec in sorted(best.items()):
        t = title_map.get(mid, {})
        lv = lv_map.get((mid, diff), (None, None))
        rows.append({
            "musicId": mid,
            "title_jp": t.get("jp", ""),
            "title_cn": t.get("cn", ""),
            "difficulty": diff,
            "playLevel": lv[0],
            "noteCount": lv[1],
            "bestResult": rec["pr"],
            "fc": rec["fc"],
            "ap": rec["ap"],
            "highScore": rec["highScore"],
            "nPlays": rec["n_plays"],   # ⚠️ 这不是游玩次数，是 (曲,难度) 的记录条数
        })

    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--both", action="store_true", default=True)
    args = ap.parse_args()

    if args.both or args.suite:
        cred = load_credentials()
        opener = login(cred)
        n = fetch_suite(opener, os.path.join(DATA, "user_suite_latest.json"),
                        cred["game_user_id"], cred["server"])
        print(f"suite 拉取完成: {n} bytes")
    if args.both or args.merge:
        rows = merge(os.path.join(DATA, "user_results_all_latest.csv"))
        print(f"合并完成: {len(rows)} 行 → user_results_all_latest.csv")


if __name__ == "__main__":
    main()
