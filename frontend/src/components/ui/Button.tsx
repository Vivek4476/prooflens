import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  // Brand crimson is reserved for primary actions.
  primary:
    "bg-brand-crimson text-white hover:bg-brand-crimson-hover disabled:opacity-50",
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
