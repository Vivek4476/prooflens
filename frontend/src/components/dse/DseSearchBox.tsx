"use client";

import { Search, User } from "lucide-react";
import { useState } from "react";

import { useDseSearch } from "@/lib/api/hooks";
import { shapeSearchResults } from "@/lib/dse/scorecard";
import { cn } from "@/lib/utils";

export function DseSearchBox({
  onSelect,
  autoFocus,
}: {
  onSelect: (agentId: string) => void;
  autoFocus?: boolean;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const { data, isFetching, isError } = useDseSearch(q, open);
  const results = shapeSearchResults(data?.results ?? []);

  return (
    <div className="relative">
      <div className="relative">
        <Search
          size={16}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
        />
        <input
          value={q}
          autoFocus={autoFocus}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Delay so a click on a result registers before the list unmounts.
            setTimeout(() => setOpen(false), 150);
          }}
          placeholder="Search a DSE by name or ID"
          aria-label="Search a DSE by name or ID"
          className="h-11 w-full rounded-md border border-border bg-surface pl-9 pr-3 text-body text-text placeholder:text-text-muted focus-visible:border-border-strong"
        />
      </div>

      {open && (
        <div
          className={cn(
            "absolute left-0 right-0 top-full z-10 mt-1.5 max-h-80 overflow-y-auto rounded-md border border-border bg-surface shadow-[var(--shadow-2)]",
          )}
        >
          {isError ? (
            <p className="px-3 py-3 text-body-sm text-text-muted">Couldn&apos;t search DSEs — try again.</p>
          ) : isFetching && results.length === 0 ? (
            <p className="px-3 py-3 text-body-sm text-text-muted">Searching…</p>
          ) : results.length === 0 ? (
            <p className="px-3 py-3 text-body-sm text-text-muted">
              {q.trim() ? "No DSE matches that name or ID." : "Start typing a name or ID, or pick a recent DSE."}
            </p>
          ) : (
            <ul>
              {results.map((r) => (
                <li key={r.agent_id}>
                  <button
                    type="button"
                    // onMouseDown fires before the input's onBlur, so the click registers.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setOpen(false);
                      onSelect(r.agent_id);
                    }}
                    className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-2"
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface-2 text-text-muted">
                      <User size={15} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-body-sm text-text">{r.name}</span>
                      <span className="block truncate text-caption text-text-muted">
                        {r.agent_id}
                        {r.branch ? ` · ${r.branch}` : ""}
                        {r.sm ? ` · SM ${r.sm}` : ""}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
