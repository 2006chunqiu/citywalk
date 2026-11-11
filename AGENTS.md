# AGENTS.md

> 给所有 AI 助手的项目说明书。开工前先读这份文件，再读 `docs/api.md`。

## 项目

武汉 City Walk 路线推荐 Web 应用。前端 Vue 3 + Vite，后端 FastAPI，数据 PostgreSQL。

## 目录约定

- `frontend/` 前端，页面在 `src/pages/`，地图相关在 `src/map/`
- `backend/` 后端，接口在 `app/routers/`，业务在 `app/services/`，算法在 `app/algo/`
- `data/` 种子库与映射表，CSV 格式
- `docs/api.md` 是接口字段的唯一准绳

## 硬性约定

1. 坐标统一 `lng` / `lat`（数字类型，GCJ-02，最多 6 位小数），不要用 `lon`。
2. 距离统一 `distanceM`（米，整数），时长统一 `durationS`（秒，整数）。不要自创 `distance`、`km`、`meters`。
3. 空值用 `null`，不要用空字符串或「暂无」。
4. 接口字段名一律 camelCase。
5. 不新增依赖前先问人；不改 `docs/api.md` 里的字段名和类型。
6. `.env` 不进仓库，本地用 `.env.example` 复制一份改。
7. 高德 Key 从环境变量读，不要写死在代码里，也不要把真实 Key 贴进对话。

## 提交信息

`feat: 说明` / `fix: 说明` / `docs: 说明`
