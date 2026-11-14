/** 后端接口层：所有请求都打到 FastAPI（开发环境由 Vite 代理到 127.0.0.1:8000）。 */

export type TagId =
  | "art"
  | "park"
  | "history"
  | "food"
  | "river"
  | "local"
  | "photo"
  | "family";

export type Effort = "easy" | "normal" | "deep";

export interface LngLat {
  lng: number;
  lat: number;
}

export interface Waypoint {
  seq: number;
  poiId: string;
  amapId?: string;
  name: string;
  address?: string;
  lng: number;
  lat: number;
  typeName?: string;
  tagIds?: TagId[];
  stayMinutes?: number;
  rating?: number | null;
  source?: string;
  distanceFromPrevM?: number;
}

export interface Scheme {
  schemeId: string;
  mode: "shortest" | "max" | "balanced";
  title?: string;
  distanceM: number;
  durationS: number;
  walkS: number;
  stayS: number;
  waypointCount: number;
  detourRatio: number;
  difficulty: string;
  reason: string;
  polyline: Array<[number, number]>;
  polylineSource: "amap" | "straight";
  waypoints: Waypoint[];
  crossing?: boolean;
}

export interface RoutingInfo {
  calls: number;
  cacheHits: number;
  straightLegs: number;
  failedLegs: number;
  budgetExhausted: boolean;
  provider: string;
}

export interface GenerateResult {
  status?: string;
  schemes: Scheme[];
  routing?: RoutingInfo;
  validation?: { passed: boolean; dropped: number; reasons: string[] };
  apiCalls?: number;
}

export interface GeocodeResult {
  name: string;
  lng: number;
  lat: number;
  level?: string;
  adcode?: string;
}

export interface IntentResult {
  tagIds: TagId[];
  source?: "rule" | "llm";
}

export interface ShareResult {
  token: string;
  url: string;
  text: string;
  expireAt?: string | null;
}

export class BackendError extends Error {
  code: string;
  hint?: string;

  constructor(code: string, message: string, hint?: string) {
    super(message);
    this.name = "BackendError";
    this.code = code;
    this.hint = hint;
  }
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new BackendError(
      "NETWORK",
      "连不上后端服务（127.0.0.1:8000）。",
      "先在 backend 目录启动 uvicorn，再刷新页面。",
    );
  }

  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // 非 JSON 响应，下面按状态码处理
  }

  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new BackendError(
      err?.code || `HTTP_${res.status}`,
      err?.message || `后端返回 ${res.status}`,
    );
  }
  return body as T;
}

export function geocodeAddress(address: string) {
  return request<GeocodeResult>(
    `/api/geo/geocode?address=${encodeURIComponent(address)}&city=${encodeURIComponent("武汉")}`,
  );
}

export function postIntent(query: string) {
  return request<IntentResult>("/api/intent", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function postGenerate(body: {
  origin: LngLat;
  destination: LngLat;
  tagIds: TagId[];
  effort: Effort;
}) {
  return request<GenerateResult>("/api/route/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postReplan(body: {
  origin: LngLat;
  destination: LngLat;
  tagIds: TagId[];
  effort: Effort;
  excludeIds: string[];
}) {
  return request<GenerateResult>("/api/route/replan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postShare(schemeId: string) {
  return request<ShareResult>("/api/share", {
    method: "POST",
    body: JSON.stringify({ schemeId }),
  });
}
