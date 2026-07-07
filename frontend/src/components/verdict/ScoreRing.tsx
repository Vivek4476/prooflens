"use client";

import { motion, useReducedMotion } from "framer-motion";

import { BAND_META } from "@/lib/verdict";
import type { Band } from "@/lib/api/types";

/** Animated 0–100 score ring, coloured by band (large number gets the space). */
export function ScoreRing({ score, band, size = 160 }: { score: number; band: Band; size?: number }) {
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = BAND_META[band].ring;
  const reduceMotion = useReducedMotion();
  const finalOffset = c * (1 - pct);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          {...(reduceMotion
            ? { strokeDashoffset: finalOffset }
            : {
                initial: { strokeDashoffset: c },
                animate: { strokeDashoffset: finalOffset },
                transition: { duration: 0.9, ease: "easeOut" },
              })}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="text-display tabular-nums text-text"
          {...(reduceMotion
            ? { animate: { opacity: 1 } }
            : {
                initial: { opacity: 0 },
                animate: { opacity: 1 },
                transition: { delay: 0.2 },
              })}
        >
          {Math.round(score)}
        </motion.span>
        <span className="text-caption text-text-muted">/ 100</span>
      </div>
    </div>
  );
}
