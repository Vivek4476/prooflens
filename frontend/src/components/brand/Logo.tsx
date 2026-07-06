"use client";

import { useState } from "react";

/**
 * Aditya Birla Capital — Life Insurance logo.
 * Loads /brand/abc-life-insurance.png; if absent, renders a placeholder of a
 * similar aspect ratio (see README). The logo is never recolored; in dark mode
 * it sits on a light chip because the artwork assumes a light background.
 */
export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  const [failed, setFailed] = useState(false);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="inline-flex items-center rounded-md bg-white px-2 py-1.5 shadow-1 dark:ring-1 dark:ring-black/10">
        {failed ? (
          <Placeholder collapsed={collapsed} />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src="/brand/abc-life-insurance.png"
            alt="Aditya Birla Capital — Life Insurance"
            className={collapsed ? "h-7 w-auto" : "h-8 w-auto"}
            onError={() => setFailed(true)}
          />
        )}
      </div>
      {/* Gold rule — echoes the logo's own gold bar. Appears here and nowhere else. */}
      <div className="h-[2px] w-full rounded-full bg-brand-gold" aria-hidden />
    </div>
  );
}

function Placeholder({ collapsed }: { collapsed: boolean }) {
  return (
    <div className={collapsed ? "flex h-7 items-center gap-2" : "flex h-8 items-center gap-2"}>
      <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-crimson text-[11px] font-bold text-white">
        ABC
      </span>
      {!collapsed && (
        <span className="text-body-sm font-semibold leading-tight text-[#7a1420]">
          Aditya Birla Capital
          <span className="block text-caption font-normal text-text-muted">
            Life Insurance · logo placeholder
          </span>
        </span>
      )}
    </div>
  );
}
