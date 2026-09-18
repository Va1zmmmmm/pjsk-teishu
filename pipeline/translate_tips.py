# -*- coding: utf-8 -*-
"""
把 pjsekai.com 的日文攻略（要素标签 + メモ）译成中文音游话术。

为什么要专门的词表：这些是音游专业术语，直译会错得离谱——
  トリル 直译「颤音」（实际是「交互」）、階段 直译「阶段」（实际是「楼梯」）、
  縦連 直译「纵列」（实际是「纵连」）、餡蜜 直译「豆沙馅」（实际是「糊过去」）。
术语译法依据见 data/pjsk_glossary.json 的 _source 字段。

输入 data/pjsekai_tips.json → 输出 data/pjsekai_tips_zh.json
（保留日文原文，网页折叠显示备查）

用法:
    python scripts/translate_tips.py            # 增量（已译的跳过）
    python scripts/translate_tips.py --force    # 全部重译
    python scripts/translate_tips.py --only 人生 六兆年と一夜物語   # 只译指定曲
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(BASE)
DATA = os.path.join(PROJ, "data")
sys.path.insert(0, os.path.dirname(PROJ))
from cc_config import deepseek_key  # noqa: E402

API = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"

tips = json.load(open(os.path.join(DATA, "pjsekai_tips.json"), encoding="utf-8"))
gl = json.load(open(os.path.join(DATA, "pjsk_glossary.json"), encoding="utf-8"))
OUT = os.path.join(DATA, "pjsekai_tips_zh.json")

GLOSSARY_TXT = "\n".join(f"  {k} → {v}" for k, v in gl["glossary"])
ELEM_TXT = "\n".join(f"  {k} → {v}" for k, v in gl["elements"].items())
STYLE_TXT = "\n".join(f"  - {s}" for s in gl["style_guide"])

SYSTEM = f"""你是中文音游（PJSK/プロセカ）社区的谱面攻略写手，负责把日文攻略翻成中文。

【术语对照表 —— 必须严格使用，这些是音游黑话，直译必错】
{ELEM_TXT}

【更多术语】
{GLOSSARY_TXT}

【翻译要求】
{STYLE_TXT}

【输出格式】只输出 JSON，不要 markdown 代码块：
{{"elements": ["中文要素1", ...], "memo": "中文攻略正文"}}
elements 按输入的标签逐个翻译（数量、顺序一致）。memo 是整段中文攻略；若输入 memo 为空则输出空字符串。"""


def call_ds(payload, retries=3):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {deepseek_key()}"},
    )
    last = None
    for attempt in range(retries):
        try:
            r = urllib.request.urlopen(req, timeout=180)
            d = json.loads(r.read())
            return d["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def clean_json(txt):
    t = txt.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    i, j = t.find("{"), t.rfind("}")
    return json.loads(t[i:j + 1])


def translate_one(item):
    title, v = item
    memo = (v.get("tips") or "").strip()
    elems = v.get("elements") or []
    if not memo and not elems:
        return title, {"elements": [], "memo": "", "elements_jp": [], "memo_jp": ""}, "skip"

    user = f"""曲名：{title}（官方星级 Lv{v.get('level')}）
社区判定：{v.get('judge','')} {v.get('judge_note','')}

要素标签（日文）：{json.dumps(elems, ensure_ascii=False)}

攻略メモ（日文原文）：
{memo if memo else "（无）"}

请翻译成中文。"""

    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
        "max_tokens": 4000,
    }

    # 空响应 / JSON 截断都重试（实测首轮 18/708 是这两类，重试即通）
    last = None
    for attempt in range(4):
        try:
            raw = call_ds(payload, retries=2)
            if not (raw or "").strip():
                raise ValueError("空响应")
            d = clean_json(raw)
            return title, {
                "elements": d.get("elements") or [],
                "memo": (d.get("memo") or "").strip(),
                "elements_jp": elems,
                "memo_jp": memo,
                "level": v.get("level"),
                "judge": v.get("judge", ""),
                "judge_note": v.get("judge_note", ""),
            }, "ok"
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 + attempt)
    return title, {"elements": [], "memo": "", "elements_jp": elems, "memo_jp": memo,
                   "error": f"{type(last).__name__}: {str(last)[:120]}"}, "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="只译指定日文曲名")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    done = {}
    if os.path.exists(OUT) and not args.force:
        done = json.load(open(OUT, encoding="utf-8"))

    todo = []
    for title, v in tips.items():
        if args.only and title not in args.only:
            continue
        prev = done.get(title) or {}
        # 已成功译过的跳过；失败过的（带 error）要重试
        if prev.get("memo") and "error" not in prev and not args.force:
            continue
        if not (v.get("tips") or v.get("elements")):
            continue
        todo.append((title, v))

    print(f"待译 {len(todo)} 首（已有 {len(done)} 首）")
    if not todo:
        print("无新增，结束")
        return

    ok = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for n, (title, res, tag) in enumerate(ex.map(translate_one, todo), 1):
            done[title] = res
            if tag == "ok":
                ok += 1
            else:
                fail += 1
            if n % 10 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)}  用时 {time.time()-t0:.0f}s")
            if n % 25 == 0:
                json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完成：成功 {ok} / 失败 {fail}，共 {len(done)} 首 → {OUT}")
    bad = [t for t, r in done.items() if "error" in r]
    if bad:
        print("失败清单:", bad[:10])


if __name__ == "__main__":
    main()
