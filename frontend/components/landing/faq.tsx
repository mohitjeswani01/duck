import { ChevronDown } from "lucide-react";
import { TASKBOARD_GITHUB_URL } from "@/lib/constants";

const QUESTIONS = [
  {
    q: "Does Duck change my code?",
    a: "Not without asking. Duck proposes a fix as a real diff, built by the backend from the actual file content — never by the model guessing — and nothing is applied until you click Accept.",
  },
  {
    q: "Which repos work?",
    a: "Any public GitHub repo, small to medium sized (up to ~500 files, 5MB total). Private repos aren't supported in this demo.",
  },
  {
    q: "What is taskboard?",
    a: (
      <>
        A small task-manager app built specifically for this demo, with three real bugs planted in it on purpose. Pick
        a symptom chip above and Duck investigates it live — or skip it and point Duck at any public repo of your
        own.{" "}
        <a href={TASKBOARD_GITHUB_URL} target="_blank" rel="noreferrer" className="font-semibold underline">
          View the source →
        </a>
      </>
    ),
  },
  {
    q: "Is my code stored anywhere?",
    a: "Connected repos are cached in Duck's database for an hour so repeat sessions are instant, then re-fetched from GitHub. Nothing is sent anywhere except to Google's Gemini API for reasoning.",
  },
  {
    q: "Do I need Wispr Flow to use it?",
    a: "No — you can type into the textarea too. But Duck was designed around dictation, so it's built to handle rambling, filler words, and misheard technical terms gracefully.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="flex flex-col gap-6 py-12">
      <h2 className="font-heading text-2xl font-bold sm:text-3xl">FAQ</h2>
      <div className="flex flex-col gap-3">
        {QUESTIONS.map((item) => (
          <details key={item.q} className="group rounded-xl border-2 border-ink bg-paper px-4 py-3 shadow-brutal-sm">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-heading text-base font-bold">
              {item.q}
              <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <p className="mt-2 text-sm text-ink/80">{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
