import { useState } from "react";
import { stopImageUrl, type Stop } from "@/data/routes";
import { cn } from "@/lib/utils";

interface StopThumbProps {
  stop: Stop;
  className?: string;
}

export function StopThumb({ stop, className }: StopThumbProps) {
  const [failed, setFailed] = useState(false);

  return (
    <div
      className={cn(
        "shrink-0 overflow-hidden border border-hairline bg-secondary",
        className
      )}
    >
      {failed ? (
        <div className="grid h-full w-full place-items-center text-[10px] text-muted-foreground">
          {stop.kind}
        </div>
      ) : (
        <img
          src={stopImageUrl(stop)}
          alt={`${stop.name} 实景`}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      )}
    </div>
  );
}
