"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * The ABSLI tenant logo. The source PNG is a wide ~2.4:1 lockup on a solid white
 * background, so it is rendered on a light card (the artwork assumes a light
 * ground) with object-contain — never clipped, never distorted.
 *
 * - `md` (masthead): a full-width, centered card that reads as a header.
 * - `sm`: a compact inline chip for dense contexts.
 */
export function TenantLogo({
  size = "md",
  className,
}: {
  size?: "md" | "sm";
  className?: string;
}) {
  const [ok, setOk] = useState(true);
  const box =
    size === "md"
      ? "flex w-full items-center justify-center rounded-lg px-4 py-3"
      : "inline-flex h-8 items-center justify-center rounded-md px-2";
  const imgHeight = size === "md" ? "h-9" : "h-4";

  return (
    <span className={cn("bg-white ring-1 ring-border", box, className)}>
      {ok ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src="/brand/abc-life-insurance.png"
          alt="Aditya Birla Sun Life Insurance"
          className={cn("w-auto object-contain", imgHeight)}
          onError={() => setOk(false)}
        />
      ) : (
        <span
          className={cn(
            "font-bold text-brand-crimson",
            size === "md" ? "text-h2" : "text-body-sm",
          )}
        >
          ABSLI
        </span>
      )}
    </span>
  );
}
