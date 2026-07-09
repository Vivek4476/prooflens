import Link from "next/link";
import type { LucideIcon } from "lucide-react";

/**
 * Empty states teach: what this page does, why it's empty, and one clear CTA.
 */
export function EmptyState({
  icon: Icon,
  title,
  what,
  why,
  cta,
}: {
  icon: LucideIcon;
  title: string;
  what: string;
  why?: string;
  cta?: { label: string; href: string };
}) {
  return (
    <div className="card flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full bg-surface-2 text-text-secondary">
        <Icon size={22} />
      </div>
      <h3 className="text-h2 text-text">{title}</h3>
      <p className="max-w-md text-body-sm text-text-secondary">{what}</p>
      {why && <p className="max-w-md text-caption text-text-muted">{why}</p>}
      {cta && (
        <Link
          href={cta.href}
          className="mt-2 inline-flex h-10 items-center rounded-md bg-accent px-4 text-body-sm font-medium text-accent-fg transition-colors hover:bg-accent-hover"
        >
          {cta.label}
        </Link>
      )}
    </div>
  );
}
