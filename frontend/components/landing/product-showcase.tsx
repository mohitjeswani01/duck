import type { ReactNode } from "react";
import { FileSearch, FileText, Lightbulb, MoveRight } from "lucide-react";

const TRACE = [
  { icon: FileText, label: "Duck is reading backend/routes/tasks.js" },
  { icon: FileSearch, label: "Duck is searching for page * pageSize" },
  { icon: FileText, label: "Duck is reading backend/db/store.js" },
];

/** A static recreation of the workspace mid-investigation, not a real
 * screenshot — stays crisp at any size and never goes stale as the UI
 * evolves. Three short callouts label the parts judges care about. */
export function ProductShowcase() {
  return (
    <section id="product-showcase" className="flex flex-col gap-6 py-12">
      <div>
        <h2 className="font-heading text-2xl font-bold sm:text-3xl">Watch Duck think</h2>
        <p className="mt-1 text-muted-foreground">Every investigation is visible, live — nothing happens off-screen.</p>
      </div>

      <div className="rounded-2xl border-2 border-ink bg-paper p-2 shadow-brutal-lg sm:p-3">
        <div className="flex items-center gap-1.5 border-b-2 border-ink/10 px-2 pb-2">
          <span className="size-2.5 rounded-full bg-diff-remove" />
          <span className="size-2.5 rounded-full bg-duck" />
          <span className="size-2.5 rounded-full bg-diff-add" />
          <span className="ml-2 font-mono text-xs text-muted-foreground">duck.app/workspace</span>
        </div>

        <div className="grid grid-cols-1 gap-4 p-3 sm:grid-cols-2 sm:p-4">
          <div className="flex flex-col gap-2">
            <Callout>Live investigation trace</Callout>
            <div className="flex flex-col gap-2 rounded-xl border-2 border-ink/15 bg-cream px-3 py-3">
              {TRACE.map((t, i) => (
                <div key={i} className="flex items-center gap-2 text-xs sm:text-sm">
                  <t.icon className="size-3.5 shrink-0 text-beak" aria-hidden />
                  <span className="font-mono text-ink/80">{t.label}</span>
                </div>
              ))}
            </div>

            <Callout className="mt-2">Hypothesis, with evidence</Callout>
            <div className="flex items-start gap-2 rounded-xl border-2 border-ink bg-duck-soft px-3 py-3">
              <Lightbulb className="mt-0.5 size-4 shrink-0" aria-hidden />
              <p className="text-xs font-semibold sm:text-sm">
                Pagination offset is <span className="font-mono">page * pageSize</span> instead of{" "}
                <span className="font-mono">(page - 1) * pageSize</span> — page 1 skips the first page&apos;s tasks.
                <span className="mt-1 block font-normal text-ink/60">Evidence: backend/routes/tasks.js:14</span>
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Callout>Backend-built diff, never hand-written by the model</Callout>
            <div className="overflow-hidden rounded-xl border-2 border-ink font-mono text-xs">
              <div className="bg-ink px-3 py-1.5 text-paper">backend/routes/tasks.js</div>
              <div className="bg-diff-remove-bg px-3 py-1.5 text-diff-remove">− const offset = page * pageSize;</div>
              <div className="bg-diff-add-bg px-3 py-1.5 text-diff-add">+ const offset = (page - 1) * pageSize;</div>
            </div>
            <div className="mt-2 flex flex-1 flex-col items-start justify-center gap-2 rounded-xl border-2 border-ink/15 bg-cream px-3 py-4">
              <p className="text-xs font-semibold text-ink/70 sm:text-sm">
                You accept it, reject it, or tell Duck why it&apos;s wrong — and it keeps digging.
              </p>
              <div className="flex gap-2">
                <span className="rounded-full border-2 border-ink bg-ink px-3 py-1 text-xs font-bold text-cream">Accept fix</span>
                <span className="rounded-full border-2 border-ink bg-paper px-3 py-1 text-xs font-bold">This doesn&apos;t fix it</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Callout({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`flex items-center gap-1.5 text-xs font-bold text-beak uppercase tracking-wide ${className}`}>
      <MoveRight className="size-3.5" aria-hidden />
      {children}
    </div>
  );
}
