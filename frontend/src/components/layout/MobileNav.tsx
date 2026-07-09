"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Menu, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { SidebarInner } from "./Sidebar";

/**
 * Mobile navigation. The desktop rail is `hidden md:block`; below md this
 * hamburger + slide-over is the ONLY nav (previously there was none). The
 * drawer also carries search, which is `hidden md:flex` in the desktop Topbar.
 */
export function MobileNav() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Lock body scroll while the drawer is open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Move focus into the drawer on open; restore it to the trigger on close.
  // Skip on mount — only run this in response to an actual open/close
  // transition, never on first render (otherwise the hamburger trigger
  // steals focus from the page on every load, before the user has done
  // anything).
  const mounted = useRef(false);
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    if (open) {
      closeRef.current?.focus();
      return;
    }
    triggerRef.current?.focus();
  }, [open]);

  // Escape to close; Tab / Shift+Tab wrap focus within the drawer.
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      return;
    }
    if (e.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = panel.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="md:hidden">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        className="grid h-9 w-9 place-items-center rounded-md border border-border bg-surface text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
      >
        <Menu size={18} />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
              tabIndex={-1}
              className="fixed inset-0 z-50 cursor-default bg-black/40"
            />
            <motion.div
              ref={panelRef}
              role="dialog"
              aria-modal="true"
              aria-label="Navigation"
              onKeyDown={onKeyDown}
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.22, ease: "easeOut" }}
              className="fixed inset-y-0 left-0 z-50 flex w-[268px] max-w-[82%] flex-col border-r border-border bg-surface shadow-2"
            >
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
                className="absolute right-2 top-3.5 z-10 grid h-8 w-8 place-items-center rounded-md text-text-secondary hover:bg-surface-2 hover:text-text"
              >
                <X size={17} />
              </button>

              <form
                className="border-b border-border p-3 pr-12"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (q.trim()) {
                    router.push(`/history?q=${encodeURIComponent(q.trim())}`);
                    setOpen(false);
                  }
                }}
              >
                <div className="relative">
                  <Search
                    size={15}
                    className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
                  />
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search opportunity or rep ID…"
                    className="h-9 w-full rounded-md border border-border bg-surface pl-8 pr-3 text-body-sm text-text placeholder:text-text-muted focus-visible:border-border-strong"
                    aria-label="Search uploads"
                  />
                </div>
              </form>

              <div className="min-h-0 flex-1">
                <SidebarInner onNavigate={() => setOpen(false)} />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
