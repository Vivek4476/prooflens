"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { HealthDot } from "@/components/HealthDot";
import { ThemeToggle } from "@/components/ThemeToggle";
import { NAV } from "@/lib/nav";

function titleFor(pathname: string): string {
  const match = NAV.find((n) =>
    n.href === "/" ? pathname === "/" : pathname.startsWith(n.href),
  );
  return match?.label ?? "ProofLens";
}

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-border bg-surface/90 px-6 backdrop-blur">
      <h1 className="text-h1 text-text">{titleFor(pathname)}</h1>

      <form
        className="ml-auto hidden items-center md:flex"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) router.push(`/history?q=${encodeURIComponent(q.trim())}`);
        }}
      >
        <div className="relative">
          <Search
            size={15}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search opportunity or rep ID…"
            className="h-9 w-64 rounded-md border border-border bg-surface pl-8 pr-3 text-body-sm text-text placeholder:text-text-muted focus-visible:border-border-strong"
            aria-label="Search uploads"
          />
        </div>
      </form>

      <div className="ml-auto flex items-center gap-2.5 md:ml-0">
        <HealthDot />
        <ThemeToggle />
        <div
          className="grid h-9 w-9 place-items-center rounded-full bg-surface-2 text-caption font-semibold text-text-secondary"
          title="Demo user"
        >
          UA
        </div>
      </div>
    </header>
  );
}
