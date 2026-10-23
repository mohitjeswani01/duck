"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { PhaseStepper } from "@/components/workspace/phase-stepper";
import { SoundToggle, useSoundEnabled } from "@/components/workspace/sound-toggle";
import type { SessionPhase } from "@/lib/events";

interface TopBarProps {
  repoOwner?: string;
  repoName?: string;
  githubUrl?: string;
  phase: SessionPhase;
  soundEnabled: boolean;
  onSoundChange: (value: boolean) => void;
}

export function TopBar({ repoOwner, repoName, githubUrl, phase, soundEnabled, onSoundChange }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex flex-col gap-3 border-b-2 border-ink bg-cream/95 px-4 py-3 backdrop-blur-sm sm:px-6">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-2">
          <DuckMascot mood="idle" size={28} />
          <span className="font-heading text-lg font-extrabold">Duck</span>
        </Link>

        {repoOwner && repoName && (
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-paper px-3 py-1 text-xs font-semibold shadow-brutal-sm sm:text-sm"
          >
            <span className="font-mono">{repoOwner}/{repoName}</span>
            <ExternalLink className="size-3" aria-hidden />
          </a>
        )}

        <SoundToggle enabled={soundEnabled} onChange={onSoundChange} />
      </div>

      <PhaseStepper phase={phase} />
    </header>
  );
}

export { useSoundEnabled };
