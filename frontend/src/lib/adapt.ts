/** 把后端的 scheme 映射成页面现有的 Route 结构。只做字段搬运与展示层改写，不改任何坐标/距离。 */
import type { District, Intensity, Route, Stop, TimeOfDay } from "@/data/routes";
import type { Scheme, TagId, Waypoint } from "@/lib/api";

export const TAG_NAMES: Record<TagId, string> = {
  art: "文艺",
  park: "公园绿地",
  history: "历史建筑",
  food: "美食小吃",
  river: "江景滨江",
  local: "市井烟火",
  photo: "拍照出片",
  family: "亲子友好",
};

export const THEME_TAGS: Record<string, TagId[]> = {
  历史人文: ["history"],
  江畔风光: ["river", "local"],
  市井烟火: ["local", "food"],
  建筑美学: ["history", "art"],
  湖光山色: ["park"],
  艺术街区: ["art", "photo"],
};

const MODE_META: Record<
  Scheme["mode"],
  { name: string; color: string; subtitle: string }
> = {
  shortest: {
    name: "最短路线",
    color: "#2f6f5f",
    subtitle: "同样的兴趣点，走最少的路",
  },
  max: {
    name: "兴趣最全",
    color: "#a9603c",
    subtitle: "多绕一点，把想看的都串上",
  },
  balanced: {
    name: "均衡推荐",
    color: "#4a6b86",
    subtitle: "距离和内容各让一步",
  },
};

const KINDS: Array<[string, string]> = [
  ["咖啡", "咖啡"],
  ["书店", "书店"],
  ["公园", "公园"],
  ["大学", "校园"],
  ["学校", "校园"],
  ["码头", "码头"],
  ["市场", "菜场"],
  ["餐", "餐馆"],
  ["小吃", "小吃"],
  ["旧址", "文保"],
  ["故居", "文保"],
  ["纪念馆", "文保"],
  ["博物", "文保"],
  ["寺", "文保"],
  ["街", "街巷"],
  ["巷", "街巷"],
  ["里份", "街巷"],
];

const TIPS = [
  "老里份多是窄巷和石板路，穿一双好走的鞋。",
  "沿江路段风大，傍晚记得加件外套。",
  "过早摊子大多上午 10 点前收摊，想吃要趁早。",
  "部分旧址周一闭馆，进馆前先确认开放时间。",
  "拍照时避让居民出入口，别打扰住户生活。",
];

function kindOf(w: Waypoint): string {
  const text = `${w.name}${w.typeName ?? ""}`;
  for (const [key, label] of KINDS) {
    if (text.includes(key)) return label;
  }
  return "途经点";
}

function districtOf(lng: number, lat: number): District {
  if (lat > 30.6 && lng < 114.3) return "汉口";
  if (lng < 114.27 && lat < 30.56) return "汉阳";
  if (lng > 114.4 && lat < 30.6) return "东湖";
  if (lng > 114.37 && lat > 30.6) return "青山";
  return "武昌";
}

function bestTimeOf(tags: TagId[]): TimeOfDay[] {
  if (tags.includes("river")) return ["黄昏", "夜晚"];
  if (tags.includes("park")) return ["上午", "午后"];
  return ["午后", "黄昏"];
}

function intensityOf(scheme: Scheme): Intensity {
  if (scheme.difficulty === "easy" || scheme.difficulty === "relaxed") return "轻松";
  if (scheme.difficulty === "deep" || scheme.difficulty === "intense") return "深度";
  return "适中";
}

export interface AdaptContext {
  originName: string;
  tagIds: TagId[];
}

export function schemeToRoute(scheme: Scheme, ctx: AdaptContext): Route {
  const meta = MODE_META[scheme.mode] ?? MODE_META.balanced;
  const last = scheme.waypoints[scheme.waypoints.length - 1];

  const stops: Stop[] = scheme.waypoints.map((w) => ({
    name: w.name,
    lng: w.lng,
    lat: w.lat,
    stay: `${w.stayMinutes ?? 20} 分钟`,
    desc: [w.typeName, w.address].filter(Boolean).join(" · ") || "途经点",
    kind: kindOf(w),
  }));

  const rated = scheme.waypoints
    .filter((w) => typeof w.rating === "number")
    .sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
  const highlights = (rated.length ? rated : scheme.waypoints)
    .slice(0, 4)
    .map((w) =>
      typeof w.rating === "number" ? `${w.name} · 评分 ${w.rating}` : w.name,
    );

  return {
    id: scheme.schemeId,
    name: meta.name,
    subtitle: meta.subtitle,
    district: districtOf(last?.lng ?? 114.3, last?.lat ?? 30.59),
    themes: ctx.tagIds.map((t) => TAG_NAMES[t]),
    duration: Math.max(0.5, Math.round((scheme.durationS / 3600) * 10) / 10),
    distance: Math.round((scheme.distanceM / 1000) * 10) / 10,
    intensity: intensityOf(scheme),
    bestTime: bestTimeOf(ctx.tagIds),
    start: ctx.originName,
    story: scheme.reason,
    highlights,
    tips: [TIPS[0], TIPS[2], TIPS[3]],
    cover: "",
    color: meta.color,
    stops,
  };
}

export function schemeToPath(scheme: Scheme): Array<[number, number]> | null {
  if (scheme.polylineSource !== "amap" || scheme.polyline?.length < 2) return null;
  return scheme.polyline;
}
