import { FolderGit2, Mic, Wrench } from "lucide-react";

const STEPS = [
  {
    icon: FolderGit2,
    title: "Connect a repo",
    body: "Paste any public GitHub repo, or use the sample one. Duck downloads it once and reads from there.",
  },
  {
    icon: Mic,
    title: "Talk through the bug",
    body: "Hold your Wispr key and describe what's happening, like you're explaining it to a coworker.",
  },
  {
    icon: Wrench,
    title: "Get the fix",
    body: "Duck investigates, states its theory with evidence, and proposes a real diff — you accept or push back.",
  },
];

export function HowItWorks() {
  return (
    <section className="flex flex-col gap-8 py-12">
      <h2 className="font-heading text-2xl font-bold sm:text-3xl">How it works</h2>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <div key={step.title} className="flex flex-col gap-3 rounded-xl border-2 border-ink bg-paper p-5 shadow-brutal">
            <div className="flex items-center gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-duck font-heading text-sm font-bold">
                {i + 1}
              </span>
              <step.icon className="size-5 text-beak" aria-hidden />
            </div>
            <h3 className="font-heading text-lg font-bold">{step.title}</h3>
            <p className="text-sm text-muted-foreground">{step.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
