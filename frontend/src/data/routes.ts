export type Theme =
  | "历史人文"
  | "江畔风光"
  | "市井烟火"
  | "建筑美学"
  | "湖光山色"
  | "艺术街区";

export type Intensity = "轻松" | "适中" | "深度";

export type TimeOfDay = "上午" | "午后" | "黄昏" | "夜晚";

export type District = "武昌" | "汉口" | "汉阳" | "东湖" | "青山";

export interface Stop {
  name: string;
  lng: number;
  lat: number;
  stay: string;
  desc: string;
  kind: string;
}

export interface Route {
  id: string;
  name: string;
  subtitle: string;
  district: District;
  themes: string[];
  duration: number;
  distance: number;
  intensity: Intensity;
  bestTime: TimeOfDay[];
  start: string;
  story: string;
  highlights: string[];
  tips: string[];
  cover: string;
  color: string;
  stops: Stop[];
}

export const THEMES: Theme[] = [
  "历史人文",
  "江畔风光",
  "市井烟火",
  "建筑美学",
  "湖光山色",
  "艺术街区",
];

export const INTENSITIES: Intensity[] = ["轻松", "适中", "深度"];

export const TIMES: TimeOfDay[] = ["上午", "午后", "黄昏", "夜晚"];

export const DURATION_OPTIONS = [
  { value: "all", label: "不限" },
  { value: "short", label: "2–3 小时" },
  { value: "half", label: "半日" },
  { value: "full", label: "全天" },
] as const;

export type DurationKey = (typeof DURATION_OPTIONS)[number]["value"];

export const DURATION_TARGET: Record<DurationKey, number> = {
  all: 0,
  short: 2.5,
  half: 4,
  full: 7,
};

export const ROUTES: Route[] = [];

export const TOTAL_STOPS = 0;


// 演示阶段不再依赖第三方文生图接口：封面用渐变，站点缩略图用类型文字兜底。
export const coverUrl = (_prompt: string) => "";

export const stopImageUrl = (_stop: Stop) => "";

export const amapMarkerUrl = (stop: Stop) =>
  `https://uri.amap.com/marker?position=${stop.lng},${stop.lat}&name=${encodeURIComponent(
    stop.name
  )}&src=wuhan-citywalk&coordinate=gaode&callnative=0`;
