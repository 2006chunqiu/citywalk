import { useEffect } from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

function Modal({
  open,
  onClose,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 animate-fade bg-black/45 backdrop-blur-[3px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative w-full max-w-[440px] animate-rise overflow-hidden rounded-[26px] border border-hairline bg-card p-6 shadow-[var(--shadow-float)]",
          className
        )}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭"
          className="absolute right-4 top-4 grid size-8 place-items-center rounded-full text-muted-foreground transition hover:bg-secondary hover:text-foreground"
        >
          <X className="size-4" strokeWidth={1.8} />
        </button>
        {children}
      </div>
    </div>
  );
}

export function AboutDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Modal open={open} onClose={onClose}>
      <p className="text-[10px] tracking-caps text-muted-foreground">
        ABOUT · WUHAN CITY WALK
      </p>
      <h2 className="mt-2 font-display text-[22px] tracking-wide">
        漫步江城
      </h2>
      <p className="mt-3 text-[12px] leading-[1.9] text-foreground/80">
        一个为武汉做的 AI City Walk 路线规划器。告诉它起点、终点，或只是说一句"想走点安静的老街"，它会在武汉三镇为你画出一条能走的线。
      </p>

      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        {[
          { value: "AI", label: "实时生成" },
          { value: "5", label: "武汉片区" },
          { value: "∞", label: "条可能路线" },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-hairline bg-surface/70 py-2.5"
          >
            <div className="font-display text-lg text-river">{item.value}</div>
            <div className="text-[9.5px] text-muted-foreground">
              {item.label}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-1.5 border-t border-dashed border-hairline pt-4 text-[10.5px] leading-relaxed text-muted-foreground">
        <p>地图组件基于开源项目 amapcn，地图服务与数据版权归高德地图所有。</p>
        <p>路线由 DeepSeek 实时生成，站点坐标由高德地理编码解析，不作为精确导航依据。</p>
        <p>摄影图片由 AI 生成，仅用于界面展示。</p>
      </div>

      <p className="mt-4 font-display text-[11px] tracking-[0.2em] text-muted-foreground/70">
        武汉 · 江湖之上
      </p>
    </Modal>
  );
}
