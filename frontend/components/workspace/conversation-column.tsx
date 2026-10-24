"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { Home, MessageSquareText, PlayCircle, RotateCcw } from "lucide-react";
import { MessageBubble } from "@/components/workspace/message-bubble";
import { WisprInput } from "@/components/duck/wispr-input";
import type { MessageOut } from "@/lib/api";
import type { SessionPhase } from "@/lib/events";

interface ConversationColumnProps {
  messages: MessageOut[];
  onSendMessage: (text: string) => void;
  busy: boolean;
  statusText?: string;
  wordsSpokenCount: number;
  phase: SessionPhase;
  deadlineHit: boolean;
  onKeepGoing: () => void;
}

export function ConversationColumn({
  messages,
  onSendMessage,
  busy,
  statusText,
  wordsSpokenCount,
  phase,
  deadlineHit,
  onKeepGoing,
}: ConversationColumnProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  const awaitingFixDecision = phase === "fix_proposed";
  const resolved = phase === "resolved";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">Duck is getting started&hellip;</p>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t-2 border-ink/10 px-4 py-4 sm:px-6">
        <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
          <MessageSquareText className="size-3.5" aria-hidden />
          You&apos;ve spoken {wordsSpokenCount} {wordsSpokenCount === 1 ? "word" : "words"} this session
        </div>

        {resolved ? (
          <div className="flex flex-col gap-3 rounded-xl border-2 border-ink bg-duck-soft px-4 py-3">
            <p className="text-sm font-semibold">This bug is resolved — nice work.</p>
            <div className="flex flex-wrap gap-2">
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
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {deadlineHit && !busy && (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border-2 border-ink bg-duck-soft px-3.5 py-2.5">
                <p className="text-sm font-semibold">Gemini was slow to respond, so Duck paused.</p>
                <button
                  type="button"
                  onClick={onKeepGoing}
                  className="press-down inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-ink px-3 py-1.5 text-sm font-bold text-cream shadow-brutal-sm"
                >
                  <PlayCircle className="size-3.5" aria-hidden />
                  Keep going
                </button>
              </div>
            )}
            <WisprInput
              onSubmit={onSendMessage}
              disabled={busy || awaitingFixDecision}
              placeholder={
                awaitingFixDecision
                  ? "Use Accept fix / This doesn't fix it in the investigation panel →"
                  : "Hold your Wispr key and just talk."
              }
              statusText={statusText}
            />
          </div>
        )}
      </div>
    </div>
  );
}
