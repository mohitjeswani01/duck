import { HelpCircle } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";

/** Duck's clarifying questions, parsed from the numbered-list text the
 * backend saves ("1. ...\n2. ..."), rendered as a distinct card rather than
 * a plain chat bubble. */
export function QuestionCard({ content }: { content: string }) {
  const questions = content
    .split(/\n+/)
    .map((line) => line.replace(/^\d+\.\s*/, "").trim())
    .filter(Boolean);

  return (
    <div className="flex items-start gap-3">
      <DuckMascot mood="investigating" size={32} className="mt-1 shrink-0" />
      <div className="flex-1 rounded-xl border-2 border-ink bg-duck-soft px-4 py-3 shadow-brutal-sm">
        <div className="mb-1.5 flex items-center gap-1.5 text-xs font-bold tracking-wide text-ink/70 uppercase">
          <HelpCircle className="size-3.5" aria-hidden />
          Duck is asking
        </div>
        <ol className="flex flex-col gap-1.5">
          {questions.map((q, i) => (
            <li key={i} className="flex gap-2 text-sm font-medium sm:text-base">
              <span className="font-heading font-bold">{i + 1}.</span>
              <span>{q}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
