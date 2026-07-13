import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          crimson: "var(--brand-crimson)",
          "crimson-hover": "var(--brand-crimson-hover)",
          gold: "var(--brand-gold)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          fg: "var(--accent-fg)",
        },
        verdict: {
          clear: "var(--verdict-clear)",
          doubtful: "var(--verdict-doubtful)",
          suspect: "var(--verdict-suspect)",
          "clear-bg": "var(--verdict-clear-bg)",
          "doubtful-bg": "var(--verdict-doubtful-bg)",
          "suspect-bg": "var(--verdict-suspect-bg)",
          "clear-fg": "var(--verdict-clear-fg)",
          "doubtful-fg": "var(--verdict-doubtful-fg)",
          "suspect-fg": "var(--verdict-suspect-fg)",
          unassessed: "var(--verdict-unassessed)",
          "unassessed-bg": "var(--verdict-unassessed-bg)",
          "unassessed-fg": "var(--verdict-unassessed-fg)",
        },
        canvas: "var(--canvas)",
        surface: {
          DEFAULT: "var(--surface)",
          2: "var(--surface-2)",
          3: "var(--surface-3)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        text: {
          DEFAULT: "var(--text)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        ring: "var(--ring)",
        ok: "var(--ok)",
        warn: "var(--warn)",
        danger: "var(--danger)",
      },
      boxShadow: {
        1: "var(--shadow-1)",
        2: "var(--shadow-2)",
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sm: "var(--radius-sm)",
      },
      fontSize: {
        // 1 display, 2 heading, 2 body, 1 caption
        display: ["2rem", { lineHeight: "2.4rem", letterSpacing: "-0.02em", fontWeight: "600" }],
        h1: ["1.375rem", { lineHeight: "1.75rem", letterSpacing: "-0.01em", fontWeight: "600" }],
        h2: ["1.0625rem", { lineHeight: "1.4rem", fontWeight: "600" }],
        body: ["0.9375rem", { lineHeight: "1.4rem" }],
        "body-sm": ["0.8125rem", { lineHeight: "1.2rem" }],
        caption: ["0.75rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
      },
      transitionDuration: { DEFAULT: "180ms" },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "tooltip-in": {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        "slide-up": "slide-up 200ms ease-out",
        "tooltip-in": "tooltip-in 120ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
