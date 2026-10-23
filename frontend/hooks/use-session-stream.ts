"use client";

import { useEffect, useRef, useState } from "react";
import { getStreamUrl } from "@/lib/api";
import type { DuckEvent } from "@/lib/events";

type ConnectionState = "connecting" | "open" | "reconnecting";

interface UseSessionStreamOptions {
  onEvent: (event: DuckEvent) => void;
  /** Called after a drop-and-reconnect, so the caller can re-fetch full
   * session state via GET /sessions/{id} and not lose anything that was
   * missed while disconnected. Not called on the very first connect. */
  onReconnect: () => void;
}

const EVENT_TYPES: DuckEvent["type"][] = ["phase", "tool_call", "assistant_message", "diff", "error", "done"];

/** Subscribes to GET /sessions/{id}/stream. Browsers already retry a dropped
 * EventSource automatically; this just tracks that so the UI can say
 * "reconnecting…" and resync full state once back, per CLAUDE.md "Loading,
 * errors and slow responses". */
export function useSessionStream(sessionId: string | null, { onEvent, onReconnect }: UseSessionStreamOptions) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const hasErroredRef = useRef(false);
  const onEventRef = useRef(onEvent);
  const onReconnectRef = useRef(onReconnect);

  // Keep the refs pointing at the latest callbacks without restarting the
  // EventSource effect below on every render a new inline function is passed.
  useEffect(() => {
    onEventRef.current = onEvent;
    onReconnectRef.current = onReconnect;
  });

  useEffect(() => {
    if (!sessionId) return;

    hasErroredRef.current = false;

    const source = new EventSource(getStreamUrl(sessionId));

    const listeners = EVENT_TYPES.map((type) => {
      const handler = (e: MessageEvent) => {
        try {
          const parsed = JSON.parse(e.data) as DuckEvent;
          onEventRef.current(parsed);
        } catch {
          // malformed event — drop it rather than crash the stream
        }
      };
      source.addEventListener(type, handler);
      return { type, handler };
    });

    source.onopen = () => {
      if (hasErroredRef.current) {
        onReconnectRef.current();
      }
      hasErroredRef.current = false;
      setConnectionState("open");
    };

    source.onerror = () => {
      hasErroredRef.current = true;
      setConnectionState("reconnecting");
    };

    return () => {
      listeners.forEach(({ type, handler }) => source.removeEventListener(type, handler));
      source.close();
    };
  }, [sessionId]);

  return { connectionState };
}
