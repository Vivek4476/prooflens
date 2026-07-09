import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  // Focus Indigo is the product's one accent — primary actions, never tenant
  // crimson (BRAND.md §6/§9: tenant brand is a guest, confined to the tenant
  // identity chip; it is never interface chrome or a button).
  primary: "bg-accent text-white hover:bg-accent-hover disabled:opacity-50",
  secondary:
    "border border-border-strong bg-surface text-text hover:bg-surface-2 disabled:opacity-50",
  ghost: "text-text-secondary hover:bg-surface-2 hover:text-text disabled:opacity-50",
  danger:
    "border border-verdict-suspect/30 bg-verdict-suspect-bg text-verdict-suspect-fg hover:bg-verdict-suspect/10 disabled:opacity-50",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "secondary", className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex h-10 min-h-[44px] items-center justify-center gap-2 rounded-md px-4 text-body-sm font-medium transition-colors disabled:cursor-not-allowed sm:min-h-0",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
});
