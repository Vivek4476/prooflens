import type { ReactNode } from "react";

/**
 * The single page-header contract: title + optional description + optional
 * actions, together. Replaces the old split of a Topbar h1 plus a floating
 * rhetorical subtitle on each page. Every page owns exactly one of these.
 */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-h1 text-text">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-body-sm text-text-secondary">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
