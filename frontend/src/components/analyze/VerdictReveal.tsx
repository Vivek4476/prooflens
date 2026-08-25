"use client";

import { motion, useReducedMotion } from "framer-motion";
import { AlertCircle, ArrowRight, Clock } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/verdict/ScoreRing";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { formatMs } from "@/lib/utils";
import type { ScoreResponse } from "@/lib/api/types";

export function VerdictReveal({ result }: { result: ScoreResponse }) {
  const reduce = useReducedMotion();
  const entrance = reduce
    ? {}
    : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.22 } };
  return (
    <motion.div className="outline-none" {...entrance}>
      <Card className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <VerdictBadge band={result.band} size="lg" />
          <div className="flex items-center gap-1.5 text-caption text-text-muted">
            <Clock size={13} />{formatMs(result.processing_ms)}
          </div>
        </div>
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
          <ScoreRing score={result.score} band={result.band} />
          <div className="flex-1">
            <p className="text-h2 leading-snug text-text">{result.reason}</p>
            <motion.p
              className="mt-2 text-body-sm leading-relaxed text-text-secondary"
              {...(reduce ? {} : { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { delay: 0.5 } })}
            >
              {result.copilot_summary ?? result.reason}
            </motion.p>
            <p className="mt-3 text-caption text-text-muted">
              Scored by <span className="font-medium text-text-secondary">{result.backend}</span>
              {result.backend_is_real ? "" : " (deterministic demo model)"}
            </p>
            {result.backend_note && (
              <p className="mt-2 flex items-start gap-1.5 text-caption text-warn">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />{result.backend_note}
              </p>
            )}
            <Link href={`/verdict/${result.result_id}`}
              className="mt-3 inline-flex items-center gap-1 text-caption font-medium text-text-secondary hover:text-text">
              View saved report <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
