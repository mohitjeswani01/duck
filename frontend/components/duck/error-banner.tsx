"use client";

import { motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { cn } from "cn";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
}

/** The only place a user-facing error ever gets rendered. Backend errors are
 * already friendly strings (never raw exceptions) — this just gives them a
 * consistent, visible treatment instead of a toast that's easy to miss. */
export function ErrorBanner({ message, onDismiss, className }: ErrorBannerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-xl border-2 border-ink bg-beak px-4 py-3 text-ink shadow-brutal-sm",
        className
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="flex-1 text-sm font-semibold">{message}</p>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss" className="press-down shrink-0 rounded-md p-0.5">
          <X className="size-4" aria-hidden />
        </button>
      )}
    </motion.div>
  );
}
