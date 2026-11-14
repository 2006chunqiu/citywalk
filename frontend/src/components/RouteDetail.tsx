import {
  ArrowUpRight,
  Clock3,
  Footprints,
  Lightbulb,
  MapPin,
  Navigation,
  Signal,
  SunMedium,
  X,
} from "lucide-react";
import { CoverImage } from "@/components/CoverImage";
import { StopThumb } from "@/components/StopThumb";
import { amapMarkerUrl, type Route } from "@/data/routes";
import { cn } from "@/lib/utils";

interface RouteDetailProps {
  route: Route;
  score: number;
  showScore: boolean;
  onClose: () => void;
  activeStop: number | null;
  onSelectStop: (index: number) => void;
  open: boolean;
}

export function RouteDetail({
  route,
  score,
  showScore,
  onClose,
  activeStop,
  onSelectStop,
  open,
}: RouteDetailProps) {
  return (
    <aside
      aria-hidden={!open}
      className={cn(
        "fixed inset-0 z-50 flex flex-col bg-background transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] lg:absolute lg:inset-y-0 lg:left-auto lg:right-0 lg:z-30 lg:w-[424px] lg:border-l lg:border-hairline lg:shadow-[var(--shadow-float)]",
        open ? "translate-x-0" : "pointer-events-none translate-x-full"
      )}
    >
      <div className="relative h-[210px] shrink-0 overflow-hidden lg:h-[236px]">
        <CoverImage route={route} className="h-full w-full" priority />
        <div className="absolute inset-0 bg-gradient-to-t from-black/88 via-black/35 to-black/10" />

        <button
          type="button"
          onClick={onClose}
          aria-label="关闭路线详情"
          className="absolute right-4 top-4 grid size-9 place-items-center rounded-full border border-white/25 bg-black/30 text-white/90 backdrop-blur transition hover:bg-black/50"
        >
          <X className="size-4" strokeWidth={1.9} />
        </button>

        {showScore && (
          <div className="absolute left-4 top-4 rounded-full border border-white/25 bg-black/30 px-3 py-1 text-[10.5px] tracking-wide text-white/90 backdrop-blur">
            契合度 {score}
          </div>
        )}

        <div className="absolute inset-x-5 bottom-4">
          <div className="mb-2 flex flex-wrap gap-1.5">
            <span className="rounded-full border border-white/25 bg-white/10 px-2 py-0.5 text-[9.5px] tracking-[0.16em] text-white/85 backdrop-blur">
              {route.district}
            </span>
            {route.themes.map((theme) => (
              <span
                key={theme}
                className="rounded-full border border-white/15 bg-black/20 px-2 py-0.5 text-[9.5px] text-white/75 backdrop-blur"
              >
                {theme}
              </span>
            ))}
          </div>
          <h2 className="font-display text-[25px] leading-tight tracking-wide text-white">
            {route.name}
          </h2>
          <p className="mt-1 text-[11px] tracking-wide text-white/60">
            {route.subtitle}
          </p>
        </div>
      </div>

      <div className="panel-scroll flex-1 overflow-y-auto overscroll-contain">
        <div className="space-y-6 px-5 pb-8 pt-5">
          <div className="grid grid-cols-4 divide-x divide-hairline rounded-2xl border border-hairline bg-surface py-3">
            <MetaItem
              icon={<Clock3 className="size-3.5" strokeWidth={1.7} />}
              label="时长"
              value={`${route.duration}h`}
            />
            <MetaItem
              icon={<Footprints className="size-3.5" strokeWidth={1.7} />}
              label="距离"
              value={`${route.distance}km`}
            />
            <MetaItem
              icon={<Signal className="size-3.5" strokeWidth={1.7} />}
              label="强度"
              value={route.intensity}
            />
            <MetaItem
              icon={<SunMedium className="size-3.5" strokeWidth={1.7} />}
              label="最佳"
              value={route.bestTime[0]}
            />
          </div>

          <section>
            <SectionTitle>这条路上</SectionTitle>
            <p className="text-[12.5px] leading-[1.95] text-foreground/80">
              {route.story}
            </p>
          </section>

          <section>
            <SectionTitle>不要错过</SectionTitle>
            <ul className="grid grid-cols-2 gap-2">
              {route.highlights.map((item) => (
                <li
                  key={item}
                  className="rounded-xl border border-dashed border-hairline bg-surface/60 px-3 py-2 text-[11px] leading-snug text-foreground/75"
                >
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <SectionTitle>沿途站点</SectionTitle>
            <div className="mt-1">
              {route.stops.map((stop, index) => {
                const isActive = activeStop === index;
                return (
                  <button
                    key={stop.name}
                    type="button"
                    onClick={() => onSelectStop(index)}
                    className="group flex w-full gap-3 text-left"
                  >
                    <div className="flex flex-col items-center">
                      <span
                        className={cn(
                          "grid size-6 shrink-0 place-items-center rounded-full border font-display text-[10.5px] transition",
                          isActive
                            ? "border-transparent bg-clay text-white"
                            : "border-hairline bg-surface text-muted-foreground group-hover:border-river/50 group-hover:text-river"
                        )}
                      >
                        {index + 1}
                      </span>
                      {index < route.stops.length - 1 && (
                        <span className="my-1 w-px flex-1 bg-hairline" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1 pb-4">
                      <div className="flex gap-2.5">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-display text-[14px] text-foreground">
                              {stop.name}
                            </span>
                            <span className="rounded bg-secondary px-1.5 py-0.5 text-[9.5px] text-muted-foreground">
                              {stop.stay}
                            </span>
                            <span className="ml-auto flex items-center gap-0.5 text-[10px] text-river opacity-0 transition group-hover:opacity-100">
                              <MapPin className="size-2.5" strokeWidth={2} />
                              定位
                            </span>
                          </div>
                          <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
                            {stop.desc}
                          </p>
                        </div>
                        {index > 0 && index < route.stops.length - 1 && (
                          <StopThumb stop={stop} className="size-14 rounded-lg" />
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section>
            <SectionTitle>漫步贴士</SectionTitle>
            <ul className="space-y-2">
              {route.tips.map((tip, index) => (
                <li
                  key={tip}
                  className="flex gap-2 text-[11.5px] leading-relaxed text-foreground/75"
                >
                  <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full bg-clay/12 text-[9px] font-medium text-clay">
                    {index + 1}
                  </span>
                  {tip}
                </li>
              ))}
            </ul>
          </section>

          <p className="flex items-start gap-1.5 rounded-xl bg-secondary/60 px-3 py-2 text-[10.5px] leading-relaxed text-muted-foreground">
            <Lightbulb className="mt-0.5 size-3 shrink-0" strokeWidth={1.8} />
            地图上的折线是高德真实步行路径，照着走即可；出行前请核实场馆开放时间。
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 border-t border-hairline bg-background/95 px-5 py-3.5 backdrop-blur">
        <a
          href={amapMarkerUrl(route.stops[0])}
          target="_blank"
          rel="noreferrer"
          className="flex h-10 flex-1 items-center justify-center gap-1.5 rounded-full bg-river text-[12px] text-primary-foreground transition hover:opacity-90"
        >
          <Navigation className="size-3.5" strokeWidth={1.9} />
          导航到起点 · {route.start}
        </a>
        <ArrowUpRight className="hidden size-3.5 text-muted-foreground/50 lg:block" strokeWidth={1.9} />
      </div>
    </aside>
  );
}

function MetaItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-muted-foreground/70">{icon}</span>
      <span className="text-[12px] font-medium text-foreground">{value}</span>
      <span className="text-[9.5px] text-muted-foreground">{label}</span>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2.5 flex items-center gap-2 font-display text-[14px] tracking-wide text-foreground">
      <span className="h-3 w-[2px] rounded-full bg-clay" />
      {children}
    </h3>
  );
}
