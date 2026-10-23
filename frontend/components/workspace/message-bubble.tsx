import { DuckMascot } from "@/components/duck/duck-mascot";
import { QuestionCard } from "@/components/workspace/question-card";
import { cn } from "cn";
import type { MessageOut } from "@/lib/api";

export function MessageBubble({ message }: { message: MessageOut }) {
  if (message.role === "assistant" && message.phase_at_time === "clarifying") {
    return <QuestionCard content={message.content} />;
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
