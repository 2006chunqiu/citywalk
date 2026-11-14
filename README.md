# 漫步江城 · City Walk 路线推荐系统

面向武汉的兴趣导向型 City Walk 步行路线推荐 Web 应用。

## 当前状态

前端目录已清空，等待 React 版源码合入。后端保留（组员正在其上开发），文档与数据保留。

| 目录 | 内容 | 归属 | 状态 |
|---|---|---|---|
| `frontend/` | 前端 | 待合入（React 版源码） | **空，等待合入** |
| `backend/` | FastAPI 服务 | 骨架 + 组员开发中的召回/路径/校验 | 有效 |
| `data/` | 点位数据（组员 193 条 + OSM 1164 条） | 共有 | 有效 |
| `docs/` | 接口契约、协作说明 | 共有 | 有效 |
| `scripts/` | 点位采集与分析脚本 | 共有 | 有效 |

## 后端启动

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
uvicorn app.main:app --reload --port 8000
```

接口文档：http://localhost:8000/docs

后端依赖分层说明：

| 层 | 文件 | 说明 |
|---|---|---|
| 算法 | `app/algo/scoring.py` | 五因子打分与约束求解，有单测 |
| 召回 | `app/services/recall.py` | 种子库优先 + 高德合并类型召回 |
| 路径 | `app/services/routing.py` | 分段步行规划与几何拼接 |
| 校验 | `app/services/validate.py` | 四类结果校验 |
| 意图 | `app/services/intent.py` | 自然语言输入转标签 |
| 外部 | `app/services/amap.py` | 高德接口封装 + Key 池 |
| 数据 | `app/services/poi_repo.py` | 点位数据访问 |

改这几个文件前先在群里说一声，它们是多人共用的。

## 数据

| 文件 | 条数 | 来源 |
|---|---|---|
| `data/poi.csv` | 193 | 组员整理 |
| `data/poi_from_osm.csv` | 771 | OpenStreetMap 采集，坐标已转 GCJ-02 |
| `data/poi_seed_200.csv` | 200 | 按标签平衡抽样 |
| `data/POI采集报告.md` | — | 分布统计与质量评估 |

OSM 采集脚本可重跑：

```powershell
python scripts/collect_osm_poi.py       # 全量采集
python scripts/collect_missing.py park  # 补采某一类
python scripts/analyze_poi.py           # 生成质量报告
```

## 前端合入说明

React 版前端的源码需要放进 `frontend/`。提交前必须做三件事：

1. **删除硬编码的高德 Key**，改为读环境变量 `VITE_AMAP_JS_KEY` / `VITE_AMAP_JS_SECRET`
2. **不要提交** `node_modules`、`dist`、`.netlify`、`.env`
3. **必须提交** `netlify/functions/`，否则 DeepSeek 与高德代理会失效

## 恢复旧脚手架

切换到最初版本的 Vue 脚手架，历史里还在：

```powershell
git log --all --oneline -- frontend/
git checkout <commit> -- frontend
```

## Git 代理

本机需经代理访问 GitHub，否则 `git push` 会报 `Failed to connect to github.com:443`：

```powershell
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

## 协作三条

1. **一个仓库，一个主分支。** 都在 `main` 上干，动手前先 `git pull`，推之前再 `git pull`。
2. **接口字段以 `docs/api.md` 为准。** 想改字段名或类型，先在群里说，改完同步更新。
3. **动手前说一句。** 要改别人可能也在改的文件，群里发一句「我改 xxx」，改完说「推了」。
