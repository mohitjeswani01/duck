import type { ReactNode } from "react";
import { Check, X } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { QuestionCard } from "@/components/workspace/question-card";
import { cn } from "cn";
import type { MessageOut } from "@/lib/api";

const ACCEPTED_PREFIX = "(The user accepted the proposed fix";
const REJECTED_PREFIX = "(The user rejected the proposed fix";

export function MessageBubble({ message }: { message: MessageOut }) {
  // Synthetic fix-decision notes saved by the backend aren't user speech —
  // render them as a small centered system event instead of a chat bubble.
  if (message.role === "user" && message.content.startsWith(ACCEPTED_PREFIX)) {
    return <EventLine icon="check">You accepted the fix</EventLine>;
  }
  if (message.role === "user" && message.content.startsWith(REJECTED_PREFIX)) {
    const feedback = message.content.replace(REJECTED_PREFIX, "").replace(/^[^)]*\)\s*/, "").trim();
    return (
      <EventLine icon="x">
        You said the fix doesn&apos;t work{feedback ? `: "${feedback}"` : ""}
      </EventLine>
    );
  }

  if (message.role === "assistant" && message.phase_at_time === "clarifying") {
    return <QuestionCard content={message.content} />;
  }

  // The full hypothesis lives in the hypothesis card only — the chat message
  // just points there, so the same text doesn't appear twice.
  if (message.role === "assistant" && message.phase_at_time === "hypothesis") {
    return (
      <div className="flex items-start gap-3">
        <DuckMascot mood="hypothesis" size={32} className="mt-1 shrink-0" />
        <div className="max-w-[85%] rounded-xl border-2 border-ink bg-paper px-4 py-2.5 text-sm shadow-brutal-sm sm:text-base">
          <p>I think I found it — check the hypothesis card. →</p>
        </div>
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      {!isUser && <DuckMascot mood="idle" size={32} className="mt-1 shrink-0" />}
      <div
        className={cn(
          "max-w-[85%] rounded-xl border-2 border-ink px-4 py-2.5 text-sm shadow-brutal-sm sm:text-base",
          isUser ? "bg-ink text-cream" : "bg-paper text-ink"
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}

function EventLine({ icon, children }: { icon: "check" | "x"; children: ReactNode }) {
  return (
    <div className="flex items-center justify-center gap-1.5 py-1 text-center text-xs font-semibold text-muted-foreground">
      {icon === "check" ? (
        <Check className="size-3.5 text-diff-add" aria-hidden />
      ) : (
        <X className="size-3.5 text-diff-remove" aria-hidden />
      )}
      <span>{children}</span>
    </div>
  );
}
