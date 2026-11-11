# 漫步江城 · City Walk 路线推荐系统

面向武汉的兴趣导向型 City Walk 步行路线推荐 Web 应用。输入起终点与兴趣标签，系统召回真实 POI、打分排序、生成带途经点的步行路线，并给出三条备选方案。

## 技术栈

- 前端：Vue 3 + Vite + 高德 JS API 2.0
- 后端：Python 3.11+ / FastAPI
- 数据：PostgreSQL（可选 PostGIS）+ Redis（缓存，可先用内存字典代替）
- 部署：前端静态托管，后端单机进程

## 目录

```
citywalk/
├─ frontend/          前端工程
├─ backend/           后端工程
├─ data/              种子库、标签映射表（CSV）
├─ docs/              接口表、协作说明
├─ AGENTS.md          给 AI 的项目说明书
└─ .env.example       环境变量模板（真实 .env 不进仓库）
```

## 本地启动

**第一次（前后端各一次）**

```powershell
# 复制环境变量模板，填自己的高德 Key（.env 不会进仓库）
Copy-Item .env.example .env

# 前端
cd frontend
npm install

# 后端（建议用 Python 3.11 / 3.12 建虚拟环境；3.14 太新，部分包还没有轮子）
cd ..\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**日常启动（两个终端）**

```powershell
# 终端 1：后端
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
# 打开 http://localhost:8000/docs 可以看接口文档

# 终端 2：前端
cd frontend
npm run dev
# 打开 http://localhost:5173
```

**跑测试**

```powershell
cd backend
python -m pytest tests/ -q
# 或者不装 pytest 也能跑：
python tests/test_scoring.py
```

**装依赖很慢或卡住怎么办**

国内直连 PyPI 经常卡在“Collecting”。用清华镜像，实测 17 秒装完：

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

两点说明：

- `requirements.txt` 里**锁了版本**。不锁版本时 pip 会反复回溯解析，可能卡几分钟；锁了之后大家装出来的环境也完全一致。
- 刻意**不用 `uvicorn[standard]`**。加上它会多拉 watchfiles、httptools、websockets 这些要编译的包，Windows 上又慢又容易失败。纯 uvicorn 够开发用，`--reload` 会自动换成轮询实现。

**当前状态**

- 前端可独立运行：默认 `VITE_MOCK=true`，用 `src/mock/route.json` 的假数据，不依赖后端
- 后端 `/api/tips` 已真接高德（需要 `.env` 里配 `AMAP_WEB_KEYS`）
- 后端 `/api/route/generate` 目前返回合成数据，召回逻辑待实现（见 `app/services/mock_data.py` 顶部注释）
- 打分与约束求解已实现并有单测：`backend/app/algo/scoring.py`

## 六人分工

| 角色 | 负责人 | 主要产出 |
|---|---|---|
| 产品经理兼测试 | 王乐 | PRD、验收标准、测试用例、进度协调 |
| 前端 | 赵中奕、罗俊杰 | 参数输入页、方案对比页、详情页、地图与定位 |
| 后端 | 韩牧宸、孙浩哲 | 召回与打分、分段路径规划、接口与缓存 |
| 数据与文档 | 陈志洲 | 种子 POI 库、标签—分类码映射表 |

## 协作三条

1. **一个仓库，一个主分支。** 都在 `main` 上干，动手前先 `git pull`，推之前再 `git pull`。超过半天的大改才开分支。
2. **接口字段以 `docs/api.md` 为准。** 想改字段名或类型，先在群里说，改完同步更新这张表。
3. **动手前说一句。** 要改别人可能也在改的文件（尤其是地图、接口层），群里发一句「我改 xxx」，改完说「推了」。

完整协作步骤见 [docs/setup.md](docs/setup.md)。
