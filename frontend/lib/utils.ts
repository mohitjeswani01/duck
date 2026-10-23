export { cn } from "cn";

import type { FixOut } from "./api";

/** Fixes in one `propose_fix` call all share one explicit batch timestamp
 * (see backend control_tools.py) — this is how the frontend groups "the
 * current proposal" without a dedicated batch id. */
export function latestFixBatch(fixes: FixOut[]): FixOut[] {
  if (fixes.length === 0) return [];
  const latestTime = fixes.reduce((max, f) => (f.created_at > max ? f.created_at : max), fixes[0].created_at);
  return fixes.filter((f) => f.created_at === latestTime);
}
