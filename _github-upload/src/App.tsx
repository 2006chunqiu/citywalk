import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Loader2,
  MapPinned,
  Route as RouteIcon,
  Sparkles,
  Wand2,
} from "lucide-react";
import type { MapRef } from "amapcn";
import { Header } from "@/components/Header";
import { RouteDetail } from "@/components/RouteDetail";
import { MapView } from "@/components/MapView";
import { AboutDialog } from "@/components/Dialogs";
import { THEMES, INTENSITIES, type Route, type Theme, type Intensity } from "@/data/routes";
import { generateRoutes, AiRouteError, type RouteRequest } from "@/lib/aiRoute";
import { geocodeStops, GeocodeError } from "@/lib/geocode";
import { buildWalkingPath } from "@/lib/directions";
import { cn } from "@/lib/utils";

const amapKey = import.meta.env.VITE_AMAP_KEY || "";
const amapSecurity = import.meta.env.VITE_AMAP_SECURITY_CODE || "";

type GenStatus = "idle" | "loading" | "geocoding" | "done" | "error";

interface GenError {
  code: string;
  message: string;
}

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
  const [geocodeFailed, setGeocodeFailed] = useState(0);

  const [activeStop, setActiveStop] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [mobileView, setMobileView] = useState<"input" | "map">("input");

  const mapRef = useRef<MapRef | null>(null);
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

  useEffect(() => {
    if (!isMobile || mobileView !== "map") return;
    const timer = window.setTimeout(() => {
      const map = mapRef.current;
      if (!map) return;
      map.resize();
      map.setFitView(null, false, [150, 165, 40, 40]);
    }, 160);
    return () => window.clearTimeout(timer);
  }, [isMobile, mobileView, route?.id]);

  const handleGenerate = async () => {
    setError(null);
    setGeocodeFailed(0);
    setRoutes([]);
    setPaths([]);
    setSelected(0);
    setActiveStop(null);

    const req: RouteRequest = {
      start: start.trim() || undefined,
      end: end.trim() || undefined,
      theme: theme || undefined,
      duration,
      intensity: intensity || undefined,
      freePrompt: freePrompt.trim() || undefined,
    };

    setStatus("loading");
    let aiRoutes: Route[];
    try {
      aiRoutes = await generateRoutes(req);
    } catch (e) {
      if (e instanceof AiRouteError) {
        setError({ code: e.code, message: e.message });
      } else {
        setError({ code: "UNKNOWN", message: String(e) });
      }
      setStatus("error");
      return;
    }

    setStatus("geocoding");
    let failedTotal = 0;
    let geocodeError: string | null = null;
    const located = await Promise.all(
      aiRoutes.map(async (r) => {
        try {
          const { stops, failed } = await geocodeStops(r.stops);
          failedTotal += failed;
          return { ...r, stops };
        } catch (e) {
          // 地理编码整体失败也不阻塞，用占位坐标继续
          if (e instanceof GeocodeError && !geocodeError) {
            geocodeError = `地理编码失败：${e.message}。路线已生成但站点位置可能不准。`;
          }
          failedTotal += r.stops.length;
          return r;
        }
      })
    );
    if (geocodeError) setError({ code: "GEOCODE", message: geocodeError });
    setGeocodeFailed(failedTotal);

    // 逐段调高德步行规划，让折线沿真实道路走；失败则回退直线
    const walkingPaths = await Promise.all(
      located.map((r) => buildWalkingPath(r.stops).catch(() => null))
    );

    setRoutes(located);
    setPaths(walkingPaths);
    setSelected(0);
    setStatus("done");
    if (isMobile) setMobileView("map");
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

  const canGenerate =
    status !== "loading" &&
    status !== "geocoding" &&
    (start.trim() || end.trim() || theme || freePrompt.trim().length > 0);

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
                  输入起点、终点或单纯说一句"想走点安静的老街"，DeepSeek 会在武汉三镇为你规划一条能走的路线。
                </p>
              </section>

              {/* 表单 */}
              <section className="mt-4 rounded-[22px] border border-hairline bg-card p-4 shadow-[var(--shadow-card)]">
                <div className="mb-3 flex items-center gap-2">
                  <Sparkles className="size-3.5 text-clay" strokeWidth={1.9} />
                  <p className="text-[10px] tracking-[0.24em] text-muted-foreground">
                    AI 路线规划
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
                    {status === "loading" ? (
                      <>
                        <Loader2 className="size-4 animate-spin" strokeWidth={1.9} />
                        AI 正在规划路线…
                      </>
                    ) : status === "geocoding" ? (
                      <>
                        <Loader2 className="size-4 animate-spin" strokeWidth={1.9} />
                        正在定位站点…
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
                  <p className="font-display text-[12px]">路线生成失败</p>
                  <p className="mt-1 opacity-90">{error.message}</p>
                  {error.code === "MISSING_KEY" && (
                    <p className="mt-1 text-[10.5px] opacity-70">
                      需要在项目根目录的 <code>.env</code> 里配置 <code>DEEPSEEK_API_KEY</code> 和 <code>AMAP_WEB_KEY</code>，然后重启 dev server。
                    </p>
                  )}
                </section>
              )}

              {/* 生成结果 */}
              {route && status === "done" && (
                <section className="mt-4">
                  <div className="mb-2 mt-2 flex items-end justify-between">
                    <div>
                      <p className="text-[9px] tracking-[0.26em] text-muted-foreground/70">
                        AI 为你规划 · {routes.length} 条备选
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

                  {geocodeFailed > 0 && (
                    <p className="mt-2 text-[10.5px] leading-relaxed text-clay/80">
                      有 {geocodeFailed} 个站点未在地图上找到，已用占位位置代替。
                    </p>
                  )}
                </section>
              )}

              {/* 空闲提示 */}
              {status === "idle" && !route && (
                <section className="mt-4 rounded-[18px] border border-dashed border-hairline px-4 py-6 text-center text-[11px] leading-relaxed text-muted-foreground/80">
                  <RouteIcon className="mx-auto mb-2 size-5 text-muted-foreground/60" strokeWidth={1.7} />
                  左边表单里随便填点什么，AI 会在右边地图上画出一条路线。
                </section>
              )}

              <p className="mt-6 border-t border-dashed border-hairline pt-4 text-[10px] leading-relaxed text-muted-foreground/75">
                路线由 DeepSeek 实时生成，站点位置由高德地图地理编码服务解析。出行前请核实场馆开放时间。
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
            amapKey={amapKey}
            securityJsCode={amapSecurity}
            mapRef={mapRef}
            onError={() => setMapError(true)}
          />

          {route ? (
            <>
              <div className="pointer-events-none absolute left-4 top-4 z-10 flex items-center gap-2 rounded-full border border-hairline bg-background/85 px-3 py-1.5 text-[10.5px] text-muted-foreground shadow-sm backdrop-blur">
                <span className="size-1.5 rounded-full bg-clay" />
                {route.district} · {route.stops.length} 站 · {route.distance}km · AI 规划
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
          label="AI 路线"
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
        <p className="font-display text-[14px]">在左边告诉 AI 你想怎么走</p>
        <p className="mt-1 text-[10.5px] leading-relaxed text-muted-foreground">
          输入起点、终点或单纯说一句需求，AI 会在武汉三镇为你规划一条能走的路线。
        </p>
      </div>
    </div>
  );
}
