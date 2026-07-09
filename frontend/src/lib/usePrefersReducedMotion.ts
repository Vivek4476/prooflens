"use client";
import { useEffect, useState } from "react";

/**
 * recharts drives its enter/update animations via requestAnimationFrame, not CSS —
 * so the global `prefers-reduced-motion` CSS override in globals.css never reaches
 * them (BRAND.md §11 risk #2). Charts must read this hook directly and set
 * `isAnimationActive={!reducedMotion}` themselves.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
