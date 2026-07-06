"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";

import { SidebarInner } from "./Sidebar";

/**
 * Mobile navigation. The desktop rail is `hidden md:block`; below md this
 * hamburger + slide-over is the ONLY nav (previously there was none).
 */
export function MobileNav() {
  const [open, setOpen] = useState(false);

  // Lock body scroll while the drawer is open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <div className="md:hidden">
      <button
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
              className="fixed inset-0 z-50 cursor-default bg-black/40"
            />
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.22, ease: "easeOut" }}
              className="fixed inset-y-0 left-0 z-50 w-[268px] max-w-[82%] border-r border-border bg-surface shadow-2"
            >
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
                className="absolute right-2 top-3.5 z-10 grid h-8 w-8 place-items-center rounded-md text-text-secondary hover:bg-surface-2 hover:text-text"
              >
                <X size={17} />
              </button>
              <SidebarInner onNavigate={() => setOpen(false)} />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
