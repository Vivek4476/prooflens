import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-sm", className)} />;
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function CardsSkeleton({
  count = 5,
  className,
}: {
  count?: number;
  /** Grid columns override — defaults to the 5-card dashboard layout;
   *  pass the consuming page's real grid (e.g. analytics' 2/4-col KpiRow)
   *  so the loading state doesn't reflow once data arrives. */
  className?: string;
}) {
  return (
    <div className={cn("grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-[92px] w-full" />
      ))}
    </div>
  );
}
