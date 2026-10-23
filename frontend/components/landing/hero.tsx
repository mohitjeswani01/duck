import { MiniDemo } from "@/components/landing/mini-demo";
import { DuckMascot } from "@/components/duck/duck-mascot";

export function Hero() {
  return (
    <section className="grid grid-cols-1 items-center gap-10 py-12 sm:py-16 lg:grid-cols-2 lg:gap-16">
      <div className="flex flex-col gap-6">
        <div className="inline-flex items-center gap-2 self-start rounded-full border-2 border-ink bg-paper px-3 py-1 text-xs font-bold shadow-brutal-sm">
          <DuckMascot mood="idle" size={20} />
          No Hands Wispr Challenge
        </div>

        <h1 className="font-heading text-5xl leading-[1.05] font-extrabold tracking-tight sm:text-6xl">
          Explain the bug.
          <br />
          <span className="bg-duck px-2">Out loud.</span>
        </h1>

        <p className="max-w-lg text-lg text-ink/80 sm:text-xl">
          Duck is the rubber duck that talks back. Explain your bug like you&apos;re talking to a friend, and Duck
          reads your code, asks the right questions, and finds the fix.
        </p>

        <p className="font-mono text-sm text-beak">built voice first with Wispr Flow</p>
      </div>

      <div className="relative">
        <div className="absolute -top-6 -right-4 hidden rotate-6 sm:block">
          <DuckMascot mood="hypothesis" size={56} />
        </div>
        <MiniDemo />
      </div>
    </section>
  );
}
