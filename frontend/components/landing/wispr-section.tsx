import { Mic, Sparkles } from "lucide-react";

export function WisprSection() {
  return (
    <section id="wispr" className="flex flex-col gap-4 rounded-xl border-2 border-ink bg-paper p-6 shadow-brutal sm:p-10">
      <div className="inline-flex items-center gap-2 self-start rounded-full border-2 border-ink bg-duck-soft px-3 py-1 text-xs font-bold">
        <Mic className="size-3.5" aria-hidden />
        Built with Wispr Flow
      </div>
      <h2 className="font-heading text-2xl font-bold sm:text-3xl">Built by voice, for voice</h2>
      <div className="grid gap-6 sm:grid-cols-2">
        <p className="text-ink/80">
          Every line of this project — the plan, the code, the commit messages, this page — was dictated with Wispr
          Flow, not typed. If Duck only worked for carefully-typed bug reports, it would have missed its own point.
        </p>
        <p className="text-ink/80">
          <Sparkles className="mr-1 inline size-4 text-beak" aria-hidden />
          So Duck is built for how people actually talk: rambling, backtracking, filler words, and technical terms
          dictation mishears (&ldquo;expires at&rdquo; → &ldquo;expire sat&rdquo;). Duck reads through all of it
          silently and never comments on the transcription — it just gets to work.
        </p>
      </div>
    </section>
  );
}
