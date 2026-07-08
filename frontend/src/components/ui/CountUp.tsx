"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Animated count-up number. Runs a smooth 0 → value animation over `duration`ms
 * using requestAnimationFrame. Respects prefers-reduced-motion (shows final
 * value immediately). Works for integers and single-decimal floats.
 */
export function CountUp({
  value,
  duration = 800,
  decimals = 0,
}: {
  value: number;
  duration?: number;
  decimals?: number;
}) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    // Respect reduced-motion preference
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced) {
      setDisplay(value);
      prevValue.current = value;
      return;
    }

    const start = prevValue.current;
    const delta = value - start;
    const startTime = performance.now();

    function tick(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic for a satisfying deceleration
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(start + delta * eased);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        prevValue.current = value;
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  const formatted =
    decimals > 0 ? display.toFixed(decimals) : Math.round(display).toString();

  return <>{formatted}</>;
}
