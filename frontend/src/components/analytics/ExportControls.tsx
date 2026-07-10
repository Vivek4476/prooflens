"use client";

import { Download, Printer } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { analyticsToCsv, csvFilename } from "@/lib/analytics/exportCsv";
import type { AnalyticsSummary } from "@/lib/api/types";

/**
 * CSV download + print/PDF for the current analytics view. The CSV is a sectioned report
 * (summary KPIs + time series + top reasons) built from the same summary the page shows, so
 * an export never disagrees with the screen. Marked `no-print` so the controls don't appear
 * in the PDF.
 */
export function ExportControls({ analytics }: { analytics: AnalyticsSummary }) {
  function downloadCsv() {
    const blob = new Blob([analyticsToCsv(analytics)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = csvFilename(analytics.period);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="no-print flex items-center gap-2">
      <Button variant="secondary" onClick={downloadCsv} aria-label="Download analytics as CSV">
        <Download aria-hidden className="h-4 w-4" />
        <span className="hidden sm:inline">CSV</span>
      </Button>
      <Button variant="ghost" onClick={() => window.print()} aria-label="Print or save as PDF">
        <Printer aria-hidden className="h-4 w-4" />
        <span className="hidden sm:inline">Print</span>
      </Button>
    </div>
  );
}
