import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Info, Moon, Sun } from "lucide-react";

interface HeaderProps {
  onOpenAbout: () => void;
}

export function Header({ onOpenAbout }: HeaderProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <header className="relative z-40 flex h-16 shrink-0 items-center gap-4 border-b border-hairline bg-background/85 px-4 backdrop-blur-xl lg:px-6">
      <div className="flex items-center gap-3">
        <div className="grid size-10 place-items-center rounded-[11px] bg-river text-primary-foreground shadow-[0_10px_20px_-12px_rgba(20,82,76,0.9)]">
          <span className="font-display text-lg leading-none">江</span>
        </div>
        <div className="leading-tight">
          <div className="font-display text-[17px] tracking-[0.18em] text-foreground">
            漫步江城
          </div>
          <div className="text-[9px] tracking-[0.3em] text-muted-foreground">
            WUHAN CITY WALK
          </div>
        </div>
      </div>

      <nav className="ml-2 hidden items-center gap-1 lg:flex">
        <span className="relative rounded-full bg-river/10 px-3.5 py-2 text-[12.5px] text-river">
          路线推荐
          <span className="absolute inset-x-3 -bottom-[13px] h-px bg-river/60" />
        </span>
      </nav>

      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          title={isDark ? "切换到日间" : "切换到夜间"}
          className="grid size-9 place-items-center rounded-full text-muted-foreground transition hover:bg-secondary hover:text-foreground"
        >
          {isDark ? (
            <Sun className="size-4" strokeWidth={1.7} />
          ) : (
            <Moon className="size-4" strokeWidth={1.7} />
          )}
        </button>

        <button
          type="button"
          onClick={onOpenAbout}
          title="关于漫步江城"
          className="grid size-9 place-items-center rounded-full text-muted-foreground transition hover:bg-secondary hover:text-foreground"
        >
          <Info className="size-4" strokeWidth={1.7} />
        </button>
      </div>
    </header>
  );
}
