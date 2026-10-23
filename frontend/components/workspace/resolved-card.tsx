"use client";

import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Home, PartyPopper, RotateCcw, Tag } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { playQuack } from "@/lib/quack";

interface ResolvedCardProps {
  resolutionSummary: string | null;
  rootCause: string | null;
  tags: string[];
  soundEnabled: boolean;
}

export function ResolvedCard({ resolutionSummary, rootCause, tags, soundEnabled }: ResolvedCardProps) {
  useEffect(() => {
    if (soundEnabled) playQuack();
    // only on mount — this card only renders once the session is resolved
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center gap-3 rounded-xl border-2 border-ink bg-duck px-5 py-6 text-center shadow-brutal-lg"
    >
      <DuckMascot mood="resolved" size={72} />
      <div className="flex items-center gap-1.5 font-heading text-xl font-extrabold">
        <PartyPopper className="size-5" aria-hidden />
        Resolved!
      </div>
      {rootCause && (
        <p className="text-sm font-semibold">
          <span className="text-ink/60">Root cause: </span>
          {rootCause}
        </p>
      )}
      {resolutionSummary && <p className="text-sm text-ink/80">{resolutionSummary}</p>}
      {tags.length > 0 && (
        <div className="flex flex-wrap justify-center gap-1.5 pt-1">
          {tags.map((tag) => (
            <span key={tag} className="inline-flex items-center gap-1 rounded-full border-2 border-ink bg-paper px-2 py-0.5 text-xs font-bold">
              <Tag className="size-3" aria-hidden />
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
        <Link
          href="/#try-a-bug"
          className="press-down inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-ink px-3.5 py-1.5 text-sm font-bold text-cream shadow-brutal-sm"
        >
          <RotateCcw className="size-3.5" aria-hidden />
          Try another bug
        </Link>
        <Link
          href="/"
          className="press-down inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-paper px-3.5 py-1.5 text-sm font-bold shadow-brutal-sm"
        >
          <Home className="size-3.5" aria-hidden />
          Back to home
        </Link>
      </div>
    </motion.div>
  );
}
