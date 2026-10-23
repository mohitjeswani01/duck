"use client";

import { ArrowRight } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";

export function FinalCta() {
  return (
    <section id="final-cta" className="flex flex-col items-center gap-5 rounded-2xl border-2 border-ink bg-duck px-6 py-14 text-center shadow-brutal-lg">
      <DuckMascot mood="hypothesis" size={88} />
      <h2 className="font-heading text-3xl font-extrabold sm:text-4xl">Go explain a bug to it.</h2>
      <p className="max-w-md text-ink/80">No login, no setup — pick a real bug and watch Duck work.</p>
      <a
        href="#try-a-bug"
        onClick={(e) => {
          e.preventDefault();
          document.querySelector("#try-a-bug")?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
        className="press-down inline-flex items-center gap-2 rounded-full border-2 border-ink bg-ink px-6 py-3 text-base font-bold text-cream shadow-brutal"
      >
        Try it on a real bug
        <ArrowRight className="size-4" aria-hidden />
      </a>
    </section>
  );
}
