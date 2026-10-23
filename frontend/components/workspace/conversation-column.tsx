"use client";

import { useEffect, useRef } from "react";
import { MessageSquareText } from "lucide-react";
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
}

export function ConversationColumn({ messages, onSendMessage, busy, statusText, wordsSpokenCount, phase }: ConversationColumnProps) {
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
          <p className="rounded-xl border-2 border-ink bg-duck-soft px-4 py-3 text-sm font-semibold">
            This bug is resolved. Start a new session from the home page for a different one.
          </p>
        ) : (
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
        )}
      </div>
    </div>
  );
}
