import type { Route, Stop, District, Intensity, Theme, TimeOfDay } from "@/data/routes";

export interface RouteRequest {
  start?: string;
  end?: string;
  theme?: Theme | "";
  duration?: string; // "2-3小时" | "半日" | "全天"
  intensity?: Intensity | "";
  freePrompt?: string;
}

interface AiStopRaw {
  name: string;
  stay?: string;
  desc?: string;
  kind?: Stop["kind"];
}

interface AiRouteRaw {
  name?: string;
  subtitle?: string;
  district?: District | string;
  themes?: Theme[] | Theme | string;
  duration?: number | string;
  distance?: number | string;
  intensity?: Intensity | string;
  bestTime?: TimeOfDay[] | TimeOfDay | string;
  start?: string;
  story?: string;
  highlights?: string[] | string;
  tips?: string[] | string;
  color?: string;
  cover?: string;
  stops?: AiStopRaw[];
}

const STOP_KINDS: Stop["kind"][] = [
  "文保",
  "街巷",
  "过早",
  "观景",
  "咖啡",
  "公园",
  "码头",
  "校园",
];

const COLOR_POOL = ["#14524c", "#b95f36", "#2f5d7a", "#6b4a7a", "#3f6b4f", "#7a4a3a", "#324a6b"];

function extractJson(text: string): string {
  const trimmed = text.trim();
  // Case 1: wrapped in ```json ... ``` or ``` ... ```
  const codeMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (codeMatch) return codeMatch[1].trim();
  // Case 2: direct JSON — find first '{' to last '}'
  const firstBrace = trimmed.indexOf("{");
  const lastBrace = trimmed.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    return trimmed.slice(firstBrace, lastBrace + 1);
  }
  return trimmed;
}

function toArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x));
  if (typeof v === "string") {
    // comma / 、 separated
    return v
      .split(/[,，、]/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

function pickIntensity(v: unknown): Intensity {
  if (typeof v === "string") {
    if (v.includes("轻松") || v.includes("relax")) return "轻松";
    if (v.includes("深度") || v.includes("deep")) return "深度";
    if (v.includes("适中") || v.includes("moderate")) return "适中";
  }
  return "适中";
}

function pickDistrict(v: unknown): District {
  const list: District[] = ["武昌", "汉口", "汉阳", "东湖", "青山"];
  if (typeof v === "string") {
    for (const d of list) if (v.includes(d)) return d;
  }
  return "武昌";
}

function pickThemes(v: unknown): Theme[] {
  const all: Theme[] = [
    "历史人文",
    "江畔风光",
    "市井烟火",
    "建筑美学",
    "湖光山色",
    "艺术街区",
  ];
  const arr = toArray(v);
  const out: Theme[] = [];
  for (const item of arr) {
    const hit = all.find((t) => item.includes(t) || t.includes(item));
    if (hit && !out.includes(hit)) out.push(hit);
  }
  if (out.length === 0) out.push("历史人文");
  return out;
}

function pickBestTime(v: unknown): TimeOfDay[] {
  const all: TimeOfDay[] = ["上午", "午后", "黄昏", "夜晚"];
  const arr = toArray(v);
  const out: TimeOfDay[] = [];
  for (const item of arr) {
    const hit = all.find((t) => item.includes(t));
    if (hit && !out.includes(hit)) out.push(hit);
  }
  if (out.length === 0) out.push("午后");
  return out;
}

function pickKind(v: unknown): Stop["kind"] {
  if (typeof v === "string") {
    for (const k of STOP_KINDS) if (v.includes(k)) return k;
  }
  return "街巷";
}

function toNumber(v: unknown, fallback: number): number {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string") {
    const n = parseFloat(v);
    if (!Number.isNaN(n)) return n;
  }
  return fallback;
}

export class AiRouteError extends Error {
  code: "MISSING_KEY" | "PROXY_ERROR" | "PARSE_ERROR" | "EMPTY" | "NETWORK";
  constructor(code: AiRouteError["code"], message: string) {
    super(message);
    this.code = code;
  }
}

export async function generateRoutes(req: RouteRequest): Promise<Route[]> {
  const systemPrompt = `你是一个武汉 City Walk 路线规划专家。根据用户需求，在武汉三镇范围内规划 3 条互不相同的步行路线。
要求：
1. 三条路线必须有明显差异：不同的片区、不同的主题侧重、不同的节奏，不能只是顺序不同。
2. 只走武汉真实存在、适合步行的点位，避免必须打车的长距离移动。
3. 每条路线站点数量 4~7 个，相邻站点步行时间 10~30 分钟。
4. 所有输出用中文。
5. 必须严格返回单个 JSON 对象，不要 markdown 代码块，不要任何解释文字。

JSON 结构：
{
  "routes": [
    {
      "name": "路线名（8字以内）",
      "subtitle": "几个关键站点用 / 分隔",
      "district": "武昌|汉口|汉阳|东湖|青山",
      "themes": ["历史人文", ...],
      "duration": 3.5,
      "distance": 4.2,
      "intensity": "轻松|适中|深度",
      "bestTime": ["上午", "午后", "黄昏", "夜晚"],
      "story": "一段介绍这条路线的 80~120 字叙事。",
      "highlights": ["亮点1", "亮点2", "亮点3", "亮点4"],
      "tips": ["贴士1", "贴士2", "贴士3"],
      "color": "#14524c",
      "cover": "给图像模型的英文 prompt，描述路线封面场景",
      "stops": [
        {
          "name": "景点或街区的真实名称",
          "stay": "40分钟",
          "desc": "一句话描述",
          "kind": "文保|街巷|过早|观景|咖啡|公园|码头|校园"
        }
      ]
    }
  ]
}
routes 数组必须正好包含 3 个元素。`;

  const userParts: string[] = [];
  if (req.start) userParts.push(`起点：${req.start}`);
  if (req.end) userParts.push(`终点：${req.end}`);
  if (req.theme) userParts.push(`主题偏好：${req.theme}`);
  if (req.duration) userParts.push(`时长：${req.duration}`);
  if (req.intensity) userParts.push(`强度：${req.intensity}`);
  if (req.freePrompt) userParts.push(`其他需求：${req.freePrompt}`);
  if (userParts.length === 0) userParts.push("请为我推荐一条武汉 City Walk 路线。");

  const body = {
    model: "deepseek-chat",
    temperature: 0.85,
    response_format: { type: "json_object" },
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userParts.join("；") },
    ],
  };

  let res: Response;
  try {
    res = await fetch("/api/deepseek/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new AiRouteError("NETWORK", `网络错误：${(e as Error).message}`);
  }

  if (res.status === 502) {
    const json = await res.json().catch(() => ({}));
    throw new AiRouteError(
      "MISSING_KEY",
      json.message || "DeepSeek API Key 未配置"
    );
  }
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new AiRouteError("PROXY_ERROR", `API 返回 ${res.status}：${txt}`);
  }

  let data: { choices?: [{ message?: { content?: string } }] };
  try {
    data = await res.json();
  } catch {
    throw new AiRouteError("PARSE_ERROR", "DeepSeek 返回非 JSON");
  }

  const content = data?.choices?.[0]?.message?.content;
  if (!content) {
    throw new AiRouteError("EMPTY", "DeepSeek 没有返回内容");
  }

  let parsed: { routes?: AiRouteRaw[] } & AiRouteRaw;
  try {
    parsed = JSON.parse(extractJson(content));
  } catch (e) {
    throw new AiRouteError(
      "PARSE_ERROR",
      `解析失败：${(e as Error).message}。模型原始输出：${content.slice(0, 200)}`
    );
  }

  // 兼容模型只返回单条路线的情况
  const list = Array.isArray(parsed.routes) && parsed.routes.length > 0
    ? parsed.routes
    : parsed.stops
      ? [parsed]
      : [];

  if (list.length === 0) {
    throw new AiRouteError("EMPTY", "模型没有返回任何路线");
  }

  return list.slice(0, 3).map((raw, index) => normalizeRoute(raw, index));
}

function normalizeRoute(raw: AiRouteRaw, index = 0): Route {
  if (!Array.isArray(raw.stops) || raw.stops.length === 0) {
    throw new AiRouteError("EMPTY", "模型没有返回任何站点");
  }

  const stops: Stop[] = raw.stops.map((s) => ({
    name: String(s.name || "").trim(),
    stay: String(s.stay || "30分钟"),
    desc: String(s.desc || "").trim() || "AI 推荐站点",
    kind: pickKind(s.kind),
    lng: 0,
    lat: 0,
  })).filter((s) => s.name.length > 0);

  if (stops.length < 2) {
    throw new AiRouteError("EMPTY", "站点数量不足，至少需要 2 个");
  }

  const color = typeof raw.color === "string" && /^#[0-9a-fA-F]{6}$/.test(raw.color)
    ? raw.color
    : COLOR_POOL[index % COLOR_POOL.length];

  return {
    id: `ai-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    name: String(raw.name || "AI 推荐路线").trim(),
    subtitle: String(raw.subtitle || stops.map((s) => s.name).join(" / ")).trim(),
    district: pickDistrict(raw.district),
    themes: pickThemes(raw.themes),
    duration: toNumber(raw.duration, 3.5),
    distance: toNumber(raw.distance, 4),
    intensity: pickIntensity(raw.intensity),
    bestTime: pickBestTime(raw.bestTime),
    start: String(raw.start || stops[0].name),
    story: String(raw.story || "AI 为你量身推荐的这条路线，希望能让你在武汉走得舒服。").trim(),
    highlights: toArray(raw.highlights).slice(0, 4),
    tips: toArray(raw.tips).slice(0, 3),
    color,
    cover: typeof raw.cover === "string" && raw.cover.trim()
      ? raw.cover
      : `Wuhan ${raw.name || "city walk"}, street photography, warm afternoon light`,
    stops,
  };
}
