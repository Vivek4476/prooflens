"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * The ABSLI tenant logo.
 *
 * - `md` (masthead): a full-bleed, transparent-background lockup
 *   (`absli-logo.png`) that spans the full width of the sidebar bar and sits
 *   directly on the sidebar surface. In dark mode the artwork's maroon text
 *   loses contrast against the dark surface, so it gets a light rounded
 *   panel behind it in that theme only.
 * - `sm`: a compact inline chip on the original white-background PNG, for
 *   dense contexts (e.g. exports) where a light card is still appropriate.
 */
export function TenantLogo({
  size = "md",
  className,
}: {
  size?: "md" | "sm";
  className?: string;
}) {
  const [ok, setOk] = useState(true);

  if (size === "sm") {
    return (
      <span
        className={cn(
          "inline-flex h-8 items-center justify-center rounded-md bg-white px-2 ring-1 ring-border",
          className,
        )}
      >
        {ok ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src="/brand/abc-life-insurance.png"
            alt="Aditya Birla Sun Life Insurance"
            className="h-4 w-auto object-contain"
            onError={() => setOk(false)}
          />
        ) : (
          <span className="text-body-sm font-bold text-brand-crimson">ABSLI</span>
        )}
      </span>
    );
  }

  return (
    <span
      className={cn(
        // A consistent white card in BOTH themes so the tenant's maroon lockup stays legible,
        // with generous clear space around a medium logo.
        "flex w-full items-center justify-center rounded-lg border border-border bg-white px-4 py-3.5",
        className,
      )}
    >
      {ok ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src="/brand/absli-logo.png"
          alt="Aditya Birla Sun Life Insurance"
          className="h-9 w-auto max-w-full object-contain"
          onError={() => setOk(false)}
        />
      ) : (
        <span className="text-h2 font-bold text-brand-crimson">ABSLI</span>
      )}
    </span>
  );
}
