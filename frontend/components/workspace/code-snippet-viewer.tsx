"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import { Loader2, X } from "lucide-react";
import { getFileContent, ApiError } from "@/lib/api";

const CONTEXT_LINES = 7;

interface CodeSnippetViewerProps {
  repoId: string;
  filePath: string;
  lineNumber: number;
  onClose: () => void;
}

export function CodeSnippetViewer({ repoId, filePath, lineNumber, onClose }: CodeSnippetViewerProps) {
  const [lines, setLines] = useState<string[] | null>(null);
  const [startLine, setStartLine] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFileContent(repoId, filePath)
      .then((result) => {
        if (cancelled) return;
        const all = result.content.split("\n");
        const start = Math.max(0, lineNumber - 1 - CONTEXT_LINES);
        const end = Math.min(all.length, lineNumber + CONTEXT_LINES);
        setLines(all.slice(start, end));
        setStartLine(start + 1);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load that file.");
      });
    return () => {
      cancelled = true;
    };
  }, [repoId, filePath, lineNumber]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border-2 border-ink bg-paper shadow-brutal-lg"
      >
        <div className="flex items-center justify-between gap-3 border-b-2 border-ink bg-ink px-4 py-2.5 text-cream">
          <span className="truncate font-mono text-sm font-semibold">{filePath}:{lineNumber}</span>
          <button type="button" onClick={onClose} aria-label="Close" className="press-down shrink-0 rounded-md p-0.5">
            <X className="size-4" aria-hidden />
          </button>
        </div>

        <div className="overflow-auto p-2">
          {error && <p className="p-4 text-sm font-semibold text-destructive">{error}</p>}
          {!error && !lines && (
            <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Loading snippet&hellip;
            </div>
          )}
          {lines && (
            <pre className="font-mono text-xs leading-relaxed sm:text-sm">
              {lines.map((line, i) => {
                const num = startLine + i;
                const isTarget = num === lineNumber;
                return (
                  <div key={num} className={isTarget ? "bg-duck-soft" : undefined}>
                    <span className="inline-block w-10 shrink-0 select-none text-right text-muted-foreground">{num}</span>
                    <span className="pl-3">{line}</span>
                  </div>
                );
              })}
            </pre>
          )}
        </div>
      </motion.div>
    </div>,
    document.body
  );
}
