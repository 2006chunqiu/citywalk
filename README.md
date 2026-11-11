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

## 本地启动（待补：各自开发到能跑通时填这里）

```
# 前端
cd frontend && npm install && npm run dev

# 后端
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

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
