"use client";

import Link from "next/link";
import { ExternalLink, Home } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { PhaseStepper } from "@/components/workspace/phase-stepper";
import { SoundToggle, useSoundEnabled } from "@/components/workspace/sound-toggle";
import type { SessionPhase } from "@/lib/events";
import type { MessageOut } from "@/lib/api";

interface TopBarProps {
  repoOwner?: string;
  repoName?: string;
  githubUrl?: string;
  isSampleRepo?: boolean;
  phase: SessionPhase;
  messages?: MessageOut[];
  soundEnabled: boolean;
  onSoundChange: (value: boolean) => void;
}

export function TopBar({
  repoOwner,
  repoName,
  githubUrl,
  isSampleRepo,
  phase,
  messages,
  soundEnabled,
  onSoundChange,
}: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex flex-col gap-3 border-b-2 border-ink bg-cream/95 px-4 py-3 backdrop-blur-sm sm:px-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2">
            <DuckMascot mood="idle" size={28} />
            <span className="font-heading text-lg font-extrabold">Duck</span>
          </Link>
          <Link
            href="/"
            className="press-down hidden items-center gap-1.5 rounded-full border-2 border-ink bg-paper px-3 py-1 text-xs font-bold shadow-brutal-sm sm:inline-flex sm:text-sm"
          >
            <Home className="size-3.5" aria-hidden />
            New bug
          </Link>
        </div>

        <div className="flex items-center gap-2">
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
          {isSampleRepo && (
            <span className="inline-flex items-center rounded-full border-2 border-ink bg-duck-soft px-2 py-0.5 text-[0.65rem] font-bold whitespace-nowrap sm:text-xs">
              sample repo
            </span>
          )}
        </div>

        <SoundToggle enabled={soundEnabled} onChange={onSoundChange} />
      </div>

      <div className="flex items-center justify-between gap-3">
        <PhaseStepper phase={phase} messages={messages} />
        <Link
          href="/"
          className="press-down inline-flex shrink-0 items-center gap-1 rounded-full border-2 border-ink bg-paper px-2.5 py-1 text-xs font-bold shadow-brutal-sm sm:hidden"
          aria-label="New bug"
        >
          <Home className="size-3.5" aria-hidden />
        </Link>
      </div>
    </header>
  );
}

export { useSoundEnabled };
