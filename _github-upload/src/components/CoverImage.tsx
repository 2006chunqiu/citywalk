import { useState } from "react";
import { coverUrl, type Route } from "@/data/routes";
import { cn } from "@/lib/utils";

interface CoverImageProps {
  route: Route;
  className?: string;
  priority?: boolean;
}

export function CoverImage({ route, className, priority }: CoverImageProps) {
  const [failed, setFailed] = useState(false);

  return (
    <div
      className={cn("relative overflow-hidden", className)}
      style={{
        background: `linear-gradient(135deg, ${route.color} 0%, #182420 100%)`,
      }}
    >
      {!failed ? (
        <img
          src={coverUrl(route.cover)}
          alt={`${route.name} 沿途风景`}
          loading={priority ? "eager" : "lazy"}
          onError={() => setFailed(true)}
          className="h-full w-full object-cover transition-transform duration-[900ms] ease-out group-hover:scale-[1.045]"
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-primary-foreground/85">
          <span className="font-display text-2xl tracking-[0.3em]">
            {route.district}
          </span>
          <span className="text-[10px] tracking-[0.24em] opacity-70">
            {route.start}
          </span>
        </div>
      )}
    </div>
  );
}
