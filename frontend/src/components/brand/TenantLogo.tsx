"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * The ABSLI tenant logo, fitted to its real ~2:1 proportions. The source PNG is
 * a wide horizontal lockup, so it is rendered in a height-constrained, width-auto
 * white card (object-contain, padded, NOT clipped) — never forced into a square.
 */
export function TenantLogo({
  size = "md",
  className,
}: {
  size?: "md" | "sm";
  className?: string;
}) {
  const [ok, setOk] = useState(true);
  const box = size === "md" ? "h-11 px-3" : "h-8 px-2";
  const img = size === "md" ? "max-h-6" : "max-h-4";

  if (!ok) {
    return (
      <span
        className={cn(
          "inline-grid place-items-center rounded-md bg-white ring-1 ring-border",
          box,
          className,
        )}
      >
        <span className="text-body-sm font-bold text-brand-crimson">ABSLI</span>
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md bg-white ring-1 ring-border",
        box,
        className,
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/abc-life-insurance.png"
        alt="Aditya Birla Sun Life Insurance"
        className={cn("w-auto object-contain", img)}
        onError={() => setOk(false)}
      />
    </span>
  );
}
