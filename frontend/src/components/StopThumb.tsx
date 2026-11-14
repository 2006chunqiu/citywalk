import { type Stop } from "@/data/routes";
import { cn } from "@/lib/utils";

interface StopThumbProps {
  stop: Stop;
  className?: string;
}

/** 站点缩略图：不再调用第三方文生图，直接用类型标签占位，保证离线可用。 */
export function StopThumb({ stop, className }: StopThumbProps) {
  return (
    <div
      className={cn(
        "relative grid shrink-0 place-items-center overflow-hidden rounded border border-hairline bg-[linear-gradient(135deg,#e7e2d5_0%,#d6cfbc_100%)]",
        className,
      )}
    >
      <span className="text-[10px] tracking-[0.16em] text-[#6b6552]">
        {stop.kind}
      </span>
    </div>
  );
}
