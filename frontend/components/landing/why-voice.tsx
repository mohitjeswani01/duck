export function WhyVoice() {
  return (
    <section className="flex flex-col gap-4 rounded-xl border-2 border-ink bg-duck-soft/50 p-6 py-12 sm:p-10">
      <h2 className="font-heading text-2xl font-bold sm:text-3xl">Why voice?</h2>
      <div className="grid gap-6 sm:grid-cols-2">
        <p className="text-ink/80">
          Rubber duck debugging works: saying a bug out loud, in order, forces the clarity that finds it. The problem
          is typing it all out is slow enough that the technique gets skipped under deadline pressure — right when
          it would help most.
        </p>
        <p className="text-ink/80">
          Speaking is faster than typing, and it&apos;s harder to skip the details when you&apos;re narrating instead
          of summarizing. Wispr Flow makes the dictation itself invisible, so the only thing left to do is talk —
          Duck listens, reads through the mangled transcription, and gets to work.
        </p>
      </div>
    </section>
  );
}
