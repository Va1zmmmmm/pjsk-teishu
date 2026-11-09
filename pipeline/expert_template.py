# -*- coding: utf-8 -*-
"""把基线 `web/_template.html` 打上 EXPERT/混合 B50 候选补丁。

原则：
- 只做「锚点唯一」的精确替换；任何锚点数量 != 1 立即失败，绝不静默跳过。
- 不碰 `/*__B50_EXPORT_BEGIN__*/ … END` 里的导出实现（Codex 的正式模板可能更新）；
  只保证它依赖的 `A.b50.list[].chartId / difficulty / musicId` 由 build_candidate 提供。
- 失败信息直接列出补丁名与锚点，便于整合时定位基线漂移。

用法（通常由 build_candidate.py 调用）：
    from template_patch import apply
    patched = apply(open("inputs/_template.html", encoding="utf-8").read())
"""
import re
from pathlib import Path

PATCHES = []


def _one(text, old, new, name):
    n = text.count(old)
    if n != 1:
        raise SystemExit("[template_patch] %s 锚点数量=%d（应为 1），基线模板已变化" % (name, n))
    PATCHES.append(name)
    return text.replace(old, new, 1)


def _re(text, pattern, new, name):
    rx = re.compile(pattern, re.S)
    found = rx.findall(text)
    if len(found) != 1:
        raise SystemExit("[template_patch] %s 正则命中=%d（应为 1），基线模板已变化" % (name, len(found)))
    PATCHES.append(name)
    return rx.sub(lambda m: new, text, count=1)


AGG_OLD = r'''function aggregateSuite(obj){
  if (!obj || typeof obj !== "object" || Array.isArray(obj))
    return { ok:false, error:"文件内容不是一个 JSON 对象" };
  const arr = obj.userMusicResults;
  if (!Array.isArray(arr))
    return { ok:false, error:"这看起来不是 haruki 的 suite 数据（缺少 userMusicResults 数组）" };
  const status = Object.create(null);
  let n = 0;
  for (let i = 0; i < arr.length; i++){
    const r = arr[i];
    if (!r || typeof r !== "object") continue;
    if (r.musicDifficultyType !== "master") continue;
    const id = parseInt(r.musicId, 10);
    if (!isFinite(id)) continue;
    let e = status[id];
    if (!e){ e = status[id] = { played:1, fc:0, ap:0, hs:0 }; n++; }
    if (r.fullComboFlg) e.fc = 1;
    if (r.fullPerfectFlg) e.ap = 1;
    const hs = parseInt(r.highScore, 10) || 0;
    if (hs > e.hs) e.hs = hs;
  }
  if (!n) return { ok:false, error:"这份数据里没有 MASTER 难度的游玩记录" };
  const t = parseInt(obj.upload_time, 10);
  return { ok:true, status, uploadTime: (isFinite(t) && t > 0) ? t : null, n };
}'''

AGG_NEW = r'''/* ---------- 谱面身份（唯一 key）----------
   MASTER 继续用原数字 musicId（JSON 属性会字符串化为 "315"，旧备份天然兼容）；
   EXPERT 用 "expert:<musicId>"。同一首歌两种难度是两张独立谱面，FC/次数/详情互不覆盖。 */
function chartKey(musicId, difficulty){
  const n = parseInt(musicId, 10);
  if (!isFinite(n) || n <= 0) return null;
  return difficulty === "expert" ? ("expert:" + n) : n;
}
function validChartKey(k){
  return /^\d{1,7}$/.test(String(k)) || /^expert:\d{1,7}$/.test(String(k));
}
/* 把 haruki suite 的 userMusicResults 聚合成「每张谱面的状态」。
   口径：master / expert 都解析；played=有记录；fc=任一 fullComboFlg；
        ap=任一 fullPerfectFlg；hs=最大 highScore。两张难度分别累计。 */
function aggregateSuite(obj){
  if (!obj || typeof obj !== "object" || Array.isArray(obj))
    return { ok:false, error:"文件内容不是一个 JSON 对象" };
  const arr = obj.userMusicResults;
  if (!Array.isArray(arr))
    return { ok:false, error:"这看起来不是 haruki 的 suite 数据（缺少 userMusicResults 数组）" };
  const status = Object.create(null);
  let n = 0, nMaster = 0, nExpert = 0;
  for (let i = 0; i < arr.length; i++){
    const r = arr[i];
    if (!r || typeof r !== "object") continue;
    const dt = String(r.musicDifficultyType || "");
    if (dt !== "master" && dt !== "expert") continue;
    const id = chartKey(r.musicId, dt);
    if (id == null) continue;
    let e = status[id];
    if (!e){
      e = status[id] = { played:1, fc:0, ap:0, hs:0, difficulty:dt,
                         musicId:parseInt(r.musicId, 10) };
      n++; if (dt === "expert") nExpert++; else nMaster++;
    }
    if (r.fullComboFlg) e.fc = 1;
    if (r.fullPerfectFlg) e.ap = 1;
    const hs = parseInt(r.highScore, 10) || 0;
    if (hs > e.hs) e.hs = hs;
  }
  if (!n) return { ok:false, error:"这份数据里没有 MASTER/EXPERT 难度的游玩记录" };
  const t = parseInt(obj.upload_time, 10);
  return { ok:true, status, uploadTime: (isFinite(t) && t > 0) ? t : null,
           n, nMaster, nExpert };
}'''

ANA_OLD_RE = r"function buildAnalysis\(songs, stateOf\)\{.*?\n\}\n/\*__PJSK_CORE_END__\*/"

ANA_NEW = r'''/* 单标签统计：按难度分别做（EXPERT 不套用 MASTER 的标签 z）。 */
function _tagStatsFor(rows, stateOf){
  const MIN = 10, BAND = 0.5;
  const played = rows.filter(s => stateOf(s.id) && s.teishu != null);
  const bands = new Map();
  played.forEach(s => {
    const key = Math.round(s.teishu / BAND) * BAND;
    if (!bands.has(key)) bands.set(key, []);
    bands.get(key).push(s);
  });
  const tagMap = new Map();
  bands.forEach(group => {
    const n = group.length;
    if (n <= 1) return;
    const nFc = group.filter(s => _isFCany(stateOf(s.id))).length;
    group.forEach(s => {
      const own = _isFCany(stateOf(s.id)) ? 1 : 0;
      const p = (nFc - own) / (n - 1);
      (s.elems || []).forEach(tag => {
        if (!tagMap.has(tag)) tagMap.set(tag, []);
        tagMap.get(tag).push({ p: p, own: own, s: s });
      });
    });
  });
  const out = [];
  tagMap.forEach((items, tag) => {
    if (items.length < MIN) return;
    const actual = items.reduce((a, i) => a + i.own, 0);
    const expected = items.reduce((a, i) => a + i.p, 0);
    const varr = items.reduce((a, i) => a + i.p * (1 - i.p), 0);
    if (varr <= 1e-9) return;
    const z = (actual - expected) / Math.sqrt(varr);
    const examples = items.filter(i => !i.own)
      .sort((a, b) => a.s.teishu - b.s.teishu).slice(0, 3)
      .map(i => ({ id:i.s.id, chartId:i.s.id, difficulty:i.s.difficulty || "master",
                   name:i.s.disp || i.s.jp, lv:i.s.lv, teishu:i.s.teishu }));
    out.push({ tag:tag, n:items.length, fc:actual,
               fcRate: Math.round(actual / items.length * 1000) / 1000,
               expected: Math.round(expected * 10) / 10,
               z: Math.round(z * 100) / 100, examples: examples });
  });
  out.sort((a, b) => a.z - b.z);
  return out;
}
const _isFCany = u => !!(u && (u.fc || u.ap));

/* B50 + 提升空间 + 苦手/擅长 + 水平报告。
   算法与 scripts/build_analysis.py 逐行对应：
     B50      —— A 套：只算 FC/AP，score = 定数 + (AP ? 1.5 : 0)，rating = 前 50 之和 / 50
                  MASTER + EXPERT 混合，每张谱面按自己的 chartId 独立；同曲两难度可同时入榜。
                  同分稳定顺序：分数降序 → MASTER 先于 EXPERT → musicId 升序。
     苦手/擅长 —— 每个难度各自 0.5 一层 + 留一法基线 + z 检验，样本 < 10 不列入；
                  两张难度的标签 z 绝不互相套用。 */
function buildAnalysis(songs, stateOf){
  const MIN_TAG_SAMPLES = 10;
  const r2 = x => Math.round(x * 100) / 100;

  /* ---- 混合 B50 ---- */
  const pool = [];
  songs.forEach(s => {
    const u = stateOf(s.id);
    if (!_isFCany(u) || s.teishu == null || s.unrel) return;
    const diff = s.difficulty || "master";
    pool.push({ musicId: s.musicId == null ? s.id : s.musicId, chartId: s.id,
                difficulty: diff,
                score: r2(s.teishu + (u.ap ? 1.5 : 0)),
                teishu: s.teishu, ap: !!u.ap, lv: s.lv });
  });
  pool.sort((a, b) => (b.score - a.score)
    || ((a.difficulty === "expert") - (b.difficulty === "expert"))
    || (a.musicId - b.musicId));
  const top = pool.slice(0, 50);
  const b50 = {
    n: 50, count: top.length,
    rating: top.length >= 50 ? r2(top.reduce((a, e) => a + e.score, 0) / 50) : null,
    list: top,
  };
  const cut = top.length >= 50 ? top[top.length - 1].score : 0;

  /* ---- 提升空间：打过未 FC，且定数高于榜尾门槛（FC 掉就能进榜）---- */
  const gains = [];
  songs.forEach(s => {
    const u = stateOf(s.id);
    if (!u || _isFCany(u) || s.unrel || s.teishu == null || s.teishu <= cut) return;
    const diff = s.difficulty || "master";
    gains.push({ musicId: s.musicId == null ? s.id : s.musicId, chartId: s.id,
                 difficulty: diff, name: s.disp || s.jp, lv: s.lv, teishu: s.teishu,
                 gain: r2(s.teishu - cut), highScore: u.hs || 0 });
  });
  gains.sort((a, b) => (b.teishu - a.teishu)
    || ((a.difficulty === "expert") - (b.difficulty === "expert"))
    || (a.musicId - b.musicId));
  const optimistic = pool.map(e => e.score).concat(gains.map(g => g.teishu))
    .sort((a, b) => b - a).slice(0, 50);
  const b50opt = optimistic.length >= 50 ? r2(optimistic.reduce((a, b) => a + b, 0) / 50) : null;

  /* ---- 苦手 / 擅长：按难度分别统计 ---- */
  const statsByDiff = {}, zmapByDiff = {};
  ["master", "expert"].forEach(d => {
    statsByDiff[d] = _tagStatsFor(songs.filter(s => (s.difficulty || "master") === d), stateOf);
    const z = {};
    statsByDiff[d].forEach(t => { z[t.tag] = t.z; });
    zmapByDiff[d] = z;
  });
  const tags = statsByDiff.master;
  const weak = tags.filter(t => t.z <= -0.5).slice(0, 8);
  const strong = tags.slice().reverse().filter(t => t.z >= 0.5).slice(0, 8);
  const pick = (d, kind) => (kind === "weak"
    ? statsByDiff[d].filter(t => t.z <= -0.5).slice(0, 8)
    : statsByDiff[d].slice().reverse().filter(t => t.z >= 0.5).slice(0, 8));
  const tagZ = zmapByDiff.master;

  /* ---- 水平报告素材 ---- */
  const firstMax = (arr, better) => arr.length ? arr.reduce((a, b) => better(a, b) ? a : b) : null;
  const fcRows = songs.filter(s => _isFCany(stateOf(s.id)));
  const unfcPlayed = songs.filter(s => {
    const u = stateOf(s.id); return u && !_isFCany(u) && s.teishu != null && !s.unrel;
  });
  const highest = firstMax(fcRows, (a, b) => (a.teishu || 0) >= (b.teishu || 0));
  const easiestMiss = firstMax(unfcPlayed, (a, b) => a.teishu <= b.teishu);
  const hardestMiss = firstMax(unfcPlayed, (a, b) => a.teishu >= b.teishu);
  const live = songs.filter(s => !s.unrel);
  const liveFc = live.filter(s => _isFCany(stateOf(s.id))).length;
  const brief = o => o ? { id:o.id, chartId:o.id, difficulty:o.difficulty || "master",
                           name:o.disp || o.jp, lv:o.lv, teishu:o.teishu } : null;
  const report = {
    b50Rating: b50.rating, b50Optimistic: b50opt,
    prog: { total: live.length, fc: liveFc,
            ap: live.filter(s => (stateOf(s.id) || {}).ap).length,
            pct: live.length ? Math.round(liveFc / live.length * 1000) / 10 : 0 },
    highest: brief(highest), easiestMiss: brief(easiestMiss), hardestMiss: brief(hardestMiss),
    nUnfcPool: unfcPlayed.length,
  };
  return { b50: b50, gainCut: cut, gains: gains.slice(0, 20), nGains: gains.length,
           weak: weak, strong: strong,
           weakByDiff: { master: pick("master", "weak"), expert: pick("expert", "weak") },
           strongByDiff: { master: pick("master", "strong"), expert: pick("expert", "strong") },
           tagPool: songs.filter(s => stateOf(s.id) && s.teishu != null).length,
           tagTotal: new Set([].concat(statsByDiff.master, statsByDiff.expert).map(t => t.tag)).size,
           zmap: tagZ, zmapByDiff: zmapByDiff, tagZ: tagZ,
           report: report };
}
/*__PJSK_CORE_END__*/'''


def split_stats(text):
    source=(Path(__file__).resolve().parents[1]/'web/stats_by_difficulty.js').read_text(encoding='utf-8').strip()
    function=source[source.index('function renderStats(){'):]
    text,count=re.subn(r'function renderStats\(\)\{.*?\n\}',lambda _:function,text,count=1,flags=re.S)
    if count!=1:raise SystemExit('renderStats锚点不唯一或缺失')
    return text

def apply(text):
    if 'function chartKey(' in text and 'id="dExpert"' in text:
        return split_stats(text)  # 已组合模板仍同步统计渲染，其他补丁不重复应用。
    PATCHES.clear()

    # 1) suite 聚合：两种难度 + 唯一 key
    text = _re(text, r"function aggregateSuite\(obj\)\{.*?\n\}", AGG_NEW, "aggregateSuite")

    # 2) 混合 B50 + 分难度标签
    text = _re(text, ANA_OLD_RE, ANA_NEW, "buildAnalysis")

    # 3) 难度筛选状态
    text = _one(
        text,
        'const S = { q:"", sort:"teishu", dir:1, fc:false, never:false, tried:false, quick:false, green:false,\n'
        '            var:false, low:false, hide:false, unrel:false, view:"cards", lv:new Set() };',
        'const S = { q:"", sort:"teishu", dir:1, fc:false, never:false, tried:false, quick:false, green:false,\n'
        '            var:false, low:false, hide:false, unrel:false, diff:"all", view:"cards", lv:new Set() };',
        "state.diff")

    # 4) 工具栏：难度筛选（只影响浏览；B50 始终混合）
    text = _one(
        text,
        '  <div class="sep"></div>\n  <span class="lbl">状态</span>',
        '  <div class="sep"></div>\n'
        '  <span class="lbl">难度</span>\n'
        '  <button id="dAll" class="on" title="浏览列表按难度筛选；B50 始终 MASTER+EXPERT 混合，不受这里影响">全部</button>\n'
        '  <button id="dMaster" title="只看 MASTER 谱面（B50 仍混合）">MASTER</button>\n'
        '  <button id="dExpert" title="只看 EXPERT 谱面（B50 仍混合）">EXPERT</button>\n'
        '  <div class="sep"></div>\n  <span class="lbl">状态</span>',
        "listbar.diff")

    # 4b) 难度筛选绑定（只切浏览列表；B50/分析读 DATA.analysis，不受影响）
    text = _one(
        text,
        'toggle("fVar","var"); toggle("fLow","low"); toggle("fUnrel","unrel"); toggle("fHide","hide");',
        'toggle("fVar","var"); toggle("fLow","low"); toggle("fUnrel","unrel"); toggle("fHide","hide");\n'
        '/* 难度筛选：只切浏览列表；B50/分析读 DATA.analysis，不受影响 */\n'
        'const setDiff = d => {\n'
        '  S.diff = d;\n'
        '  [["dAll","all"],["dMaster","master"],["dExpert","expert"]].forEach(([id, v]) => {\n'
        '    const el = document.getElementById(id);\n'
        '    if (el) el.classList.toggle("on", d === v);\n'
        '  });\n'
        '  render();\n'
        '};\n'
        'document.getElementById("dAll").onclick = () => setDiff("all");\n'
        'document.getElementById("dMaster").onclick = () => setDiff("master");\n'
        'document.getElementById("dExpert").onclick = () => setDiff("expert");',
        "diff.bind")

    # 5) 列表过滤 + 搜索
    text = _one(
        text,
        '    // 未实装曲目默认隐藏（国服还没上线，打不了）\n'
        '    if (!S.unrel && s.unrel) return false;',
        '    // 未实装曲目默认隐藏（国服还没上线，打不了）\n'
        '    if (!S.unrel && s.unrel) return false;\n'
        '    // 难度筛选只控制浏览列表；B50 用 DATA.analysis，与本筛选无关\n'
        '    if (S.diff !== "all" && s.difficulty !== S.diff) return false;',
        "compute.diff")
    text = _one(
        text,
        '      const hay = [s.disp, s.cn, s.jp, s.alias, s.id].join(" ").toLowerCase();',
        '      const hay = [s.disp, s.cn, s.jp, s.alias, s.id, s.musicId, s.difficulty]\n'
        '        .join(" ").toLowerCase();',
        "compute.search")

    text = _one(text,
                '  ["fc","never","tried","quick","green","var","low","unrel","hide"].forEach(k => S[k] = false);',
                '  ["fc","never","tried","quick","green","var","low","unrel","hide"].forEach(k => S[k] = false);\n'
                '  S.diff = "all";',
                "reset.diffState")
    text = _one(text,
                '  document.querySelectorAll("#listbar button").forEach(b => b.classList.remove("on"));',
                '  document.querySelectorAll("#listbar button").forEach(b => b.classList.remove("on"));\n'
                '  const dAllBtn = document.getElementById("dAll");\n'
                '  if (dAllBtn) dAllBtn.classList.add("on");',
                "reset.diffUI")

    # 6) 卡片：难度标签
    text = _one(
        text,
        '  if (s.bpmVar) t.push(\'<span class="tag v">速度变化</span>\');',
        '  t.push(\'<span class="tag \' + (s.difficulty === "expert" ? "de" : "dm") + \'">\'\n'
        '         + (s.difficulty === "expert" ? "EXPERT" : "MASTER") + \'</span>\');\n'
        '  if (s.bpmVar) t.push(\'<span class="tag v">速度变化</span>\');',
        "card.diff")

    # 7) 表格：曲名格里加难度
    text = _one(
        text,
        "    <td>${esc(s.disp)}${s.basis==='alias'?' <span class=\"tag t\">译</span>':''}",
        "    <td><span class=\"tag ${s.difficulty==='expert'?'de':'dm'}\">"
        "${s.difficulty==='expert'?'EXPERT':'MASTER'}</span>${esc(s.disp)}"
        "${s.basis==='alias'?' <span class=\"tag t\">译</span>':''}",
        "table.diff")

    # 8) B50：按 chartId 取谱面，保留 musicId；行上标难度
    text = _one(text, '  songs.forEach(s => byId[s.id] = s);',
                '  songs.forEach(s => byId[String(s.id)] = s);', "b50.byId")
    text = _one(text, '    const s = byId[e.musicId] || {};',
                '    const s = byId[String(e.chartId != null ? e.chartId : e.musicId)] || {};',
                "b50.song")
    text = _one(text, '    return `<div class="brow ${i<3?\'top3\':\'\'}" data-id="${e.musicId}">',
                '    const dc = e.difficulty === "expert" ? "de" : "dm";\n'
                '    return `<div class="brow ${i<3?\'top3\':\'\'}" '
                'data-id="${e.chartId != null ? e.chartId : e.musicId}">',
                "b50.row")
    text = _one(text,
                '        <div class="mt">Lv${e.lv}　·　社区定数 ${e.teishu}</div></div>',
                '        <div class="mt"><span class="tag ${dc}">'
                '${e.difficulty === "expert" ? "EXPERT" : "MASTER"}</span>'
                'Lv${e.lv}　·　社区定数 ${e.teishu}</div></div>',
                "b50.mt")
    text = _one(text, '    const s = byId[g.musicId] || {};',
                '    const s = byId[String(g.chartId != null ? g.chartId : g.musicId)] || {};',
                "gains.song")
    text = _one(text, '    return `<div class="brow" data-id="${g.musicId}">',
                '    const gc = g.difficulty === "expert" ? "de" : "dm";\n'
                '    return `<div class="brow" '
                'data-id="${g.chartId != null ? g.chartId : g.musicId}">',
                "gains.row")
    text = _one(text,
                '        <div class="mt">Lv${g.lv}　·　定数 ${g.teishu}　·　当前最高分 ${g.highScore || "—"}</div></div>',
                '        <div class="mt"><span class="tag ${gc}">'
                '${g.difficulty === "expert" ? "EXPERT" : "MASTER"}</span>'
                'Lv${g.lv}　·　定数 ${g.teishu}　·　当前最高分 ${g.highScore || "—"}</div></div>',
                "gains.mt")
    text = text.replace('openModal(Number(el.dataset.id))', 'openModal(el.dataset.id)')
    PATCHES.append("openModal.datasetId")

    # 9) B50 文案：说明混合口径
    text = _one(
        text,
        '        算法：AP = 定数+1.5，FC = 定数，取前 ${b.n} 之和 ÷ ${b.n}<br>',
        '        MASTER + EXPERT 混合：同一首歌两种难度各自独立，可同时入榜<br>\n'
        '        算法：AP = 定数+1.5，FC = 定数，取前 ${b.n} 之和 ÷ ${b.n}<br>',
        "b50.note")

    # 10) 按谱面取 z 表
    text = _one(text,
                'function quickZmap(){ return (A && (A.zmap || A.tagZ)) || null; }',
                'function quickZmap(s){\n'
                '  const by = A && A.zmapByDiff;\n'
                '  if (by && s && by[s.difficulty]) return by[s.difficulty];\n'
                '  return (A && (A.zmap || A.tagZ)) || null;\n'
                '}',
                "quickZmap")
    text = text.replace('const zm = quickZmap();', 'const zm = quickZmap(s);')
    PATCHES.append("quickZmap.callers")
    if 'function persHint(' in text:
        text = _one(text, '  const zm = quickZmap() || {};', '  const zm = quickZmap(s) || {};',
                    "persHint.zmap")
    text = _one(text, '  const zmapQ = (A && (A.zmap || A.tagZ)) || null;',
                '  const zmapQ = quickZmap(s);', "openModal.zmap")

    # 11) applyStatus：每张谱面用自己的难度 z 表
    text = _one(text, '  const b50 = (A.b50 || {}).rating, cut = A.gainCut, zmap = A.zmap || {};',
                '  const b50 = (A.b50 || {}).rating, cut = A.gainCut;', "applyStatus.zmap")
    text = _one(text, '    const q = quickFields(s, b50, cut, zmap);',
                '    const q = quickFields(s, b50, cut, '
                '((A.zmapByDiff || {})[s.difficulty] || A.zmap || {}));',
                "applyStatus.quick")

    # 12) 详情按复合 key 查找 + 标难度/musicId
    text = _one(text,
                'function openModal(id){\n  const s = DATA.songs.find(x => x.id === id);',
                'function openModal(id){\n'
                '  const s = DATA.songs.find(x => String(x.id) === String(id));',
                "openModal.lookup")
    text = _one(text, '<div class="jp2">${esc(s.jp)}　·　musicId ${s.id}',
                '<div class="jp2">${esc(s.jp)}　·　'
                '${s.difficulty === "expert" ? "EXPERT" : "MASTER"}　·　'
                'musicId ${s.musicId != null ? s.musicId : s.id}',
                "openModal.header")
    text = _one(text, '    <h3>难点 / 攻略<span class="src">译自 pjsekai.com 楽曲難易度表 MASTER</span></h3>',
                '    <h3>难点 / 攻略<span class="src">'
                '译自 pjsekai.com 楽曲難易度表 ${s.tipsSrc || "MASTER"}</span></h3>',
                "tips.source")

    # 13) 导入备份：先校验、后写入；非法 key 忽略，绝不部分写坏
    text = _one(
        text,
        '      const m = (j && j.marks) ? j.marks : j;',
        '      if (!j || typeof j !== "object" || Array.isArray(j))\n'
        '        throw new Error("备份文件不是 JSON 对象");\n'
        '      const hasMarks = Object.prototype.hasOwnProperty.call(j, "marks");\n'
        '      const hasPlays = Object.prototype.hasOwnProperty.call(j, "plays");\n'
        '      const m = hasMarks ? j.marks : (hasPlays ? {} : j);',
        "import.m")
    text = _one(
        text,
        '      const p = (j && j.plays) || {};',
        '      const p = hasPlays ? j.plays : {};\n'
        '      if (!m || typeof m !== "object" || Array.isArray(m) ||\n'
        '          !p || typeof p !== "object" || Array.isArray(p))\n'
        '        throw new Error("marks/plays 必须是对象；本次导入未改动任何数据");',
        "import.p")
    text = _one(
        text,
        '      Object.keys(m || {}).forEach(k => { if (!done[k]) { done[k] = 1; n++; } });',
        '      const addMarks = {}, addPlays = {};\n'
        '      Object.keys(m).forEach(k => {\n'
        '        if (!validChartKey(k)) return;   // 非法 key 忽略；纯数字 key 继续代表 MASTER\n'
        '        if (!done[k]) addMarks[k] = 1;\n'
        '      });',
        "import.marks")
    text = _one(
        text,
        '      Object.keys(p || {}).forEach(k => {\n'
        '        const v = Math.max(1, parseInt(p[k], 10) || 1);\n'
        '        // 与同步合并一致：旧备份不能减少已记录的次数；需要减少时在曲目详情里修改。\n'
        '        if (v > getPlays(k)) { plays[k] = v; np++; }\n'
        '      });',
        '      Object.keys(p).forEach(k => {\n'
        '        if (!validChartKey(k)) return;\n'
        '        const v = Math.max(1, Math.min(9999, parseInt(p[k], 10) || 1));\n'
        '        // 与同步合并一致：旧备份不能减少已记录的次数；需要减少时在曲目详情里修改。\n'
        '        if (v > getPlays(k)) addPlays[k] = v;\n'
        '      });\n'
        '      Object.keys(addMarks).forEach(k => { done[k] = 1; n++; });\n'
        '      Object.keys(addPlays).forEach(k => { plays[k] = addPlays[k]; np++; });',
        "import.plays")

    # 14) 导出：v3 + 口径说明（key 本身已区分难度）
    text = _one(text,
                '{ v: 2, snapshot: DATA.meta.snapshot, marks: done, plays: plays }',
                '{ v: 3, snapshot: DATA.meta.snapshot, charts: "master=数字 musicId；expert=expert:<musicId>",\n'
                '      marks: done, plays: plays }',
                "export.v3")

    # 15) 统计条：谱面总数 + 分难度
    text = _one(text,
                '      ["c", m.totalMaster, "MASTER 谱面"],\n'
                '      ["g", m.releasedMaster, "国服已实装"],\n'
                '      ["v", m.unreleased, "未实装"],\n'
                '      ["y", m.withTips, "有攻略"],\n'
                '      ["d", m.aliased, "社区中文译名"],\n'
                '      ["p", m.bpmVar, "速度变化谱"],',
                '      ["c", m.totalCharts, "谱面（M+E）"],\n'
                '      ["g", m.releasedCharts, "国服已实装"],\n'
                '      ["v", m.unreleased, "未实装"],\n'
                '      ["y", m.withTips, "有攻略"],\n'
                '      ["d", m.totalExpert, "EXPERT 谱面"],\n'
                '      ["p", m.expertCommunity || 0, "EXPERT 社区定数"],',
                "stats.library")
    text = _one(text, '  const unfcN = m.releasedMaster - fcN;',
                '  const unfcN = m.releasedCharts - fcN;', "stats.unfc")
    text = _one(text, '  const pct = fcN / m.releasedMaster * 100;',
                '  const pct = fcN / m.releasedCharts * 100;', "stats.pct")
    text = _one(text,
                '  document.getElementById("snap").textContent = "全量 " + m.totalMaster + " 首 · "',
                '  document.getElementById("snap").textContent = "全量 " + m.totalCharts + " 张谱面 · "',
                "stats.snap")
    text = _one(text, '  const unfcN = m.releasedMaster - fcN;\n', '', "stats.dup") if False else text
    text = _one(text, '    `显示 ${list.length} / ${DATA.songs.length} 首`',
                '    `显示 ${list.length} / ${DATA.songs.length} 张谱面`', "render.cnt")

    # 16) 导入提示：两种难度
    text = _one(text,
                '" · MASTER " + Object.keys(suiteStatus).length + " 首";',
                '" · 谱面 " + Object.keys(suiteStatus).length + " 张";',
                "suiteInfo.count")
    text = _one(text,
                '    const ok = "导入成功：MASTER 有成绩 " + k.length + " 首 · FC " '
                '+ k.filter(x => suiteStatus[x].fc).length',
                '    const ok = "导入成功：有成绩 " + k.length + " 张谱面（MASTER+EXPERT）· FC " '
                '+ k.filter(x => suiteStatus[x].fc).length',
                "suite.importMsg")

    # 17) 分析报告：分难度展示，不把 MASTER 标签套给 EXPERT
    text = _one(text,
                '  const weak = A.weak || [], strong = A.strong || [];\n'
                '  const persona = buildPersona();',
                '  const weak = A.weak || [], strong = A.strong || [];\n'
                '  const weakBy = A.weakByDiff || {}, strongBy = A.strongByDiff || {};\n'
                '  const persona = buildPersona();',
                "report.maps")
    text = _one(text,
                '    <div class="sechead"><b>苦手配置</b>\n'
                '      <span class="src">z 越负 = 含该要素的曲子，比同定数水平的其他曲子更难 FC</span></div>\n'
                '    <div class="bars">${weak.map(t => barRow(t, "weak")).join("") || \'<div class="hint">样本不足</div>\'}</div>',
                '    ${["master","expert"].map(d => `\n'
                '    <div class="sechead"><b>${d === "expert" ? "EXPERT" : "MASTER"} 苦手配置</b>\n'
                '      <span class="src">同难度内按定数分层；z 越负越难 FC（两难度不共用标签 z）</span></div>\n'
                '    <div class="bars">${((d === "master" ? weak : null) || weakBy[d] || []).map(t => barRow(t, "weak")).join("") || \'<div class="hint">样本不足</div>\'}</div>`).join("")}',
                "report.weak")
    text = _one(text,
                '    <div class="sechead"><b>擅长配置</b>\n'
                '      <span class="src">z 越正 = 这类要素你反而比同水平更稳</span></div>\n'
                '    <div class="bars">${strong.map(t => barRow(t, "strong")).join("") || \'<div class="hint">样本不足</div>\'}</div>',
                '    ${["master","expert"].map(d => `\n'
                '    <div class="sechead"><b>${d === "expert" ? "EXPERT" : "MASTER"} 擅长配置</b>\n'
                '      <span class="src">同难度内按定数分层；z 越正 = 这类要素你反而比同水平更稳</span></div>\n'
                '    <div class="bars">${((d === "master" ? strong : null) || strongBy[d] || []).map(t => barRow(t, "strong")).join("") || \'<div class="hint">样本不足</div>\'}</div>`).join("")}',
                "report.strong")
    text = _one(text, '<div class="lb">MASTER 已 FC</div>', '<div class="lb">已 FC 谱面</div>',
                "report.fcLabel")

    # 18) 页脚口径
    text = _one(text,
                '  <b>状态</b>：已 FC = 该曲 MASTER 有 full_combo / full_perfect 记录（或你在本地标了已 FC）；「打过未 FC」= 有成绩但没 FC；「没打过」= 无 MASTER 游玩记录；',
                '  <b>状态</b>：已 FC = 该谱面（MASTER 或 EXPERT）有 full_combo / full_perfect 记录（或你在本地标了已 FC）；「打过未 FC」= 有成绩但没 FC；「没打过」= 无该谱面游玩记录；',
                "footer.status")
    text = _one(text,
                '映射 最下位−0 / 最下位0.2 / 下位0.4 / 適正0.5 / 上位0.7 / 最上位0.9 / 最上位＋0.95）；',
                '映射 最下位−0 / 最下位0.2 / 下位0.4 / 適正0.5 / 上位0.7 / 最上位0.9 / 最上位＋0.95）；'
                'MASTER 用 MASTER 表、EXPERT 用 EXPERT 表；EXPERT 无社区数据时标「低可信」源C兜底，不冒充社区定数；',
                "footer.teishu")

    text = _one(text,
                '    document.getElementById("snap").textContent = "全量 " + m.totalMaster + " 首 · 未导入成绩";',
                '    document.getElementById("snap").textContent = "全量 " + m.totalCharts + " 张谱面 · 未导入成绩";',
                "stats.snapLibrary")
    text = _one(text, '<title>PJSK MASTER 定数表（全量）</title>',
                '<title>PJSK MASTER / EXPERT 定数表（全量）</title>', "title.head")
    text = _one(text,
                '  <b>难点/攻略</b>：译自 pjsekai.com「楽曲難易度表 MASTER」的要素标签与说明文字，',
                '  <b>难点/攻略</b>：译自 pjsekai.com「楽曲難易度表 MASTER / EXPERT」的对应难度要素标签与说明文字（不互相复用），',
                "footer.tips")

    # 19) 主题样式：难度标签
    # Keep approved responsive overrides last, matching the live reviewed CSS.
    css_anchor = '/* PJSK mobile controls: 2026-10-31 */' if '/* PJSK mobile controls: 2026-10-31 */' in text else '</style>\n</head>'
    text = _one(text, css_anchor,
                '/* 难度标签（MASTER 紫 / EXPERT 粉） */\n'
                '.tag.dm{background:#ad45df18;border:1px solid #ad45df55;color:#c98cf0}\n'
                '.tag.de{background:#ed477118;border:1px solid #ed477155;color:#ff7fa2}\n'
                + css_anchor, "css.diff")

    # 20) 标题
    text = _one(text, '<h1>PJSK MASTER 定数表</h1>',
                '<h1>PJSK MASTER / EXPERT 定数表</h1>', "title")

    return split_stats(text)


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else str(
        __import__("pathlib").Path(__file__).resolve().parent / "inputs/_template.html")
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    out = apply(open(src, encoding="utf-8").read())
    if dst:
        open(dst, "w", encoding="utf-8").write(out)
    print("applied %d patches -> %s" % (len(PATCHES), dst or "(stdout only)"))
