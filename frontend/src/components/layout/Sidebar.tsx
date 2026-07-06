"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/brand/Logo";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-[248px] shrink-0 flex-col border-r border-border bg-surface">
      {/* Masthead — the ONLY sidebar area that carries brand. */}
      <div className="border-b border-border px-4 py-4">
        <Logo />
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-body-sm font-medium transition-colors",
                active
                  ? "bg-surface-2 text-text"
                  : "text-text-secondary hover:bg-surface-2 hover:text-text",
              )}
            >
              {/* Active indicator: brand crimson bar (brand, used sparingly). */}
              <span
                className={cn(
                  "h-4 w-[3px] rounded-full transition-colors",
                  active ? "bg-brand-crimson" : "bg-transparent",
                )}
                aria-hidden
              />
              <Icon size={17} className="shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-4">
        <p className="text-caption text-text-muted">ProofLens · Capture Integrity</p>
        <p className="text-caption text-text-muted">Scores &amp; flags — never blocks.</p>
      </div>
    </aside>
  );
}
