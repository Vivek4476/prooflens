"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { HealthDot } from "@/components/HealthDot";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AccountMenu } from "@/components/layout/AccountMenu";
import { MobileNav } from "@/components/layout/MobileNav";

/**
 * Global chrome only. The page TITLE now lives in each page's <PageHeader>, so
 * the header no longer duplicates it — this bar carries navigation (mobile),
 * search, system health, theme, and account.
 */
export function Topbar() {
  const router = useRouter();
  const [q, setQ] = useState("");

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-surface/90 px-4 backdrop-blur md:px-6">
      <MobileNav />

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

      <div className="ml-auto flex items-center gap-2.5 md:ml-4">
        <HealthDot />
        <ThemeToggle />
        <AccountMenu />
      </div>
    </header>
  );
}
