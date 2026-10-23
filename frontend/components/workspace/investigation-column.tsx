"use client";

import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, Microscope } from "lucide-react";
import { DuckMascot, type DuckMood } from "@/components/duck/duck-mascot";
import { TraceItem } from "@/components/workspace/trace-item";
import { HypothesisCard } from "@/components/workspace/hypothesis-card";
import { DiffViewer } from "@/components/workspace/diff-viewer";
import { FixDecision } from "@/components/workspace/fix-decision";
import { ResolvedCard } from "@/components/workspace/resolved-card";
import type { ToolCallEvent } from "@/lib/events";
import type { SessionPhase } from "@/lib/events";
import type { HypothesisOut, FixOut } from "@/lib/api";
import { cn, latestFixBatch } from "@/lib/utils";

interface InvestigationColumnProps {
  phase: SessionPhase;
  busy: boolean;
  trace: ToolCallEvent[];
  hypotheses: HypothesisOut[];
  fixes: FixOut[];
  repoId: string;
  onAccept: () => void;
  onReject: (feedback?: string) => void;
  decisionBusy: boolean;
  resolutionSummary: string | null;
  rootCause: string | null;
  tags: string[];
  soundEnabled: boolean;
}

function moodFor(phase: SessionPhase, busy: boolean): DuckMood {
  if (phase === "resolved") return "resolved";
  if (busy) return "thinking";
  if (phase === "hypothesis" || phase === "fix_proposed") return "hypothesis";
  if (phase === "clarifying") return "listening";
  if (phase === "investigating") return "investigating";
  return "idle";
}

export function InvestigationColumn({
  phase,
  busy,
  trace,
  hypotheses,
  fixes,
  repoId,
  onAccept,
  onReject,
  decisionBusy,
  resolutionSummary,
  rootCause,
  tags,
  soundEnabled,
}: InvestigationColumnProps) {
  const [collapsed, setCollapsed] = useState(false);
  const latestHypothesis = hypotheses[hypotheses.length - 1];
  const currentBatch = latestFixBatch(fixes);
  const awaitingDecision = phase === "fix_proposed" && currentBatch.every((f) => f.accepted === null);

  return (
    <div className="flex h-full min-h-0 flex-col border-t-2 border-ink lg:border-t-0 lg:border-l-2">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center justify-between gap-2 border-b-2 border-ink/10 px-4 py-3 lg:cursor-default lg:pointer-events-none"
      >
        <div className="flex items-center gap-2 font-heading text-sm font-bold">
          <Microscope className="size-4 text-beak" aria-hidden />
          Duck&apos;s investigation
        </div>
        <span className="lg:hidden">{collapsed ? <ChevronDown className="size-4" aria-hidden /> : <ChevronUp className="size-4" aria-hidden />}</span>
      </button>

      <div className={cn(collapsed ? "hidden" : "block", "min-h-0 flex-1 overflow-y-auto lg:block")}>
        <div className="flex flex-col gap-4 p-4">
          <div className="flex justify-center py-2">
            <DuckMascot mood={moodFor(phase, busy)} size={64} />
          </div>

          {trace.length > 0 && (
            <div className="flex flex-col gap-0.5">
              <AnimatePresence initial={false}>
                {trace.map((event, i) => (
                  <TraceItem key={i} event={event} />
                ))}
              </AnimatePresence>
            </div>
          )}

          {latestHypothesis && <HypothesisCard hypothesis={latestHypothesis} repoId={repoId} />}

          {currentBatch.length > 0 && (
            <div className="flex flex-col gap-3">
              {currentBatch.map((fix) => (
                <DiffViewer key={fix.id} filePath={fix.file_path} diffText={fix.diff_text} />
              ))}
              {currentBatch[0]?.explanation && <p className="text-sm text-ink/80">{currentBatch[0].explanation}</p>}
              {awaitingDecision && <FixDecision onAccept={onAccept} onReject={onReject} busy={decisionBusy} />}
            </div>
          )}

          {phase === "resolved" && (
            <ResolvedCard resolutionSummary={resolutionSummary} rootCause={rootCause} tags={tags} soundEnabled={soundEnabled} />
          )}

          {trace.length === 0 && hypotheses.length === 0 && fixes.length === 0 && (
            <p className="text-center text-sm text-muted-foreground">Duck&apos;s findings will appear here as it reads your code.</p>
          )}
        </div>
      </div>
    </div>
  );
}
