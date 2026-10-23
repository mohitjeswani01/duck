"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Lightbulb } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Chip } from "@/components/ui/chip";
import { CodeSnippetViewer } from "@/components/workspace/code-snippet-viewer";
import type { HypothesisOut, EvidenceItem } from "@/lib/api";

export function HypothesisCard({ hypothesis, repoId }: { hypothesis: HypothesisOut; repoId: string }) {
  const [openEvidence, setOpenEvidence] = useState<EvidenceItem | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-3 rounded-xl border-2 border-ink bg-duck px-4 py-3.5 shadow-brutal"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs font-bold tracking-wide text-ink/70 uppercase">
          <Lightbulb className="size-3.5" aria-hidden />
          Hypothesis
        </div>
        <Badge variant={hypothesis.confidence}>{hypothesis.confidence} confidence</Badge>
      </div>

      <p className="text-sm font-semibold sm:text-base">{hypothesis.description}</p>

      {hypothesis.evidence && hypothesis.evidence.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {hypothesis.evidence.map((e, i) => (
            <Chip key={i} onClick={() => setOpenEvidence(e)} title={e.note}>
              <span className="font-mono text-xs">
                {e.file_path}:{e.line_number}
              </span>
            </Chip>
          ))}
        </div>
      )}

      {openEvidence && (
        <CodeSnippetViewer
          repoId={repoId}
          filePath={openEvidence.file_path}
          lineNumber={openEvidence.line_number}
          onClose={() => setOpenEvidence(null)}
        />
      )}
    </motion.div>
  );
}
