# data/ — 公开数据

这里只有**公开数据**，没有任何玩家成绩。个人数据（suite 快照、合并 CSV、`master_all.json`、
`analysis.json`、封面图）一律不进仓库，如需重建请见根 README 的「从头重建」。

| 文件 | 内容 | 来源 |
|---|---|---|
| `cn_master_musics.json` | 国服曲目 master（曲名 / 封面 assetbundleName / 上线时间） | haruki-sekai-sc-master（国服 master 抓取） |
| `cn_master_musicDifficulties.json` | 国服各难度谱面（星级 / 物量） | 同上 |
| `pjsekai_master_8level.json` | 日服 MASTER「楽曲難易度表」8 档分类（含判定日期） | pjsekai.com（`parse_pjsekai_8level.py`） |
| `pjsekai_tips.json` | 每曲要素标签 + 難所说明（日文原文） | pjsekai.com（`parse_pjsekai_tips.py`） |
| `pjsekai_tips_zh.json` | 上表的中文译本（术语按中文音游圈口径） | `translate_tips.py` 生成，译名口径见 `pjsk_glossary.json` |
| `pjsk_glossary.json` | 音游术语词表（要素译名 + 术语对照 + 翻译风格要求） | 萌娘百科「音乐游戏/用语」等社区口径 |
| `moegirl_bpm.json` | BPM / 时长（含 BPM 区间 = 速度变化谱） | 萌娘百科歌曲表（`parse_moegirl_bpm.py`） |
| `moegirl_names.json` | 社区中文译名（日文名 → 译名） | 萌娘百科（`parse_moegirl_names.py`） |

数据版权归各来源所有，本仓库仅作整理与翻译，供玩家交流使用。
