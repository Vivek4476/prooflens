"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertCircle, RotateCcw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ImageUploader } from "@/components/analyze/ImageUploader";
import { ScoreStage } from "@/components/analyze/ScoreStage";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api/client";

/** Pull the backend's exact reason (FastAPI `detail`) out of an axios error, so
 * operators see e.g. "Live AI (openrouter) is unavailable: … 429 …" not a generic
 * message. Falls back to the transport error text. */
function errorDetail(err: unknown): string | null {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  return e?.message ?? null;
}

/** Is this failure a transient one worth auto-retrying? The free-tier API can
 * cold-start (~20-30s), returning a 502 or a network timeout on the first hit;
 * a retry a few seconds later succeeds. Genuine 4xx (bad request) are not. */
function isTransient(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  if (status == null) return true; // no response => network error / timeout
  return [408, 425, 429, 500, 502, 503, 504].includes(status);
}

export default function AnalyzePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const mutation = useMutation({
    // No backend param — the server always uses its configured Live AI provider
    // (VISION_BACKEND, e.g. groq). There is no demo/stub path in the UI.
    mutationFn: (f: File) => api.score(f),
    // Survive a free-tier cold start: when the instance is asleep, Render returns
    // a 502 WITHOUT CORS headers, which the browser reports as "Network Error".
    // Cold starts observed at 40s+, so retry transient failures across ~50s so the
    // score self-heals as "Scoring…" once the instance finishes waking.
    retry: (failureCount, error) => failureCount < 8 && isTransient(error),
    retryDelay: (attempt) => Math.min(8_000, 2_000 + 2_000 * attempt), // 2,4,6,8,8…
  });

  // Pre-warm the free-tier API on mount so the first score isn't a cold start —
  // by the time the user uploads and clicks Analyze, the instance is awake.
  useEffect(() => {
    api.ready().catch(() => {});
  }, []);

  // Object URL lifecycle for the preview.
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function reset() {
    mutation.reset();
    setFile(null);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyze a photo"
        description="Score a photo against the live pipeline and see exactly why — band first, then the evidence behind it."
        actions={
          <Link
            href="/present"
            className="inline-flex h-10 items-center gap-2 rounded-md border border-border-strong bg-surface px-4 text-body-sm font-medium text-text transition-colors hover:bg-surface-2"
          >
            Present mode
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: image + action */}
        <div className="space-y-4">
          <ImageUploader
            preview={preview}
            fileName={file?.name ?? null}
            onSelect={setFile}
            onClear={reset}
            disabled={mutation.isPending}
          />
          <p className="flex items-center gap-1.5 text-caption text-text-muted">
            <Sparkles size={13} className="text-accent" />
            Scored by Live AI — a real vision model.
          </p>
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              disabled={!file || mutation.isPending}
              onClick={() => file && mutation.mutate(file)}
              className="flex-1"
            >
              <Sparkles size={16} />
              {mutation.isPending ? "Scoring…" : "Analyze"}
            </Button>
            {(file || mutation.data) && (
              <Button variant="ghost" onClick={reset} disabled={mutation.isPending}>
                <RotateCcw size={15} />
                Reset
              </Button>
            )}
          </div>
        </div>

        {/* Right: stepper / result / empty */}
        <div>
          {mutation.isError ? (
            <Card className="p-5">
              <div className="flex items-start gap-3">
                <AlertCircle size={18} className="mt-0.5 text-danger" />
                <div className="flex-1">
                  <p className="text-body-sm font-medium text-text">
                    Live AI is currently unavailable
                  </p>
                  <p className="mt-1 text-caption text-text-secondary">
                    Please check the AI provider configuration or try again later. ProofLens never blocks an upload — you can retry.
                  </p>
                  {errorDetail(mutation.error) && (
                    <p className="mt-2 break-words rounded bg-surface-2 px-2 py-1.5 font-mono text-caption text-text-muted">
                      {errorDetail(mutation.error)}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => file && mutation.mutate(file)}
                    >
                      <RotateCcw size={15} />
                      Retry
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ) : (
            <ScoreStage result={mutation.data ?? null} pending={mutation.isPending} />
          )}

          {!mutation.data && !mutation.isPending && !mutation.isError && (
            <div className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-[var(--radius)] border border-dashed border-border-strong px-6 text-center">
              <p className="text-body-sm text-text-secondary">The verdict will appear here.</p>
              <p className="mt-1 text-caption text-text-muted">
                Band and score first, then the full evidence breakdown.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
