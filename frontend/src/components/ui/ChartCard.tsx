import { Card, CardHeader } from "./Card";

/** A chart always answers a question — the subtitle states the "so what". */
export function ChartCard({
  title,
  subtitle,
  children,
  height = 260,
  fullWidth,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  height?: number;
  fullWidth?: boolean;
}) {
  return (
    <Card
      className={`hover:shadow-2 hover:-translate-y-0.5 transition-all duration-300${
        fullWidth ? " lg:col-span-2" : ""
      }`}
    >
      <CardHeader title={title} subtitle={subtitle} />
      <div className="p-4" style={{ height }}>
        {children}
      </div>
    </Card>
  );
}
