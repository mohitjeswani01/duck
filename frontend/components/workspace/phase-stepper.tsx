"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";
import { cn } from "cn";
import type { SessionPhase } from "@/lib/events";
import type { MessageOut } from "@/lib/api";

const STEPS: { phase: SessionPhase; label: string }[] = [
  { phase: "investigating", label: "Investigating" },
  { phase: "clarifying", label: "Clarifying" },
  { phase: "hypothesis", label: "Hypothesis" },
  { phase: "fix_proposed", label: "Fix" },
  { phase: "resolved", label: "Resolved" },
];

// Only "clarifying" is ever actually skippable — Duck can form a hypothesis
// without asking a clarifying question. Every other step, once passed, was
// necessarily visited.
const SKIPPABLE_PHASE: SessionPhase = "clarifying";

function stepIndex(phase: SessionPhase): number {
  if (phase === "listening") return 0;
  const idx = STEPS.findIndex((s) => s.phase === phase);
  return idx === -1 ? 0 : idx;
}

export function PhaseStepper({ phase, messages = [] }: { phase: SessionPhase; messages?: MessageOut[] }) {
  const current = stepIndex(phase);
  const clarifyingVisited = messages.some((m) => m.phase_at_time === "clarifying");

  return (
    <ol className="flex items-center gap-0.5 sm:gap-2">
      {STEPS.map((step, i) => {
        const isActive = i === current;
        const isSkipped = step.phase === SKIPPABLE_PHASE && !isActive && i < current && !clarifyingVisited;
        const isDone = i < current && !isSkipped;
        return (
          <li key={step.phase} className="flex items-center gap-0.5 sm:gap-2">
            <div
              className={cn(
                "relative flex items-center justify-center gap-1.5 rounded-full border-2 border-ink px-1.5 py-1 text-xs font-bold whitespace-nowrap sm:px-2.5 sm:text-sm",
                isActive && "bg-duck shadow-brutal-sm",
                isDone && !isActive && "bg-duck-soft",
                isSkipped && "border-ink/25 bg-transparent text-muted-foreground/60",
                !isActive && !isDone && !isSkipped && "bg-paper text-muted-foreground"
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
              {/* Mobile: active step keeps its label, others collapse to a tiny icon/number so all five steps fit without scrolling. */}
              <span className="sm:hidden">
                {isActive ? step.label : isDone ? <Check className="size-3" aria-hidden /> : isSkipped ? <X className="size-3" aria-hidden /> : i + 1}
              </span>
              <span className={cn("hidden sm:inline", isSkipped && "line-through")}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && <div className={cn("h-0.5 w-2 sm:w-5", isDone ? "bg-ink" : "bg-ink/20")} />}
          </li>
        );
      })}
    </ol>
  );
}
