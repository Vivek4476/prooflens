import { Card, CardHeader } from "./Card";

/** A chart always answers a question — the subtitle states the "so what". */
export function ChartCard({
  title,
  subtitle,
  children,
  height = 260,
  action,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  height?: number;
  /** Optional control rendered in the header, opposite the title (e.g. a row-count selector). */
  action?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} action={action} />
      <div className="p-4" style={{ height }}>
        {children}
      </div>
    </Card>
  );
}
