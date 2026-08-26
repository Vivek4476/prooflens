import { cn } from "@/lib/utils";

export function Card({
  className,
  glow,
  children,
}: {
  className?: string;
  glow?: boolean;
  children: React.ReactNode;
}) {
  return <div className={cn("card", glow && "card-glow", className)}>{children}</div>;
}

export function CardHeader({
  title,
  subtitle,
  action,
  serif,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  serif?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div>
        <h2 className={cn("text-h2 text-text", serif && "font-serif text-h1 font-semibold tracking-tight")}>
          {title}
        </h2>
        {subtitle && <p className="mt-0.5 text-caption text-text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
