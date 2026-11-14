import { type Route } from "@/data/routes";
import { cn } from "@/lib/utils";

interface CoverImageProps {
  route: Route;
  className?: string;
  priority?: boolean;
}

/** 不依赖外部文生图接口：用路线主色做渐变封面，保证离线演示也稳定。 */
export function CoverImage({ route, className }: CoverImageProps) {
  return (
    <div
      className={cn("relative overflow-hidden", className)}
      style={{
        background: `radial-gradient(120% 120% at 18% 0%, ${route.color} 0%, #1b2a24 58%, #121b17 100%)`,
      }}
    >
      <svg
        aria-hidden
        viewBox="0 0 400 240"
        className="pointer-events-none absolute inset-0 h-full w-full text-white/10"
        preserveAspectRatio="xMidYMid slice"
      >
        <circle cx="330" cy="40" r="70" fill="none" stroke="currentColor" />
        <circle cx="330" cy="40" r="48" fill="none" stroke="currentColor" strokeDasharray="3 6" />
        <path d="M-20 190 C90 120 210 230 430 130" fill="none" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      <div className="relative flex h-full w-full flex-col items-center justify-center gap-1 text-primary-foreground/90">
        <span className="font-display text-2xl tracking-[0.3em]">
          {route.district}
        </span>
        <span className="text-[10px] tracking-[0.24em] opacity-70 max-w-full truncate px-4">
          {route.start} 出发
        </span>
      </div>
    </div>
  );
}
