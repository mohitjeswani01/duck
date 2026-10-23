const STATS = [
  { value: "3/3", label: "planted bugs found, right file and root cause every time" },
  { value: "~30s", label: "from symptom to root cause, on the fastest runs" },
  { value: "6", label: "files read on its own, unprompted, to find one bug" },
];

/** Real numbers only, pulled straight from backend/scripts/evaluate.py's
 * hardening-phase run against the live Gemini API — nothing here is made
 * up for the pitch. */
export function StatsStrip() {
  return (
    <section id="stats" className="rounded-xl border-2 border-ink bg-ink py-8">
      <div className="grid grid-cols-1 gap-6 px-6 text-center sm:grid-cols-3">
        {STATS.map((stat) => (
          <div key={stat.label} className="flex flex-col gap-1">
            <span className="font-heading text-4xl font-extrabold text-duck sm:text-5xl">{stat.value}</span>
            <span className="text-sm text-cream/80">{stat.label}</span>
          </div>
        ))}
      </div>
      <p className="mt-6 text-center text-xs font-semibold text-cream/50">
        From real runs against the live Gemini API on the sample repo — nothing made up.
      </p>
    </section>
  );
}
