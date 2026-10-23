"use client";

import { motion } from "framer-motion";
import { cn } from "cn";
import type { SessionPhase } from "@/lib/events";

const STEPS: { phase: SessionPhase; label: string }[] = [
  { phase: "investigating", label: "Investigating" },
  { phase: "clarifying", label: "Clarifying" },
  { phase: "hypothesis", label: "Hypothesis" },
  { phase: "fix_proposed", label: "Fix" },
  { phase: "resolved", label: "Resolved" },
];

function stepIndex(phase: SessionPhase): number {
  if (phase === "listening") return 0;
  const idx = STEPS.findIndex((s) => s.phase === phase);
  return idx === -1 ? 0 : idx;
}

export function PhaseStepper({ phase }: { phase: SessionPhase }) {
  const current = stepIndex(phase);

  return (
    <ol className="flex items-center gap-1 overflow-x-auto sm:gap-2">
      {STEPS.map((step, i) => {
        const isActive = i === current;
        const isDone = i < current;
        return (
          <li key={step.phase} className="flex items-center gap-1 sm:gap-2">
            <div
              className={cn(
                "relative flex items-center gap-1.5 rounded-full border-2 border-ink px-2.5 py-1 text-xs font-bold whitespace-nowrap sm:text-sm",
                isActive && "bg-duck shadow-brutal-sm",
                isDone && !isActive && "bg-duck-soft",
                !isActive && !isDone && "bg-paper text-muted-foreground"
              )}
            >
              {isActive && (
                <motion.span
                  layoutId="phase-pulse"
                  className="absolute inset-0 rounded-full bg-duck"
                  style={{ zIndex: -1 }}
                  animate={{ opacity: [0.6, 1, 0.6] }}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                />
              )}
              <span>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && <div className={cn("h-0.5 w-3 sm:w-5", isDone ? "bg-ink" : "bg-ink/20")} />}
          </li>
        );
      })}
    </ol>
  );
}
