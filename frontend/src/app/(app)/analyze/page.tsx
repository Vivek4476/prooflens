"use client";

import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, Clock, RotateCcw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { ImageUploader } from "@/components/analyze/ImageUploader";
import { PipelineStepper, type StageState } from "@/components/analyze/PipelineStepper";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ChecksList } from "@/components/verdict/ChecksList";
import { ScoreRing } from "@/components/verdict/ScoreRing";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { api } from "@/lib/api/client";
import type { ScoreResponse } from "@/lib/api/types";
import { formatMs } from "@/lib/utils";
import { PIPELINE_STAGES, bandState, checkState } from "@/lib/verdict";

const REVEAL_MS = 260;

export default function AnalyzePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(-1); // -1 => not revealing yet
  // Live AI is the default so demos show a real model judgement, not the stub.
  const [model, setModel] = useState<"stub" | "openrouter">("openrouter");

  const mutation = useMutation({
    mutationFn: (f: File) => api.score(f, { backend: model }),
    onSuccess: () => setRevealed(-1),
  });
  const result = mutation.data;

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

  // Sequentially reveal the stepper against the REAL checks[] once we have them.
  const revealTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!result) return;
    setRevealed(-1);
    revealTimer.current = setInterval(() => {
      setRevealed((r) => {
        if (r >= PIPELINE_STAGES.length - 1) {
          if (revealTimer.current) clearInterval(revealTimer.current);
          return r;
        }
        return r + 1;
      });
    }, REVEAL_MS);
    return () => {
      if (revealTimer.current) clearInterval(revealTimer.current);
    };
  }, [result]);

  const realStates = useMemo(() => {
    if (!result) return [];
    return PIPELINE_STAGES.map((stage) => {
      if (stage.key === "fusion") return bandState(result.band);
      const c = result.checks.find((x) => x.name === stage.key);
      return c ? checkState(c) : "skip";
    });
  }, [result]);

  const stepperStates: StageState[] = useMemo(() => {
    if (mutation.isPending) {
      // In-flight: the content (vision) call is the real bottleneck.
      return PIPELINE_STAGES.map((s) => (s.key === "content" ? "active" : "pending"));
    }
    if (result) {
      return PIPELINE_STAGES.map((_, i) =>
        i <= revealed ? realStates[i] : i === revealed + 1 ? "active" : "pending",
      );
    }
    return PIPELINE_STAGES.map(() => "pending");
  }, [mutation.isPending, result, revealed, realStates]);

  const revealing = !!result && revealed < PIPELINE_STAGES.length - 1;
  const showResult = !!result && !revealing;
  const showStepper = mutation.isPending || revealing;

  function reset() {
    mutation.reset();
    setFile(null);
    setRevealed(-1);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyze a photo"
        description="Score a photo against the live pipeline and see exactly why — band first, then the evidence behind it."
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
          <div>
            <div className="mb-2 flex items-center gap-1 rounded-md border border-border bg-surface p-1">
              {(
                [
                  { key: "stub", label: "Demo model", hint: "instant" },
                  { key: "openrouter", label: "Live AI", hint: "real · slower" },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setModel(opt.key)}
                  disabled={mutation.isPending}
                  aria-pressed={model === opt.key}
                  className={
                    "flex-1 rounded px-3 py-1.5 text-caption font-medium transition-colors " +
                    (model === opt.key
                      ? "bg-surface-2 text-text"
                      : "text-text-muted hover:text-text-secondary")
                  }
                >
                  {opt.label} <span className="text-text-muted">· {opt.hint}</span>
                </button>
              ))}
            </div>
          </div>
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
            {(file || result) && (
              <Button variant="ghost" onClick={reset} disabled={mutation.isPending}>
                <RotateCcw size={15} />
                Reset
              </Button>
            )}
          </div>
        </div>

        {/* Right: stepper / result / empty */}
        <div>
          {mutation.isError && (
            <Card className="p-5">
              <div className="flex items-start gap-3">
                <AlertCircle size={18} className="mt-0.5 text-danger" />
                <div className="flex-1">
                  <p className="text-body-sm font-medium text-text">Could not score the image</p>
                  <p className="mt-1 text-caption text-text-secondary">
                    The scoring service did not respond. ProofLens never blocks an upload — you
                    can retry.
                  </p>
                  <Button variant="secondary" className="mt-3" onClick={() => file && mutation.mutate(file)}>
                    <RotateCcw size={15} />
                    Retry
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {showStepper && (
            <Card className="p-4">
              <CardHeader title="Running the pipeline" subtitle="Cheap checks first; the vision call last." />
              <div className="p-2">
                <PipelineStepper states={stepperStates} />
              </div>
            </Card>
          )}

          {showResult && result && <ResultPanel result={result} />}

          {!showStepper && !showResult && !mutation.isError && (
            <div className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-[var(--radius)] border border-dashed border-border-strong px-6 text-center">
              <p className="text-body-sm text-text-secondary">The verdict will appear here.</p>
              <p className="mt-1 text-caption text-text-muted">
                Band and score first, then the full evidence breakdown.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Explainability spans full width under the fold */}
      {showResult && result && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          <Card>
            <CardHeader
              title="Why this verdict"
              subtitle="Every check the pipeline ran — what was found and how confident."
            />
            <ChecksList checks={result.checks} rubricVersion={result.rubric_version} />
          </Card>
        </motion.div>
      )}
    </div>
  );
}

function ResultPanel({ result }: { result: ScoreResponse }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
    >
      <Card className="p-6">
        {/* Verdict FIRST: band word + colour */}
        <div className="mb-5 flex items-center justify-between">
          <VerdictBadge band={result.band} size="lg" />
          <div className="flex items-center gap-1.5 text-caption text-text-muted">
            <Clock size={13} />
            {formatMs(result.processing_ms)}
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
          <ScoreRing score={result.score} band={result.band} />
          <div className="flex-1">
            {/* Reason string VERBATIM from the backend vocabulary */}
            <p className="text-h2 leading-snug text-text">{result.reason}</p>
            <p className="mt-3 text-caption text-text-muted">
              Scored by{" "}
              <span className="font-medium text-text-secondary">{result.backend}</span>
              {result.backend_is_real ? "" : " (deterministic demo model)"}
            </p>
            {result.backend_note && (
              <p className="mt-2 flex items-start gap-1.5 text-caption text-warn">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />
                {result.backend_note}
              </p>
            )}
            {/* The verdict is persisted — link to its permanent, shareable page. */}
            <Link
              href={`/verdict/${result.result_id}`}
              className="mt-3 inline-flex items-center gap-1 text-caption font-medium text-text-secondary hover:text-text"
            >
              View saved report
              <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
