"use client";

import { DuckMascot } from "@/components/duck/duck-mascot";
import { Hero } from "@/components/landing/hero";
import { BugPicker } from "@/components/landing/bug-picker";
import { HowItWorks } from "@/components/landing/how-it-works";
import { WhyVoice } from "@/components/landing/why-voice";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b-2 border-ink/10 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center gap-2">
          <DuckMascot mood="idle" size={28} />
          <span className="font-heading text-lg font-extrabold">Duck</span>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-6">
        <Hero />
        <BugPicker />
        <HowItWorks />
        <WhyVoice />
      </main>

      <footer className="px-6 py-8 text-center text-xs text-muted-foreground">
        Built solo for the No Hands Wispr Challenge (WeMakeDevs × Wispr Flow).
      </footer>
    </div>
  );
}
