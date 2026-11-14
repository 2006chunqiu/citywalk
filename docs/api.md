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
| 10 | POST | `/api/intent` | 一句话需求转兴趣标签 |
| 11 | GET | `/api/geo/geocode` | 文字地址转坐标 |

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
  "apiCalls": 7,
  "routing": {
    "provider": "amap",
    "calls": 7,
    "cacheHits": 5,
    "straightLegs": 0,
    "failedLegs": 0,
    "budgetExhausted": false
  }
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
| routing.provider | string | 折线来源服务商，目前固定 `amap` |
| routing.calls | integer | 实际调用高德步行规划的段数 |
| routing.cacheHits | integer | 命中进程内折线缓存的段数（不消耗配额） |
| routing.straightLegs | integer | 因距离过短而直接连直线的段数 |
| routing.failedLegs | integer | 调用失败、降级为直线的段数（正常应为 0） |
| routing.budgetExhausted | boolean | 是否因调用预算耗尽而提前停止 |

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
  "polylineSource": "amap",
  "waypoints": [ Waypoint ],
  "crossing": { "isCrossing": false, "type": null, "distanceM": 0, "extraMinutes": 0 }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| mode | string | `shortest` / `max` / `balanced` |
| difficulty | string | `easy` / `standard` / `deep` |
| polyline | number[][] | `[[lng, lat], ...]`，**不是字符串**；真实步行路径通常 200～340 个点 |
| polylineSource | string | `amap`＝全部段为高德真实路径；`mixed`＝部分段降级为直线；`estimated`＝全部为直线估算 |
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

返回 `{ "ok": true, "llm": "off", "amap": "up", "keyPool": { "total": 1, "alive": 1, "calls": 16 }, "budget": { "apiCallBudget": 45 }, "poi": { "total": 244, "withRating": 191, "byTag": { "art": 70 } } }`

| 字段 | 类型 | 说明 |
|---|---|---|
| llm | string | `off` 表示未配置大模型文案，走模板兜底 |
| amap | string | `up` 表示高德 Key 可用；`down` 表示不可用 |
| keyPool.alive | integer | 当前可用 Key 数 |
| budget.apiCallBudget | integer | 单次生成允许的高德调用上限 |
| poi.total | integer | 种子库点位总数 |
| poi.withRating | integer | 带评分的点位数 |
| poi.byTag | object | 各标签点位数量（`tagId → count`） |

## 附：本地演示页

后端启动后打开 `http://127.0.0.1:8000/demo` 即可使用；页面与接口同源，不需要额外服务、不需要高德 JS Key。

## 十一、10　POST /api/intent

请求：

```json
{ "query": "想走点安静的老街拍拍照" }
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| query | string | 是 | 1～100 字 |

返回：

```json
{ "tagIds": ["art", "history", "local", "photo"], "source": "rule" }
```

| 字段 | 类型 | 说明 |
|---|---|---|
| tagIds | string[] | 最多 4 个，取值见 `/api/tags`；无法识别时返回空数组 |
| source | string | `rule`＝词表命中；`llm`＝词表命中不足 2 个、且配置了 `LLM_API_KEY`，由模型补 |

说明：词表优先，不调用大模型；仅在词表命中少于 2 个且启用 LLM 时才问模型。未配置 Key 时恒为 `rule`。

## 十二、11　GET /api/geo/geocode

文字地址 → 坐标。前端把「武汉大学」「昙华林」这类输入换成 `lng/lat` 用这个。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| address | string | 是 | 至少 2 个字符；支持常见简称（武大 / 华科 / 华师 / 华农 / 地大 / 理工 / 财大） |
| city | string | 否 | 默认 `武汉` |

返回：

```json
{
  "name": "湖北省武汉市武昌区武汉大学(澄波门)",
  "lng": 114.357777,
  "lat": 30.543913,
  "level": "兴趣点",
  "adcode": "420106"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| name | string | 高德返回的标准地址 |
| lng / lat | number | GCJ-02 |
| level | string | 高德地点级别（兴趣点 / 道路 / 村庄…） |
| adcode | string | 行政区编码 |

错误：`400 INVALID_ADDRESS`（少于 2 字）、`404 GEOCODE_NOT_FOUND`（没有匹配，含乱写地址）、`502`（高德其他错误）、`503 ALL_KEYS_EXHAUSTED`。

说明：高德对无意义字符串会模糊返回一个地点（如「火星基地xyz」→ 黄陂某村），后端做了字符重合校验，对不上就按没找到处理，避免把起点定到几十公里外。

## 十三、错误码

| code | 含义 | HTTP |
|---|---|---|
| INVALID_DISTANCE | 起终点过近或过远 | 400 |
| SAME_POINT | 起终点相同 | 400 |
| INVALID_ADDRESS | 地址少于 2 个字符 | 400 |
| GEOCODE_NOT_FOUND | 地址没有匹配结果 | 404 |
| INVALID_REQUEST | 请求参数校验失败（统一错误结构） | 422 |
| NO_CANDIDATE | 该区域无可推荐点位 | 200，status=fail |
| ALL_KEYS_EXHAUSTED | Key 池全部不可用 | 200，status=degraded |
| SHARE_EXPIRED | 分享链接失效 | 404 |
| INTERNAL | 服务内部错误 | 500 |
