/**
 * Mirrors backend/app/schemas/events.py exactly. The two must never drift —
 * if a field changes on one side, change it here too in the same commit.
 *
 * Schema locked in Phase 1; the actual SSE stream is built in Phase 3 and
 * consumed by the frontend in Phase 4. See CLAUDE.md "Real-time streaming".
 */

export type SessionPhase =
  | "listening"
  | "clarifying"
  | "investigating"
  | "hypothesis"
  | "fix_proposed"
  | "resolved";

export interface PhaseEvent {
  type: "phase";
  session_id: string;
  phase: SessionPhase;
  at: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  session_id: string;
  tool: "read_file" | "list_files" | "search_code";
  detail: string;
  at: string;
}

export interface AssistantMessageEvent {
  type: "assistant_message";
  session_id: string;
  phase: SessionPhase;
  content: string;
  at: string;
}

export interface DiffEvent {
  type: "diff";
  session_id: string;
  file_path: string;
  diff_text: string;
  at: string;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  at: string;
}

export interface DoneEvent {
  type: "done";
  session_id: string;
  at: string;
}

export type DuckEvent =
  | PhaseEvent
  | ToolCallEvent
  | AssistantMessageEvent
  | DiffEvent
  | ErrorEvent
  | DoneEvent;
