# 接口表（唯一准绳）

> 改字段名或类型之前，先在群里说，改完同步更新这张表。
> 前端**不要手写接口类型**，按此表抄或生成。

## 通用约定

| 项 | 规则 |
|---|---|
| 坐标 | `lng` / `lat`，**数字**类型，GCJ-02，最多 6 位小数 |
| 距离 | `distanceM`，**整数**，单位米 |
| 时长 | `durationS` / `walkS` / `stayS`，**整数**，单位秒 |
| 空值 | `null`，禁止空字符串、禁止「暂无」 |
| 命名 | camelCase |
| 错误 | 统一 `{ "error": { "code": "...", "message": "..." } }` |

## 一、接口清单

| # | 方法 | 路径 | 用途 |
|---|---|---|---|
| 1 | GET | `/api/tips` | 地址输入提示（代理高德） |
| 2 | GET | `/api/geo/regeo` | 坐标转地址 |
| 3 | GET | `/api/tags` | 兴趣标签与分类码映射 |
| 4 | POST | `/api/route/generate` | 生成三条路线方案 |
| 5 | GET | `/api/route/{schemeId}` | 取指定方案详情 |
| 6 | POST | `/api/route/replan` | 以当前位置重新规划 |
| 7 | POST | `/api/share` | 生成分享链接 |
| 8 | GET | `/api/share/{token}` | 读取分享快照（只读） |
| 9 | GET | `/api/health` | 健康检查与降级状态 |

## 二、1　GET /api/tips

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| keywords | string | 是 | 至少 2 个字符 |
| city | string | 否 | 默认 `武汉` |

返回 `{ "tips": [ Tip ] }`

| 字段 | 类型 | 说明 |
|---|---|---|
| name | string | 名称 |
| address | string | 地址 |
| lng | number | 经度 |
| lat | number | 纬度 |
| adcode | string | 行政区编码 |

## 三、2　GET /api/geo/regeo

参数 `lng`、`lat`（number，必填）。返回 `{ "address": string, "name": string|null, "adname": string }`

## 四、3　GET /api/tags

返回 `{ "tags": [ { "tagId": "art", "name": "文艺", "desc": "书店、画廊、独立咖啡馆", "typecodes": ["140400","140300","050500"], "keywords": ["书店","画廊"] } ] }`

## 五、4　POST /api/route/generate

请求：

```json
{
  "origin":      { "lng": 114.360, "lat": 30.539 },
  "destination": { "lng": 114.316, "lat": 30.550 },
  "tagIds": ["art", "history"],
  "tagOrder": ["art", "history"],
  "effort": "normal"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| origin / destination | object | 是 | 含 `lng`、`lat` |
| tagIds | string[] | 是 | 1～4 个 |
| tagOrder | string[] | 否 | 优先级从高到低，缺省同 tagIds |
| effort | string | 否 | `easy` / `normal` / `deep`，默认 `normal` |

响应：

```json
{
  "status": "success",
  "validation": { "passed": true, "dropped": 0, "reasons": [] },
  "schemes": [ Scheme, Scheme, Scheme ],
  "apiCalls": 28
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| status | string | `success` / `degraded` / `fail` |
| validation.passed | boolean | 校验是否通过 |
| validation.dropped | integer | 被丢弃的候选数 |
| validation.reasons | string[] | 丢弃原因 |
| schemes | Scheme[] | 三条方案，顺序固定：shortest、max、balanced |
| apiCalls | integer | 本次生成的外部调用次数（便于验收核对预算） |

### Scheme 结构

```json
{
  "schemeId": "s_8f2a",
  "mode": "balanced",
  "distanceM": 6900,
  "durationS": 8160,
  "walkS": 5160,
  "stayS": 3000,
  "waypointCount": 5,
  "detourRatio": 1.33,
  "difficulty": "standard",
  "reason": "比最短路线多走 1.3 公里，但多了 2 个历史建筑点位。",
  "polyline": [[114.361, 30.539], [114.358, 30.541]],
  "waypoints": [ Waypoint ],
  "crossing": { "isCrossing": false, "type": null, "distanceM": 0, "extraMinutes": 0 }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| mode | string | `shortest` / `max` / `balanced` |
| difficulty | string | `easy` / `standard` / `deep` |
| polyline | number[][] | `[[lng, lat], ...]`，**不是字符串** |
| crossing.type | string\|null | `bridge` / `ferry` / `metro` / null |

### Waypoint 结构

```json
{
  "seq": 1,
  "poiId": "p_1024",
  "amapId": "B00190...",
  "name": "视觉书屋",
  "address": "武昌区珞珈山街",
  "lng": 114.352,
  "lat": 30.541,
  "typeName": "书店",
  "tagIds": ["art"],
  "stayMinutes": 15,
  "rating": null,
  "source": "seed",
  "distanceFromPrevM": 320
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| rating | number\|null | 缺失用 `null`，前端显示「—」 |
| source | string | `amap` / `seed` / `keyword` / `hot` |

## 六、5　GET /api/route/{schemeId}

返回单个 `Scheme`，外加 `shareUrl`（可能为 null）。

## 七、6　POST /api/route/replan

请求 = generate 的请求体，另加：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| origin | object | 是 | 传当前位置 |
| excludeIds | string[] | 否 | 已到达的 poiId，不得再出现在结果中 |

响应同 generate。

## 八、7　POST /api/share

请求 `{ "schemeId": "s_8f2a" }`

返回 `{ "token": "8fK2mQ...", "url": "https://.../s/8fK2mQ...", "expireAt": "2026-12-21T00:00:00Z" }`

## 九、8　GET /api/share/{token}

返回与 `/api/route/{schemeId}` 相同结构。token 无效或过期返回 `404` + `{ "error": { "code": "SHARE_EXPIRED" } }`。

## 十、9　GET /api/health

返回 `{ "ok": true, "llm": "up", "amap": "up", "keyPool": { "total": 6, "alive": 6 } }`

## 十一、错误码

| code | 含义 | HTTP |
|---|---|---|
| INVALID_DISTANCE | 起终点过近或过远 | 400 |
| SAME_POINT | 起终点相同 | 400 |
| NO_CANDIDATE | 该区域无可推荐点位 | 200，status=fail |
| ALL_KEYS_EXHAUSTED | Key 池全部不可用 | 200，status=degraded |
| SHARE_EXPIRED | 分享链接失效 | 404 |
| INTERNAL | 服务内部错误 | 500 |
