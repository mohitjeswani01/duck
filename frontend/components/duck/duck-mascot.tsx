"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

export type DuckMood =
  | "idle"
  | "listening"
  | "investigating"
  | "thinking"
  | "hypothesis"
  | "resolved";

interface DuckMascotProps {
  mood?: DuckMood;
  size?: number;
  className?: string;
}

const CONFETTI_COLORS = ["var(--color-duck)", "var(--color-beak)", "var(--color-ink)", "var(--color-paper)"];

/**
 * Duck, drawn fresh for this project: a rounded body + head, a beak-orange
 * bill, two simple arc wings, and a small set of mood accessories (reading
 * glasses, a thought bubble, a lightbulb, a confetti burst) layered on top of
 * the same base shape. Not modeled on any existing character — just the
 * simplest friendly rubber-duck silhouette that reads at both avatar size and
 * large-panel size.
 */
export function DuckMascot({ mood = "idle", size = 64, className }: DuckMascotProps) {
  const reduceMotion = useReducedMotion();

  const bodyTilt = mood === "listening" ? -6 : 0;
  const headLook = mood === "investigating" ? 5 : 0;
  const eyeRadius = mood === "hypothesis" ? 4.6 : 3.2;

  const bob = reduceMotion
    ? {}
    : mood === "thinking"
      ? { y: [0, -2.5, 0] }
      : mood === "resolved"
        ? { y: [0, -4, 0] }
        : { y: [0, -1, 0] };

  const bobTransition = reduceMotion
    ? { duration: 0 }
    : {
        duration: mood === "thinking" ? 1.1 : 2.6,
        repeat: Infinity,
        ease: "easeInOut" as const,
      };

  return (
    <motion.svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={`Duck, ${mood}`}
      animate={bob}
      transition={bobTransition}
    >
      {/* feet */}
      <ellipse cx="40" cy="92" rx="5" ry="3" fill="var(--color-beak)" />
      <ellipse cx="60" cy="92" rx="5" ry="3" fill="var(--color-beak)" />

      {/* body */}
      <motion.g
        animate={
          reduceMotion
            ? {}
            : mood === "resolved"
              ? { rotate: [0, -3, 0, 3, 0] }
              : {}
        }
        transition={reduceMotion ? { duration: 0 } : { duration: 0.9, repeat: Infinity, ease: "easeInOut" }}
        style={{ transformOrigin: "50px 70px" }}
      >
        <ellipse cx="50" cy="72" rx="27" ry="21" fill="var(--color-duck)" stroke="var(--color-ink)" strokeWidth="3.5" />

        {/* wings */}
        <motion.path
          d="M 27 68 Q 18 72 23 84"
          fill="none"
          stroke="var(--color-ink)"
          strokeWidth="3"
          strokeLinecap="round"
          animate={reduceMotion ? {} : mood === "resolved" ? { rotate: [0, -18, 0] } : {}}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.45, repeat: Infinity, ease: "easeInOut" }}
          style={{ transformOrigin: "27px 68px" }}
        />
        <motion.path
          d="M 73 68 Q 82 72 77 84"
          fill="none"
          stroke="var(--color-ink)"
          strokeWidth="3"
          strokeLinecap="round"
          animate={reduceMotion ? {} : mood === "resolved" ? { rotate: [0, 18, 0] } : {}}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.45, repeat: Infinity, ease: "easeInOut" }}
          style={{ transformOrigin: "73px 68px" }}
        />
      </motion.g>

      {/* head */}
      <motion.g
        animate={{ rotate: bodyTilt, y: headLook }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        style={{ transformOrigin: "50px 42px" }}
      >
        <circle cx="50" cy="40" r="24" fill="var(--color-duck)" stroke="var(--color-ink)" strokeWidth="3.5" />

        {/* beak */}
        <ellipse cx="50" cy="58" rx="15" ry="7.5" fill="var(--color-beak)" stroke="var(--color-ink)" strokeWidth="3" />
        <line x1="38" y1="58" x2="62" y2="58" stroke="var(--color-ink)" strokeWidth="1.5" opacity="0.5" />

        {/* eyes */}
        <motion.circle cx="41" cy="36" animate={{ r: eyeRadius }} fill="var(--color-ink)" />
        <motion.circle cx="59" cy="36" animate={{ r: eyeRadius }} fill="var(--color-ink)" />
        {mood === "hypothesis" && (
          <>
            <circle cx="42.5" cy="34.5" r="1" fill="var(--color-paper)" />
            <circle cx="60.5" cy="34.5" r="1" fill="var(--color-paper)" />
          </>
        )}

        {/* reading glasses — investigating */}
        <AnimatePresence>
          {mood === "investigating" && (
            <motion.g
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25 }}
            >
              <circle cx="41" cy="36" r="9" fill="none" stroke="var(--color-ink)" strokeWidth="2.25" />
              <circle cx="59" cy="36" r="9" fill="none" stroke="var(--color-ink)" strokeWidth="2.25" />
              <line x1="50" y1="36" x2="50" y2="36" stroke="var(--color-ink)" strokeWidth="2.25" />
              <path d="M 50 34 Q 50 32 50 34" stroke="var(--color-ink)" strokeWidth="2.25" fill="none" />
              <line x1="32" y1="35" x2="27" y2="32" stroke="var(--color-ink)" strokeWidth="2" strokeLinecap="round" />
              <line x1="68" y1="35" x2="73" y2="32" stroke="var(--color-ink)" strokeWidth="2" strokeLinecap="round" />
            </motion.g>
          )}
        </AnimatePresence>
      </motion.g>

      {/* thought bubble — thinking */}
      <AnimatePresence>
        {mood === "thinking" && (
          <motion.g
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.6 }}
            transition={{ duration: 0.25 }}
          >
            <circle cx="76" cy="18" r="3" fill="var(--color-paper)" stroke="var(--color-ink)" strokeWidth="2" />
            <circle cx="83" cy="10" r="4.5" fill="var(--color-paper)" stroke="var(--color-ink)" strokeWidth="2" />
            <rect x="80" y="-2" width="20" height="14" rx="7" fill="var(--color-paper)" stroke="var(--color-ink)" strokeWidth="2" />
            {[0, 1, 2].map((i) => (
              <motion.circle
                key={i}
                cx={85 + i * 5}
                cy={5}
                r="1.6"
                fill="var(--color-ink)"
                animate={reduceMotion ? {} : { opacity: [0.25, 1, 0.25] }}
                transition={reduceMotion ? { duration: 0 } : { duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
              />
            ))}
          </motion.g>
        )}
      </AnimatePresence>

      {/* lightbulb — hypothesis */}
      <AnimatePresence>
        {mood === "hypothesis" && (
          <motion.g
            initial={{ opacity: 0, scale: 0.4, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.4 }}
            transition={{ duration: 0.3, ease: "backOut" }}
          >
            <circle cx="80" cy="14" r="8" fill="var(--color-duck)" stroke="var(--color-ink)" strokeWidth="2.25" />
            <rect x="77" y="20" width="6" height="4" fill="var(--color-ink)" />
            {[0, 1, 2, 3].map((i) => {
              const angle = (i * Math.PI) / 2 + Math.PI / 4;
              const x1 = 80 + Math.cos(angle) * 11;
              const y1 = 14 + Math.sin(angle) * 11;
              const x2 = 80 + Math.cos(angle) * 15;
              const y2 = 14 + Math.sin(angle) * 15;
              return (
                <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--color-beak)" strokeWidth="2" strokeLinecap="round" />
              );
            })}
          </motion.g>
        )}
      </AnimatePresence>

      {/* confetti — resolved */}
      <AnimatePresence>
        {mood === "resolved" &&
          !reduceMotion &&
          Array.from({ length: 8 }).map((_, i) => {
            const angle = (i / 8) * Math.PI * 2;
            return (
              <motion.rect
                key={i}
                x={49}
                y={40}
                width="4"
                height="4"
                fill={CONFETTI_COLORS[i % CONFETTI_COLORS.length]}
                initial={{ opacity: 1, x: 49, y: 40, rotate: 0 }}
                animate={{
                  opacity: [1, 1, 0],
                  x: 49 + Math.cos(angle) * 48,
                  y: 40 + Math.sin(angle) * 48,
                  rotate: 180,
                }}
                transition={{ duration: 1.1, repeat: Infinity, repeatDelay: 0.6, delay: i * 0.03 }}
              />
            );
          })}
      </AnimatePresence>
    </motion.svg>
  );
}
