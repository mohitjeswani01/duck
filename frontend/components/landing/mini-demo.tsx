"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileSearch, FileText, Lightbulb } from "lucide-react";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { DuckMascot } from "@/components/duck/duck-mascot";

const SCRIPT_TEXT = "I keep getting logged out randomly after I log in...";
const TYPE_SPEED_MS = 42;
const HOLD_AFTER_TYPE_MS = 500;
const STEP_DELAY_MS = 900;
const END_HOLD_MS = 2400;

type Beat =
  | { kind: "tool"; icon: "read" | "search"; label: string }
  | { kind: "hypothesis"; text: string }
  | { kind: "diff" };

const BEATS: Beat[] = [
  { kind: "tool", icon: "read", label: "Duck is reading auth.js" },
  { kind: "tool", icon: "search", label: "Duck is searching for expiresAt" },
  { kind: "hypothesis", text: "expiresAt is compared in seconds against Date.now() in milliseconds." },
  { kind: "diff" },
];

/** Non-interactive, looping scripted demo for the hero — no API calls. Types
 * out a bug description, then reveals tool-call lines, a hypothesis, and a
 * tiny diff, one beat at a time, then resets. */
export function MiniDemo() {
  const reduceMotion = useReducedMotion();
  const [typedLength, setTypedLength] = useState(reduceMotion ? SCRIPT_TEXT.length : 0);
  const [visibleBeats, setVisibleBeats] = useState(reduceMotion ? BEATS.length : 0);

  useEffect(() => {
    if (reduceMotion) return;

    let cancelled = false;
    const timeouts: ReturnType<typeof setTimeout>[] = [];

    function schedule(fn: () => void, delay: number) {
      const id = setTimeout(() => {
        if (!cancelled) fn();
      }, delay);
      timeouts.push(id);
      return id;
    }

    function run() {
      setTypedLength(0);
      setVisibleBeats(0);

      for (let i = 1; i <= SCRIPT_TEXT.length; i++) {
        schedule(() => setTypedLength(i), i * TYPE_SPEED_MS);
      }

      const typeDone = SCRIPT_TEXT.length * TYPE_SPEED_MS + HOLD_AFTER_TYPE_MS;
      BEATS.forEach((_, i) => {
        schedule(() => setVisibleBeats(i + 1), typeDone + i * STEP_DELAY_MS);
      });

      const totalDone = typeDone + BEATS.length * STEP_DELAY_MS + END_HOLD_MS;
      schedule(run, totalDone);
    }

    run();

    return () => {
      cancelled = true;
      timeouts.forEach(clearTimeout);
    };
  }, [reduceMotion]);

  const mood = visibleBeats === 0 ? "listening" : visibleBeats <= 2 ? "investigating" : visibleBeats === 3 ? "hypothesis" : "resolved";

  return (
    <div className="flex h-full flex-col gap-4 rounded-xl border-2 border-ink bg-paper p-5 shadow-brutal-lg">
      <div className="flex items-center gap-3 border-b-2 border-ink/10 pb-3">
        <DuckMascot mood={mood} size={40} />
        <div>
          <p className="font-heading text-sm font-bold">Live with Duck</p>
          <p className="text-xs text-muted-foreground">taskboard · auth bug</p>
        </div>
      </div>

      <div className="rounded-lg border-2 border-ink/15 bg-cream px-3 py-2.5 font-mono text-sm text-ink">
        {SCRIPT_TEXT.slice(0, typedLength)}
        {!reduceMotion && typedLength < SCRIPT_TEXT.length && (
          <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse bg-ink" />
        )}
      </div>

      <div className="flex min-h-36 flex-col gap-2">
        <AnimatePresence mode="popLayout">
          {BEATS.slice(0, visibleBeats).map((beat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
            >
              {beat.kind === "tool" && (
                <div className="flex items-center gap-2 text-sm text-ink/80">
                  {beat.icon === "read" ? (
                    <FileText className="size-3.5 text-beak" aria-hidden />
                  ) : (
                    <FileSearch className="size-3.5 text-beak" aria-hidden />
                  )}
                  <span className="font-mono text-xs sm:text-sm">{beat.label}</span>
                </div>
              )}
              {beat.kind === "hypothesis" && (
                <div className="flex items-start gap-2 rounded-lg border-2 border-ink bg-duck-soft px-3 py-2">
                  <Lightbulb className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  <p className="text-xs font-semibold sm:text-sm">{beat.text}</p>
                </div>
              )}
              {beat.kind === "diff" && (
                <div className="overflow-hidden rounded-lg border-2 border-ink font-mono text-xs">
                  <div className="bg-ink px-2 py-1 text-paper">session.js</div>
                  <div className="bg-diff-remove-bg px-2 py-1 text-diff-remove">
                    − return session.expiresAt - Date.now();
                  </div>
                  <div className="bg-diff-add-bg px-2 py-1 text-diff-add">
                    + return session.expiresAt * 1000 - Date.now();
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
