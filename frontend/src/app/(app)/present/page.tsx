"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ImageUploader } from "@/components/analyze/ImageUploader";
import { Button } from "@/components/ui/Button";
import { ScoreStage } from "@/components/analyze/ScoreStage";
import { api } from "@/lib/api/client";

const SAMPLES: { label: string; src: string }[] = [
  // Real JPEGs go in frontend/public/samples/. If none exist, this strip renders
  // nothing meaningful — the uploader path still works. See spec §2.F.
];

export default function PresentPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: (f: File) => api.score(f) });

  function pick(f: File) {
    setFile(f); setPreview(URL.createObjectURL(f));
  }
  async function scoreSample(src: string) {
    const blob = await (await fetch(src)).blob();
    const f = new File([blob], src.split("/").pop() || "sample.jpg", { type: blob.type });
    pick(f); mutation.mutate(f);
  }

  return (
    <div className="mx-auto flex min-h-[80dvh] w-full max-w-3xl flex-col items-center justify-center gap-8 py-10 text-center">
      <div>
        <h1 className="text-display text-text">ProofLens</h1>
        <p className="mt-1 text-body text-text-muted">Drop a photo — watch it get scored, live.</p>
      </div>

      {!mutation.data && !mutation.isPending && (
        <div className="w-full max-w-md space-y-4">
          <ImageUploader preview={preview} fileName={file?.name ?? null} onSelect={pick}
            onClear={() => { setFile(null); setPreview(null); }} disabled={mutation.isPending} />
          <Button variant="primary" className="w-full" disabled={!file}
            onClick={() => file && mutation.mutate(file)}>Score it</Button>
          {SAMPLES.length > 0 && (
            <div className="flex justify-center gap-3">
              {SAMPLES.map((s) => (
                <button key={s.src} onClick={() => scoreSample(s.src)}
                  className="overflow-hidden rounded-lg border border-border hover:border-border-strong">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={s.src} alt={s.label} className="h-16 w-16 object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <ScoreStage result={mutation.data ?? null} pending={mutation.isPending} size="stage" />

      {(mutation.data || mutation.isError) && (
        <Button variant="secondary" onClick={() => { mutation.reset(); setFile(null); setPreview(null); }}>
          Score another
        </Button>
      )}
    </div>
  );
}
