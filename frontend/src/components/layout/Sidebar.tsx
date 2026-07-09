"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AbsliMasthead } from "@/components/brand/AbsliMasthead";
import { PoweredByProofLens } from "@/components/brand/PoweredByProofLens";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

/**
 * The nav body, shared by the desktop rail (<Sidebar>) and the mobile drawer
 * (<MobileNav>). onNavigate lets the drawer close itself on link click.
 */
export function SidebarInner({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      {/* ABSLI-first masthead: the tenant is the primary brand. */}
      <div className="border-b border-border px-4 py-4">
        <AbsliMasthead />
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-body-sm font-medium transition-colors",
                active
                  ? "bg-surface-2 text-accent"
                  : "text-text-secondary hover:bg-surface-2 hover:text-text",
              )}
            >
              <Icon size={17} className={cn("shrink-0", active && "text-accent")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2.5 border-t border-border p-4">
        <PoweredByProofLens />
        <p className="text-caption text-text-muted">Scores &amp; flags — never blocks. Images are never stored.</p>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="flex h-full w-[248px] shrink-0 flex-col border-r border-border bg-surface">
      <SidebarInner />
    </aside>
  );
}
