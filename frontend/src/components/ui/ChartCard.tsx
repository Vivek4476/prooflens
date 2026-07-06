import { Card, CardHeader } from "./Card";

/** A chart always answers a question — the subtitle states the "so what". */
export function ChartCard({
  title,
  subtitle,
  children,
  height = 260,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  height?: number;
}) {
  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} />
      <div className="p-4" style={{ height }}>
        {children}
      </div>
    </Card>
  );
}
