"use client";

import { AlertCircle, ImageIcon, UploadCloud, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { cn } from "@/lib/utils";

const MAX_FILE_BYTES = 15 * 1024 * 1024; // 15 MB

export function ImageUploader({
  preview,
  fileName,
  onSelect,
  onClear,
  disabled,
}: {
  preview: string | null;
  fileName: string | null;
  onSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        setError("That's not an image — please choose a JPG or PNG.");
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        setError("Image is too large (max 15 MB).");
        return;
      }
      setError(null);
      onSelect(file);
    },
    [onSelect],
  );

  if (preview) {
    return (
      <div className="card overflow-hidden">
        <div className="relative bg-surface-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt={fileName ?? "Selected image"} className="mx-auto max-h-[360px] w-auto object-contain" />
          {!disabled && (
            <button
              onClick={onClear}
              className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-surface/90 text-text-secondary shadow-1 backdrop-blur hover:text-text"
              aria-label="Remove image"
            >
              <X size={16} />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2 px-4 py-2.5 text-caption text-text-muted">
          <ImageIcon size={14} />
          <span className="truncate">{fileName}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "flex min-h-[300px] cursor-pointer flex-col items-center justify-center gap-3 rounded-[var(--radius)] border-2 border-dashed bg-surface px-6 py-12 text-center transition-colors",
        dragging ? "border-brand-crimson bg-surface-2" : "border-border-strong hover:bg-surface-2",
      )}
    >
      <div className="grid h-14 w-14 place-items-center rounded-full bg-surface-2 text-text-secondary">
        <UploadCloud size={26} />
      </div>
      <div>
        <p className="text-body font-medium text-text">Drop a photo here, or click to browse</p>
        <p className="mt-1 text-caption text-text-muted">
          JPG or PNG · the image is scored, never stored
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      </div>
      {error && (
        <p role="alert" className="flex items-center gap-1.5 text-caption text-danger">
          <AlertCircle size={13} className="shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}
