import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Loader2,
  MapPinned,
  Route as RouteIcon,
  Sparkles,
  Wand2,
} from "lucide-react";
import { Header } from "@/components/Header";
import { RouteDetail } from "@/components/RouteDetail";
import { MapView } from "@/components/MapView";
import { AboutDialog } from "@/components/Dialogs";
import { THEMES, INTENSITIES, type Route, type Theme, type Intensity } from "@/data/routes";
import {
  BackendError,
  geocodeAddress,
  postGenerate,
  postIntent,
  postReplan,
  type Effort,
  type LngLat,
  type Scheme,
  type TagId,
} from "@/lib/api";
import { THEME_TAGS, schemeToPath, schemeToRoute } from "@/lib/adapt";
import { cn } from "@/lib/utils";

type GenStatus = "idle" | "planning" | "done" | "error";

interface GenError {
  code: string;
  message: string;
  hint?: string;
}

const DEFAULT_START = "武汉大学";
const DEFAULT_END = "昙华林";

function toEffort(duration: string, intensity: Intensity | ""): Effort {
  if (intensity === "轻松") return "easy";
  if (intensity === "深度") return "deep";
  if (duration === "2–3 小时") return "easy";
  if (duration === "全天") return "deep";
  return "normal";
}

interface RefineIntent {
  excludeIds: string[];
  effort?: Effort;
  matched: string[];
  understood: boolean;
}

/** 把「再改一下」这句话翻成筛选条件：只输出 poiId 和 effort，不产生任何地点。 */
function parseRefine(text: string, schemes: Scheme[], selected = 0): RefineIntent {
  const ids = new Set<string>();
  const matched: string[] = [];
  let understood = false;
  const addBy = (label: string, pred: (w: Scheme["waypoints"][number]) => boolean) => {
    understood = true;
    let hit = false;
    for (const s of schemes) {
      for (const w of s.waypoints) {
        if (pred(w)) {
          ids.add(w.poiId);
          hit = true;
        }
      }
    }
    if (hit) matched.push(label);
  };

  if (/咖啡/.test(text)) addBy("去掉咖啡", (w) => `${w.name}${w.typeName ?? ""}`.includes("咖啡"));
  if (/公园|绿地/.test(text)) addBy("去掉公园", (w) => (w.tagIds ?? []).includes("park"));
  if (/历史|老建筑|旧址|故居/.test(text)) addBy("去掉历史建筑", (w) => (w.tagIds ?? []).includes("history"));
  if (/美食|小吃|吃|餐/.test(text)) addBy("去掉美食", (w) => (w.tagIds ?? []).includes("food"));
  if (/文艺|书店|艺术/.test(text)) addBy("去掉文艺", (w) => (w.tagIds ?? []).includes("art"));
  if (/江景|江边|看江|水边/.test(text)) addBy("去掉江景", (w) => (w.tagIds ?? []).includes("river"));
  if (/市场|菜场|菜市场/.test(text))
    addBy("去掉市场", (w) => {
      const t = `${w.name}${w.typeName ?? ""}`;
      return t.includes("市场") || t.includes("菜场");
    });
  if (/拍照|出片/.test(text)) addBy("去掉拍照", (w) => (w.tagIds ?? []).includes("photo"));
  if (/亲子|带娃|孩子/.test(text)) addBy("去掉亲子", (w) => (w.tagIds ?? []).includes("family"));
  if (/换一批|换一组|都换/.test(text)) {
    understood = true;
    // 只换当前这条方案的点，避免把整个走廊的候选池一次掏空
    const current = schemes[selected] ?? schemes[0];
    if (current) for (const w of current.waypoints) ids.add(w.poiId);
    matched.push("换一批");
  }

  let effort: Effort | undefined;
  if (/少走|短一点|别太累|轻松|走太远|不想走远/.test(text)) {
    understood = true;
    effort = "easy";
    matched.push("优先最短");
  } else if (/多逛|深度|多看|长一点/.test(text)) {
    understood = true;
    effort = "deep";
    matched.push("优先兴趣最全");
  }

  return { excludeIds: Array.from(ids), effort, matched, understood };
}

const REFINE_TEMPLATES = [
  { label: "别给咖啡馆", value: "别给我咖啡馆了" },
  { label: "少走点路", value: "少走点路，别太累" },
  { label: "换一批", value: "换一批" },
  { label: "多逛一会", value: "多逛一会，想多看几个点" },
];

const DURATION_OPTIONS = ["2–3 小时", "半日", "全天"] as const;

const PROMPT_TEMPLATES = [
  { label: "情侣慢逛", value: "适合情侣，想安静一点，有咖啡馆和江景。" },
  { label: "拍照出片", value: "要适合拍照，老街巷、光影好、人别太多。" },
  { label: "带娃友好", value: "带五岁小孩，行程轻松，有户外活动。" },
  { label: "美食优先", value: "重点是武汉美食，过早、小吃、夜宵都要。" },
];

export default function App() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [theme, setTheme] = useState<Theme | "">("");
  const [duration, setDuration] = useState<string>("半日");
  const [intensity, setIntensity] = useState<Intensity | "">("适中");
  const [freePrompt, setFreePrompt] = useState("");

  const [routes, setRoutes] = useState<Route[]>([]);
  const [paths, setPaths] = useState<Array<Array<[number, number]> | null>>([]);
  const [selected, setSelected] = useState(0);
  const route = routes[selected] ?? null;
  const pathCoords = paths[selected] ?? null;
  const [status, setStatus] = useState<GenStatus>("idle");
  const [error, setError] = useState<GenError | null>(null);
  const [trip, setTrip] = useState<{ from: string; to: string } | null>(null);
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [lastReq, setLastReq] = useState<{
    origin: LngLat;
    destination: LngLat;
    tagIds: TagId[];
    effort: Effort;
  } | null>(null);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [refineText, setRefineText] = useState("");
  const [refining, setRefining] = useState(false);
  const [refineNote, setRefineNote] = useState<string | null>(null);

  const [activeStop, setActiveStop] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [mobileView, setMobileView] = useState<"input" | "map">("input");

  const [isMobile, setIsMobile] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(max-width: 1023px)").matches
  );

  useEffect(() => {
    const query = window.matchMedia("(max-width: 1023px)");
    const update = () => setIsMobile(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  const handleGenerate = async () => {
    setError(null);
    setRoutes([]);
    setPaths([]);
    setSelected(0);
    setActiveStop(null);
    setDetailOpen(false);
    setSchemes([]);
    setExcluded([]);
    setRefineText("");
    setRefineNote(null);
    setStatus("planning");

    try {
      // 1. 文字地址 → 坐标（后端调高德地理编码）
      const [from, to] = await Promise.all([
        geocodeAddress(start.trim() || DEFAULT_START),
        geocodeAddress(end.trim() || DEFAULT_END),
      ]);

      // 2. 主题 + 一句话需求 → 标签（词表优先，模型兜底）
      let tags: TagId[] = theme ? THEME_TAGS[theme] ?? [] : [];
      if (freePrompt.trim()) {
        const intent = await postIntent(freePrompt.trim());
        tags = Array.from(new Set([...tags, ...intent.tagIds]));
      }
      if (tags.length === 0) tags = ["history", "local"];
      tags = tags.slice(0, 4);

      // 3. 种子库召回 + 打分 + 高德真实步行折线，全在后端完成
      const effort = toEffort(duration, intensity);
      const result = await postGenerate({
        origin: { lng: from.lng, lat: from.lat },
        destination: { lng: to.lng, lat: to.lat },
        tagIds: tags,
        effort,
      });

      if (!result.schemes?.length) {
        throw new BackendError("NO_SCHEME", "后端没有返回可用路线。");
      }

      setTrip({ from: from.name, to: to.name });
      setSchemes(result.schemes);
      setLastReq({
        origin: { lng: from.lng, lat: from.lat },
        destination: { lng: to.lng, lat: to.lat },
        tagIds: tags,
        effort,
      });
      setRoutes(
        result.schemes.map((scheme) =>
          schemeToRoute(scheme, { originName: from.name, tagIds: tags }),
        ),
      );
      setPaths(result.schemes.map((scheme) => schemeToPath(scheme)));
      setSelected(result.schemes.length > 2 ? 2 : 0);
      setStatus("done");
      if (isMobile) setMobileView("map");
    } catch (e) {
      if (e instanceof BackendError) {
        setError({ code: e.code, message: e.message, hint: e.hint });
      } else {
        setError({
          code: "UNKNOWN",
          message: e instanceof Error ? e.message : String(e),
        });
      }
      setStatus("error");
    }
  };

  const handleRefine = async (raw?: string) => {
    const text = (raw ?? refineText).trim();
    if (!text || !lastReq || refining) return;

    const intent = parseRefine(text, schemes, selected);
    if (!intent.understood) {
      setError({
        code: "REFINE_NOT_UNDERSTOOD",
        message: "没太听懂这句。可以试试「别给我咖啡馆了」「少走点路」「换一批」。",
      });
      return;
    }
    if (intent.excludeIds.length === 0 && !intent.effort) {
      setError({
        code: "REFINE_NOOP",
        message: "这条路线里没有你要避开的这类点位，不用改。",
      });
      return;
    }

    setRefining(true);
    setError(null);
    try {
      const merged = Array.from(new Set([...excluded, ...intent.excludeIds]));
      const next = await postReplan({
        ...lastReq,
        effort: intent.effort ?? lastReq.effort,
        excludeIds: merged,
      });
      if (!next.schemes?.length) {
        throw new BackendError("NO_SCHEME", "按这个条件没排出路线，换个说法试试。");
      }

      setSchemes(next.schemes);
      setRoutes(
        next.schemes.map((scheme) =>
          schemeToRoute(scheme, {
            originName: trip?.from ?? "起点",
            tagIds: lastReq.tagIds,
          }),
        ),
      );
      setPaths(next.schemes.map((scheme) => schemeToPath(scheme)));

      // “少走”选最短的一条，“多逛”选站点最多的一条，其余默认均衡
      let target = next.schemes.length > 2 ? 2 : 0;
      if (intent.effort === "easy") {
        target = next.schemes.reduce(
          (best, s, i) => (s.distanceM < next.schemes[best].distanceM ? i : best),
          0,
        );
      } else if (intent.effort === "deep") {
        target = next.schemes.reduce(
          (best, s, i) => (s.waypointCount > next.schemes[best].waypointCount ? i : best),
          0,
        );
      }
      setSelected(target);
      setExcluded(merged);
      setLastReq({ ...lastReq, effort: intent.effort ?? lastReq.effort });
      setRefineText("");
      setRefineNote(
        intent.matched.length
          ? `已按「${intent.matched.join("、")}」重排`
          : "已重新排了一版",
      );
      setStatus("done");
    } catch (e) {
      if (e instanceof BackendError) {
        setError({ code: e.code, message: e.message, hint: e.hint });
      } else {
        setError({
          code: "UNKNOWN",
          message: e instanceof Error ? e.message : String(e),
        });
      }
    } finally {
      setRefining(false);
    }
  };

  const handleSelectRoute = (index: number) => {
    setSelected(index);
    setActiveStop(null);
  };

  const handleSelectStop = (index: number) => {
    setActiveStop(index);
    if (isMobile) {
      setDetailOpen(false);
      setMobileView("map");
    }
  };

  const canGenerate = status !== "planning";

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background">
      <Header onOpenAbout={() => setAboutOpen(true)} />

      <main className="relative flex min-h-0 flex-1">
        {/* 左侧：输入表单 + 生成结果 */}
        <section
          className={cn(
            "flex w-full min-w-0 shrink-0 flex-col border-r border-hairline bg-paper lg:w-[408px] xl:w-[436px]",
            isMobile && mobileView === "map" && "hidden"
          )}
        >
          <div className="panel-scroll flex-1 overflow-y-auto overscroll-contain">
            <div className="px-4 pb-10 pt-5 lg:px-5">
              {/* Hero */}
              <section className="relative overflow-hidden rounded-[26px] border border-white/10 bg-[linear-gradient(135deg,#16564f_0%,#0f3c37_55%,#0a2b27_100%)] p-4 text-[#f4efe2] shadow-[0_32px_64px_-42px_rgba(10,43,39,0.95)]">
                <svg
                  aria-hidden
                  viewBox="0 0 200 200"
                  className="pointer-events-none absolute -right-10 -top-12 size-44 text-white/12"
                >
                  <circle cx="100" cy="100" r="78" fill="none" stroke="currentColor" />
                  <circle cx="100" cy="100" r="56" fill="none" stroke="currentColor" strokeDasharray="3 7" />
                  <circle cx="100" cy="100" r="34" fill="none" stroke="currentColor" />
                  <path d="M10 128 C60 92 128 152 194 104" fill="none" stroke="currentColor" strokeWidth="1.4" />
                </svg>

                <p className="text-[9px] tracking-[0.32em] text-white/50">
                  WUHAN · CITY WALK GUIDE
                </p>
                <h1 className="mt-1.5 font-display text-[23px] leading-[1.4] tracking-wide">
                  告诉 AI 你想怎么走。
                </h1>
                <p className="mt-1.5 max-w-[300px] text-[10.5px] leading-[1.8] text-white/60">
                  输入起点、终点，或说一句「想走点安静的老街」——点位从本地真实地点库里挑，路线按高德步行路径逐段计算。
                </p>
              </section>

              {/* 表单 */}
              <section className="mt-4 rounded-[22px] border border-hairline bg-card p-4 shadow-[var(--shadow-card)]">
                <div className="mb-3 flex items-center gap-2">
                  <Sparkles className="size-3.5 text-clay" strokeWidth={1.9} />
                  <p className="text-[10px] tracking-[0.24em] text-muted-foreground">
                    路线规划
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="起点（可选）">
                      <input
                        type="text"
                        value={start}
                        onChange={(e) => setStart(e.target.value)}
                        placeholder="如：武昌火车站"
                        className="h-9 w-full rounded-lg border border-hairline bg-background px-3 text-[12px] outline-none transition focus:border-river/50 focus:ring-2 focus:ring-river/15"
                      />
                    </Field>
                    <Field label="终点（可选）">
                      <input
                        type="text"
                        value={end}
                        onChange={(e) => setEnd(e.target.value)}
                        placeholder="如：江汉关"
                        className="h-9 w-full rounded-lg border border-hairline bg-background px-3 text-[12px] outline-none transition focus:border-river/50 focus:ring-2 focus:ring-river/15"
                      />
                    </Field>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <Field label="主题">
                      <select
                        value={theme}
                        onChange={(e) => setTheme(e.target.value as Theme | "")}
                        className="h-9 w-full rounded-lg border border-hairline bg-background px-2.5 text-[12px] outline-none transition focus:border-river/50 focus:ring-2 focus:ring-river/15"
                      >
                        <option value="">不限</option>
                        {THEMES.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="强度">
                      <select
                        value={intensity}
                        onChange={(e) => setIntensity(e.target.value as Intensity | "")}
                        className="h-9 w-full rounded-lg border border-hairline bg-background px-2.5 text-[12px] outline-none transition focus:border-river/50 focus:ring-2 focus:ring-river/15"
                      >
                        <option value="">不限</option>
                        {INTENSITIES.map((i) => (
                          <option key={i} value={i}>{i}</option>
                        ))}
                      </select>
                    </Field>
                  </div>

                  <Field label="时长">
                    <div className="flex gap-1.5">
                      {DURATION_OPTIONS.map((d) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setDuration(d)}
                          className={cn(
                            "h-8 flex-1 rounded-lg border text-[11.5px] transition",
                            duration === d
                              ? "border-river bg-river/10 text-river"
                              : "border-hairline text-muted-foreground hover:border-river/40"
                          )}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <Field label="再说点什么（可选）">
                    <textarea
                      value={freePrompt}
                      onChange={(e) => setFreePrompt(e.target.value)}
                      rows={2}
                      placeholder="适合拍照 / 带娃 / 想安静 / 美食优先 …"
                      className="w-full resize-none rounded-lg border border-hairline bg-background px-3 py-2 text-[12px] outline-none transition focus:border-river/50 focus:ring-2 focus:ring-river/15"
                    />
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {PROMPT_TEMPLATES.map((t) => (
                        <button
                          key={t.label}
                          type="button"
                          onClick={() => setFreePrompt(t.value)}
                          className="rounded-full border border-hairline bg-background px-2 py-0.5 text-[10.5px] text-muted-foreground transition hover:border-river/40 hover:text-river"
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={!canGenerate}
                    className={cn(
                      "flex h-11 w-full items-center justify-center gap-2 rounded-xl font-display text-[14px] tracking-wide transition",
                      canGenerate
                        ? "bg-river text-primary-foreground shadow-[0_12px_24px_-12px_rgba(20,82,76,0.55)] hover:opacity-92"
                        : "cursor-not-allowed bg-secondary text-muted-foreground"
                    )}
                  >
                    {status === "planning" ? (
                      <>
                        <Loader2 className="size-4 animate-spin" strokeWidth={1.9} />
                        正在挑选点位 · 计算步行路线…
                      </>
                    ) : (
                      <>
                        <Wand2 className="size-4" strokeWidth={1.9} />
                        生成 City Walk 路线
                      </>
                    )}
                  </button>
                </div>
              </section>

              {/* 错误提示 */}
              {error && (
                <section className="mt-3 rounded-[18px] border border-clay/30 bg-clay/8 px-4 py-3 text-[11.5px] leading-relaxed text-clay">
                  <p className="font-display text-[12px]">这一步没成功</p>
                  <p className="mt-1 opacity-90">{error.message}</p>
                  {error.hint && (
                    <p className="mt-1 text-[10.5px] opacity-70">{error.hint}</p>
                  )}
                </section>
              )}

              {/* 生成结果 */}
              {route && status === "done" && (
                <section className="mt-4">
                  <div className="mb-2 mt-2 flex items-end justify-between">
                    <div>
                      <p className="text-[9px] tracking-[0.26em] text-muted-foreground/70">
                        {trip ? `${trip.from} → ${trip.to}` : "为你规划"} · {routes.length} 条备选
                      </p>
                      <h2 className="mt-1 font-display text-[17px] tracking-wide">
                        {route.name}
                      </h2>
                    </div>
                    <button
                      type="button"
                      onClick={handleGenerate}
                      className="text-[10.5px] text-river underline-offset-2 hover:underline"
                    >
                      重新生成
                    </button>
                  </div>

                  {routes.length > 1 && (
                    <div className="mb-2 flex gap-1.5">
                      {routes.map((r, i) => (
                        <button
                          key={r.id}
                          type="button"
                          onClick={() => handleSelectRoute(i)}
                          className={cn(
                            "flex-1 rounded-xl border px-2 py-1.5 text-left transition",
                            i === selected
                              ? "border-river/50 bg-river/8"
                              : "border-hairline bg-background hover:border-river/25"
                          )}
                        >
                          <span className="flex items-center gap-1">
                            <span
                              className="size-1.5 shrink-0 rounded-full"
                              style={{ backgroundColor: r.color }}
                            />
                            <span
                              className={cn(
                                "truncate text-[10.5px]",
                                i === selected ? "font-medium text-river" : "text-foreground/75"
                              )}
                            >
                              {r.name}
                            </span>
                          </span>
                          <span className="mt-0.5 block truncate text-[9.5px] text-muted-foreground">
                            {r.district} · {r.stops.length}站 · {r.distance}km
                          </span>
                        </button>
                      ))}
                    </div>
                  )}

                  <RouteMiniCard route={route} onOpen={() => setDetailOpen(true)} />

                  {/* 再改一下：一句话 → 筛选条件 / 强度，调 replan */}
                  <div className="mt-3 rounded-[18px] border border-hairline bg-card p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[9px] tracking-[0.24em] text-muted-foreground">
                        再改一下
                      </p>
                      {refineNote && (
                        <p className="truncate text-[9.5px] text-river">{refineNote}</p>
                      )}
                    </div>
                    <div className="mt-2 flex gap-1.5">
                      <input
                        type="text"
                        value={refineText}
                        onChange={(e) => setRefineText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRefine();
                        }}
                        placeholder="如：别给我咖啡馆了 / 少走点路"
                        className="h-8 min-w-0 flex-1 rounded-lg border border-hairline bg-background px-2.5 text-[11.5px] outline-none transition focus:border-river/50 focus:ring-2 focus:ring-river/15"
                      />
                      <button
                        type="button"
                        onClick={() => handleRefine()}
                        disabled={refining || !refineText.trim()}
                        className={cn(
                          "flex h-8 shrink-0 items-center gap-1 rounded-lg px-3 text-[11px] transition",
                          refining || !refineText.trim()
                            ? "cursor-not-allowed bg-secondary text-muted-foreground"
                            : "bg-river text-primary-foreground hover:opacity-92"
                        )}
                      >
                        {refining && (
                          <Loader2 className="size-3.5 animate-spin" strokeWidth={1.9} />
                        )}
                        重排
                      </button>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {REFINE_TEMPLATES.map((t) => (
                        <button
                          key={t.label}
                          type="button"
                          disabled={refining}
                          onClick={() => {
                            setRefineText(t.value);
                            handleRefine(t.value);
                          }}
                          className="rounded-full border border-hairline bg-background px-2 py-0.5 text-[10px] text-muted-foreground transition hover:border-river/40 hover:text-river disabled:opacity-50"
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                    <p className="mt-1.5 text-[9.5px] text-muted-foreground/70">
                      只改筛选条件和强度，不会新增地点。
                    </p>
                  </div>
                </section>
              )}

              {/* 空闲提示 */}
              {status === "idle" && !route && (
                <section className="mt-4 rounded-[18px] border border-dashed border-hairline px-4 py-6 text-center text-[11px] leading-relaxed text-muted-foreground/80">
                  <RouteIcon className="mx-auto mb-2 size-5 text-muted-foreground/60" strokeWidth={1.7} />
                  左边表单里随便填点什么，右边地图就会画出一条能走的路线。
                </section>
              )}

              <p className="mt-6 border-t border-dashed border-hairline pt-4 text-[10px] leading-relaxed text-muted-foreground/75">
                点位来自本地种子库（244 条武汉精选地点），步行路径由高德地图逐段计算。出行前请核实场馆开放时间。
              </p>
            </div>
          </div>
        </section>

        {/* 右侧：地图 */}
        <section
          className={cn(
            "relative min-w-0 flex-1 overflow-hidden bg-secondary/40",
            isMobile && mobileView === "input" && "hidden"
          )}
        >
          <MapView
            route={route}
            path={pathCoords}
            activeStop={activeStop}
            onSelectStop={handleSelectStop}
            onError={() => setMapError(true)}
          />

          {route ? (
            <>
              <div className="pointer-events-none absolute left-4 top-4 z-10 flex items-center gap-2 rounded-full border border-hairline bg-background/85 px-3 py-1.5 text-[10.5px] text-muted-foreground shadow-sm backdrop-blur">
                <span className="size-1.5 rounded-full bg-clay" />
                {route.district} · {route.stops.length} 站 · {route.distance}km · 高德步行路径
              </div>

              {!detailOpen && (
                <button
                  type="button"
                  onClick={() => setDetailOpen(true)}
                  className="group absolute bottom-8 left-4 right-20 z-20 max-w-[340px] rounded-[20px] border border-hairline bg-background/92 p-3 text-left shadow-[var(--shadow-float)] backdrop-blur-xl transition hover:-translate-y-0.5 lg:bottom-6 lg:right-auto lg:w-[330px] lg:p-4"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-[9.5px] tracking-[0.2em] text-muted-foreground">
                      当前路线
                    </span>
                    <ArrowUpRight
                      className="ml-auto size-3.5 text-muted-foreground transition group-hover:text-river"
                      strokeWidth={1.8}
                    />
                  </div>
                  <h3 className="mt-1 truncate font-display text-[16px]">
                    {route.name}
                  </h3>
                  <p className="mt-0.5 truncate text-[10.5px] text-muted-foreground">
                    {route.duration} 小时 · {route.distance} km · {route.intensity}
                  </p>
                  <div className="mt-2 flex items-center gap-1 text-[10.5px] text-river">
                    <RouteIcon className="size-3" strokeWidth={1.9} />
                    查看完整路线
                  </div>
                </button>
              )}
            </>
          ) : (
            <EmptyMapHint />
          )}

          {mapError && (
            <div className="absolute inset-0 z-20 grid place-items-center bg-background/85 p-6 backdrop-blur">
              <div className="w-full max-w-[360px] animate-rise rounded-[26px] border border-hairline bg-card p-6 text-center shadow-[var(--shadow-float)]">
                <span className="mx-auto grid size-11 place-items-center rounded-2xl bg-clay/10 text-clay">
                  <MapPinned className="size-5" strokeWidth={1.7} />
                </span>
                <h3 className="mt-3 font-display text-[16px]">地图没能加载</h3>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                  地图服务暂时不可用，请检查网络后重试。
                </p>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="h-9 flex-1 rounded-full bg-river text-[11.5px] text-primary-foreground transition hover:opacity-90"
                  >
                    重新加载
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {route && (
          <RouteDetail
            route={route}
            score={0}
            showScore={false}
            onClose={() => setDetailOpen(false)}
            activeStop={activeStop}
            onSelectStop={handleSelectStop}
            open={detailOpen}
          />
        )}
      </main>

      <nav className="flex h-14 shrink-0 items-center gap-2 border-t border-hairline bg-background/95 px-4 backdrop-blur lg:hidden">
        <MobileTab
          active={mobileView === "input"}
          onClick={() => setMobileView("input")}
          icon={<RouteIcon className="size-3.5" strokeWidth={1.9} />}
          label="路线"
        />
        <MobileTab
          active={mobileView === "map"}
          onClick={() => setMobileView("map")}
          icon={<MapPinned className="size-3.5" strokeWidth={1.9} />}
          label={route ? "查看地图" : "先规划路线"}
        />
      </nav>

      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] tracking-[0.18em] text-muted-foreground/75">
        {label}
      </span>
      {children}
    </label>
  );
}

function RouteMiniCard({ route, onOpen }: { route: Route; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group block w-full overflow-hidden rounded-[22px] border border-hairline bg-card text-left shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-float)]"
    >
      <div
        className="h-24 w-full"
        style={{
          background: `linear-gradient(135deg, ${route.color} 0%, #182420 100%)`,
        }}
      >
        <div className="flex h-full w-full flex-col justify-between p-3 text-white">
          <div className="flex flex-wrap gap-1">
            <span className="rounded-full border border-white/25 bg-white/10 px-2 py-0.5 text-[9px] backdrop-blur">
              {route.district}
            </span>
            {route.themes.slice(0, 2).map((t) => (
              <span key={t} className="rounded-full border border-white/15 bg-black/20 px-2 py-0.5 text-[9px] backdrop-blur">
                {t}
              </span>
            ))}
          </div>
          <div>
            <p className="font-display text-[16px] leading-tight">{route.name}</p>
            <p className="mt-0.5 truncate text-[10px] text-white/65">{route.subtitle}</p>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3 border-t border-hairline px-4 py-2.5 text-[10.5px] text-muted-foreground">
        <span>⏱ {route.duration}h</span>
        <span>🚶 {route.distance}km</span>
        <span>📍 {route.stops.length} 站</span>
        <span className="ml-auto flex items-center gap-1 text-river opacity-0 transition group-hover:opacity-100">
          详情 <ArrowUpRight className="size-3" strokeWidth={1.9} />
        </span>
      </div>
    </button>
  );
}

function MobileTab({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full text-[12px] transition",
        active ? "bg-river/10 text-river" : "text-muted-foreground"
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function EmptyMapHint() {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
      <div className="pointer-events-auto w-full max-w-[320px] rounded-[22px] border border-hairline bg-background/80 p-5 text-center shadow-[var(--shadow-card)] backdrop-blur-lg">
        <div className="mx-auto mb-2 grid size-10 place-items-center rounded-xl bg-river/10 text-river">
          <MapPinned className="size-4" strokeWidth={1.7} />
        </div>
        <p className="font-display text-[14px]">说一句话，开始一条 City Walk</p>
        <p className="mt-1 text-[10.5px] leading-relaxed text-muted-foreground">
          点位来自 244 条武汉真实地点，路线用高德步行路径逐段计算。
        </p>
      </div>
    </div>
  );
}
