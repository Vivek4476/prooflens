"use client";

import { AlertCircle, ArrowRight, CheckCircle2, Download, RotateCcw, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { api } from "@/lib/api/client";
import type { Band, BulkJob, BulkResultItem } from "@/lib/api/types";
import { buildBulkRows, parseCsv, type ColumnMapping } from "@/lib/bulk/parseCsv";
import { bulkResultsFilename, bulkResultsToCsv } from "@/lib/bulk/exportBulkCsv";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAPPING_STORAGE_KEY = "prooflens.bulk.columnMapping";
const POLL_MS = 1000;
const NONE = "__none__"; // sentinel for "no column" in the optional <select>s

type Stage = "upload" | "map" | "running" | "results";

/** Best-guess a header for a role from a list of candidate substrings (case-insensitive). */
function guessHeader(headers: string[], candidates: string[]): string | undefined {
  const lower = headers.map((h) => h.toLowerCase());
  for (const cand of candidates) {
    const idx = lower.findIndex((h) => h.includes(cand));
    if (idx >= 0) return headers[idx];
  }
  return undefined;
}

function guessMapping(headers: string[]): ColumnMapping {
  return {
    imageCol: guessHeader(headers, ["image", "photo", "url"]) ?? headers[0] ?? "",
    repIdCol: guessHeader(headers, ["agent", "rep"]),
    opportunityIdCol: guessHeader(headers, ["opportunity", "opp"]),
  };
}

/** Same shape as analyze/page.tsx's helper — pull FastAPI's `detail` out of an axios error. */
function errorDetail(err: unknown): string | null {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  return e?.message ?? null;
}

function truncateUrl(url: string, max = 44): string {
  if (url.length <= max) return url;
  return `${url.slice(0, max - 1)}…`;
}

export default function BulkUploadPage() {
  const [stage, setStage] = useState<Stage>("upload");
  const [fileName, setFileName] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [csvRows, setCsvRows] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<ColumnMapping>({ imageCol: "" });

  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<BulkJob | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load a remembered mapping once headers are known, so returning operators
  // don't re-map the same LSQ export shape every time.
  useEffect(() => {
    if (headers.length === 0) return;
    try {
      const raw = window.localStorage.getItem(MAPPING_STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as ColumnMapping;
        if (saved.imageCol && headers.includes(saved.imageCol)) {
          setMapping({
            imageCol: saved.imageCol,
            repIdCol: saved.repIdCol && headers.includes(saved.repIdCol) ? saved.repIdCol : undefined,
            opportunityIdCol:
              saved.opportunityIdCol && headers.includes(saved.opportunityIdCol)
                ? saved.opportunityIdCol
                : undefined,
          });
          return;
        }
      }
    } catch {
      // Corrupt/unavailable localStorage — fall through to the best-guess mapping.
    }
    setMapping(guessMapping(headers));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [headers]);

  function persistMapping(next: ColumnMapping) {
    setMapping(next);
    try {
      window.localStorage.setItem(MAPPING_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Best-effort only — not remembering the mapping isn't fatal.
    }
  }

  async function handleFile(file: File) {
    setParseError(null);
    setFileName(file.name);
    try {
      const text = await file.text();
      const { headers: h, rows } = parseCsv(text);
      if (h.length === 0) {
        setParseError("This file has no header row — check it's a CSV export, then try again.");
        setStage("upload");
        return;
      }
      setHeaders(h);
      setCsvRows(rows);
      setStage("map");
    } catch {
      setParseError("Couldn't read this file as CSV. Check the export and try again.");
      setStage("upload");
    }
  }

  const { valid, skipped } = useMemo(
    () => buildBulkRows(csvRows, mapping),
    [csvRows, mapping],
  );

  function resetAll() {
    if (pollRef.current) clearInterval(pollRef.current);
    setStage("upload");
    setFileName(null);
    setParseError(null);
    setHeaders([]);
    setCsvRows([]);
    setJobId(null);
    setJob(null);
    setRunError(null);
    setStarting(false);
  }

  const startJob = useCallback(async () => {
    setRunError(null);
    setStarting(true);
    try {
      const { job_id, total } = await api.bulkScore(valid, fileName ?? null);
      setJobId(job_id);
      setJob({ status: "queued", processed: 0, total, results: [] });
      setStage("running");
    } catch (err) {
      setRunError(errorDetail(err) ?? "Couldn't start the bulk job.");
    } finally {
      setStarting(false);
    }
  }, [valid, fileName]);

  // Fetch the job once and reflect it into state (job, error, done->results).
  // Shared by the automatic poll and the manual "Retry" button so the button
  // actually updates the UI instead of firing a throwaway request.
  const pollOnce = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await api.bulkJob(jobId);
      setJob(data);
      setRunError(null);
      if (data.status === "done") {
        if (pollRef.current) clearInterval(pollRef.current);
        setStage("results");
      }
    } catch (err) {
      setRunError(errorDetail(err) ?? "Lost contact with the bulk job.");
    }
  }, [jobId]);

  // Poll the job until done. Errors here are surfaced but don't stop polling
  // (a transient network blip shouldn't abandon an in-progress job).
  useEffect(() => {
    if (stage !== "running" || !jobId) return;
    let cancelled = false;

    async function tick() {
      try {
        const data = await api.bulkJob(jobId as string);
        if (cancelled) return;
        setJob(data);
        setRunError(null);
        if (data.status === "done") {
          if (pollRef.current) clearInterval(pollRef.current);
          setStage("results");
        }
      } catch (err) {
        if (cancelled) return;
        setRunError(errorDetail(err) ?? "Lost contact with the bulk job.");
      }
    }

    tick(); // fire immediately, then on the interval
    pollRef.current = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [stage, jobId]);

  function downloadCsv() {
    if (!job) return;
    const blob = new Blob([bulkResultsToCsv(job.results)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = bulkResultsFilename();
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const bandCounts = useMemo(() => {
    const counts: Record<Band, number> = { Clear: 0, Doubtful: 0, Suspect: 0, Unassessed: 0 };
    let errors = 0;
    for (const r of job?.results ?? []) {
      if (r.band) counts[r.band] += 1;
      if (r.error) errors += 1;
    }
    return { counts, errors };
  }, [job]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Bulk upload"
        description="Score a batch of field-visit photos from a LeadSquared export — mapped to the agent and opportunity, and fed straight into Analytics and Review."
      />

      {stage === "upload" && (
        <UploadStep fileName={fileName} parseError={parseError} onFile={handleFile} />
      )}

      {stage === "map" && (
        <MapStep
          headers={headers}
          mapping={mapping}
          onMappingChange={persistMapping}
          rows={csvRows}
          valid={valid}
          skipped={skipped}
          onBack={resetAll}
          onRun={startJob}
          starting={starting}
          runError={runError}
        />
      )}

      {stage === "running" && (
        <RunningStep job={job} runError={runError} onRetryJob={pollOnce} />
      )}

      {stage === "results" && job && (
        <ResultsStep job={job} bandCounts={bandCounts} onExport={downloadCsv} onStartOver={resetAll} />
      )}
    </div>
  );
}

function UploadStep({
  fileName,
  parseError,
  onFile,
}: {
  fileName: string | null;
  parseError: string | null;
  onFile: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-3">
      <EmptyState
        icon={UploadCloud}
        title="Upload the LSQ export CSV"
        what="Bulk upload scores a batch of field-visit photos at once, attributed to the agent and opportunity. Nothing has been uploaded yet."
        why="A leads/activities export with an image URL column and identifier columns (Agent ID, Opportunity ID). Images are fetched and scored server-side and are never stored."
      />
      <div className="flex flex-col items-center gap-2">
        {parseError && (
          <p className="flex items-center gap-1.5 text-caption text-verdict-suspect-fg">
            <AlertCircle size={13} />
            {parseError}
          </p>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
            e.target.value = ""; // allow re-selecting the same file name
          }}
        />
        <Button variant="primary" onClick={() => inputRef.current?.click()}>
          <UploadCloud size={16} />
          Choose CSV file
        </Button>
        {fileName && <p className="text-caption text-text-muted">Last file: {fileName}</p>}
      </div>
    </div>
  );
}

function MapStep({
  headers,
  mapping,
  onMappingChange,
  rows,
  valid,
  skipped,
  onBack,
  onRun,
  starting,
  runError,
}: {
  headers: string[];
  mapping: ColumnMapping;
  onMappingChange: (m: ColumnMapping) => void;
  rows: Record<string, string>[];
  valid: { image_url: string; rep_id: string | null; opportunity_id: string | null }[];
  skipped: number;
  onBack: () => void;
  onRun: () => void;
  starting: boolean;
  runError: string | null;
}) {
  const preview = rows.slice(0, 10);

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Map columns" subtitle="Match your export's columns to what ProofLens needs." />
        <div className="grid gap-4 p-5 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-muted">Image URL (required)</span>
            <select
              className="h-10 rounded-md border border-border-strong bg-surface px-3 text-body-sm text-text"
              value={mapping.imageCol}
              onChange={(e) => onMappingChange({ ...mapping, imageCol: e.target.value })}
            >
              <option value="" disabled>
                Select a column
              </option>
              {headers.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-muted">Agent / rep ID (optional)</span>
            <select
              className="h-10 rounded-md border border-border-strong bg-surface px-3 text-body-sm text-text"
              value={mapping.repIdCol ?? NONE}
              onChange={(e) =>
                onMappingChange({
                  ...mapping,
                  repIdCol: e.target.value === NONE ? undefined : e.target.value,
                })
              }
            >
              <option value={NONE}>None</option>
              {headers.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-muted">Opportunity ID (optional)</span>
            <select
              className="h-10 rounded-md border border-border-strong bg-surface px-3 text-body-sm text-text"
              value={mapping.opportunityIdCol ?? NONE}
              onChange={(e) =>
                onMappingChange({
                  ...mapping,
                  opportunityIdCol: e.target.value === NONE ? undefined : e.target.value,
                })
              }
            >
              <option value={NONE}>None</option>
              {headers.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Preview"
          subtitle={`${formatCount(valid.length)} rows ready · ${formatCount(skipped)} skipped (no image)`}
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-body-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">Image URL</th>
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">Rep</th>
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">
                  Opportunity
                </th>
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => {
                const img = mapping.imageCol ? row[mapping.imageCol] : "";
                const rep = mapping.repIdCol ? row[mapping.repIdCol] : "";
                const opp = mapping.opportunityIdCol ? row[mapping.opportunityIdCol] : "";
                const hasImage = img && img.trim().length > 0;
                return (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className={cn("px-4 py-2.5", !hasImage && "text-verdict-suspect-fg")}>
                      {hasImage ? truncateUrl(img) : "missing — will be skipped"}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums text-text-secondary">{rep || "—"}</td>
                    <td className="px-4 py-2.5 tabular-nums text-text-secondary">{opp || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {runError && (
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <AlertCircle size={18} className="mt-0.5 text-verdict-suspect-fg" />
            <div>
              <p className="text-body-sm font-medium text-text">Couldn&apos;t start the job</p>
              <p className="mt-1 text-caption text-text-secondary">{runError}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          disabled={!mapping.imageCol || valid.length === 0 || starting}
          onClick={onRun}
        >
          {starting ? "Starting…" : `Score ${formatCount(valid.length)} photos`}
        </Button>
        <Button variant="ghost" onClick={onBack} disabled={starting}>
          <RotateCcw size={15} />
          Choose a different file
        </Button>
      </div>
    </div>
  );
}

function RunningStep({
  job,
  runError,
  onRetryJob,
}: {
  job: BulkJob | null;
  runError: string | null;
  onRetryJob: () => void;
}) {
  const total = job?.total ?? 0;
  const processed = job?.processed ?? 0;
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <Card className="p-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <p className="text-body-sm font-medium text-text">
            Scored {formatCount(processed)} of {formatCount(total)}
          </p>
          <p className="text-caption text-text-muted">{job?.status ?? "queued"}</p>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
        {runError && (
          <div className="flex items-start gap-3 rounded-md border border-border bg-surface-2 p-3">
            <AlertCircle size={16} className="mt-0.5 text-verdict-suspect-fg" />
            <div className="flex-1">
              <p className="text-body-sm text-text-secondary">{runError}</p>
              <p className="mt-1 text-caption text-text-muted">
                The job keeps running on the server — this only affects the progress view.
              </p>
            </div>
            <Button variant="secondary" onClick={onRetryJob}>
              <RotateCcw size={15} />
              Retry
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

function ResultsStep({
  job,
  bandCounts,
  onExport,
  onStartOver,
}: {
  job: BulkJob;
  bandCounts: { counts: Record<Band, number>; errors: number };
  onExport: () => void;
  onStartOver: () => void;
}) {
  return (
    <div className="space-y-5">
      <Card className="flex flex-wrap items-center gap-6 p-5">
        <div className="flex items-center gap-2 text-body-sm text-text-secondary">
          <CheckCircle2 size={16} className="text-verdict-clear-fg" />
          {formatCount(job.total)} photos scored
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {(["Clear", "Doubtful", "Suspect"] as Band[]).map((band) => (
            <div key={band} className="flex items-center gap-2">
              <VerdictBadge band={band} size="sm" />
              <span className="tabular-nums text-body-sm text-text">{formatCount(bandCounts.counts[band])}</span>
            </div>
          ))}
          {bandCounts.errors > 0 && (
            <div className="flex items-center gap-1.5 text-body-sm text-text-secondary">
              <AlertCircle size={14} className="text-verdict-suspect-fg" />
              <span className="tabular-nums">{formatCount(bandCounts.errors)}</span> errors
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Results"
          action={
            <Button variant="secondary" onClick={onExport}>
              <Download size={15} />
              Export results CSV
            </Button>
          }
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-body-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">Image</th>
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">Rep</th>
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">
                  Opportunity
                </th>
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">Verdict</th>
                <th className="px-4 py-2.5 text-right text-caption font-medium text-text-muted">Score</th>
                <th className="px-4 py-2.5 text-left text-caption font-medium text-text-muted">Reason</th>
              </tr>
            </thead>
            <tbody>
              {job.results.map((r, i) => (
                <ResultRow key={i} row={r} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-4">
        <Link
          href="/analytics"
          className="inline-flex items-center gap-1.5 text-body-sm font-medium text-text-secondary hover:text-text"
        >
          See them in Analytics
          <ArrowRight size={14} />
        </Link>
        <Button variant="ghost" onClick={onStartOver}>
          <RotateCcw size={15} />
          Upload another batch
        </Button>
      </div>
    </div>
  );
}

function ResultRow({ row }: { row: BulkResultItem }) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-2.5">
        {row.image_url ? (
          <a
            href={row.image_url}
            target="_blank"
            rel="noreferrer"
            className="text-text-secondary underline decoration-border-strong hover:text-text"
          >
            {truncateUrl(row.image_url)}
          </a>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-2.5 tabular-nums text-text-secondary">{row.rep_id ?? "—"}</td>
      <td className="px-4 py-2.5 tabular-nums text-text-secondary">{row.opportunity_id ?? "—"}</td>
      <td className="px-4 py-2.5">
        {row.band ? (
          <VerdictBadge band={row.band} size="sm" />
        ) : (
          <span className="text-caption text-text-muted">—</span>
        )}
      </td>
      <td className="px-4 py-2.5 text-right tabular-nums text-text">
        {row.score != null ? Math.round(row.score) : "—"}
      </td>
      <td className="px-4 py-2.5 text-text-secondary">
        {row.error ? (
          <span className="flex items-center gap-1.5 text-verdict-suspect-fg">
            <AlertCircle size={13} className="shrink-0" />
            {row.error}
          </span>
        ) : (
          row.reason_code ?? "—"
        )}
      </td>
    </tr>
  );
}
