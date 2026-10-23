"use client";

import { useEffect, useState } from "react";

/** True once `active` has been true for longer than `delayMs` — drives the
 * "Waking Duck up" message for a cold Render instance instead of leaving a
 * request that's merely slow looking identical to one that's frozen.
 *
 * `slow` only ever flips true from the setTimeout callback (an async
 * callback, not a synchronous effect-body call); gating the return value
 * with `active &&` resets the visible result to false the instant `active`
 * goes false without needing a second synchronous setState in the effect. */
export function useSlowRequestNotice(active: boolean, delayMs = 4000): boolean {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setSlow(true), delayMs);
    return () => clearTimeout(timer);
  }, [active, delayMs]);

  return active && slow;
}
