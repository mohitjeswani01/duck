"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { TopBar, useSoundEnabled } from "@/components/workspace/top-bar";
import { ConversationColumn } from "@/components/workspace/conversation-column";
import { InvestigationColumn } from "@/components/workspace/investigation-column";
import { ErrorBanner } from "@/components/duck/error-banner";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { useSessionStream } from "@/hooks/use-session-stream";
import { useSlowRequestNotice } from "@/hooks/use-slow-request-notice";
import { latestFixBatch } from "@/lib/utils";
import { speak, stopSpeaking } from "@/lib/speech";
import { TASKBOARD_GITHUB_URL } from "@/lib/constants";
import { getSession, getRepo, sendMessage, acceptFix, rejectFix, ApiError, type SessionStateResponse, type RepoOut } from "@/lib/api";
import type { DuckEvent, ToolCallEvent } from "@/lib/events";

const TOOL_VERB: Record<ToolCallEvent["tool"], string> = {
  read_file: "Duck is reading",
  search_code: "Duck is searching for",
  list_files: "Duck is listing files in",
};

const STUCK_THRESHOLD_MS = 15000;

export function WorkspaceClient({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<SessionStateResponse | null>(null);
  const [repo, setRepo] = useState<RepoOut | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [trace, setTrace] = useState<ToolCallEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState<string | undefined>();
  const [decisionBusy, setDecisionBusy] = useState(false);
  const { enabled: soundEnabled, setEnabled: setSoundEnabled } = useSoundEnabled();

  // 0, not Date.now() — a ref initializer runs during render and must stay
  // pure. This is only ever read inside the busy-escalation interval below,
  // and always freshly set (via beginTurn or the SSE handler) before that
  // interval's effect can start, so the placeholder value is never read.
  const lastEventAtRef = useRef(0);
  const wakingUp = useSlowRequestNotice(initialLoading);
  const isSampleRepo = repo?.name?.toLowerCase() === "taskboard" || repo?.github_url === TASKBOARD_GITHUB_URL;

  // null means "not yet hydrated" — on first load we record the starting
  // message count without speaking anything (a page refresh shouldn't replay
  // the whole conversation out loud).
  const lastSpokenCountRef = useRef<number | null>(null);

  useEffect(() => {
    if (!session) return;
    if (lastSpokenCountRef.current === null) {
      lastSpokenCountRef.current = session.messages.length;
      return;
    }
    const newMessages = session.messages.slice(lastSpokenCountRef.current);
    lastSpokenCountRef.current = session.messages.length;
    if (!soundEnabled) return;
    for (const m of newMessages) {
      if (m.role !== "assistant") continue;
      if (m.phase_at_time === "clarifying") {
        speak(m.content);
      } else if (m.phase_at_time === "hypothesis") {
        speak("I think I found it. Check the hypothesis card.");
      } else if (m.phase_at_time === "resolved") {
        speak(session.resolution_summary ?? "Bug resolved.");
      }
    }
  }, [session, soundEnabled]);

  function handleSoundChange(value: boolean) {
    if (!value) stopSpeaking();
    setSoundEnabled(value);
  }

  const refreshSession = useCallback(async () => {
    try {
      const data = await getSession(sessionId);
      setSession(data);
    } catch (err) {
      setBannerError(err instanceof ApiError ? err.message : "Couldn't refresh this session.");
    }
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;
    getSession(sessionId)
      .then(async (data) => {
        if (cancelled) return;
        setSession(data);
        // A turn can genuinely still be running server-side when this page
        // loads (e.g. opened in a second tab, or reloaded mid-turn) — reflect
        // that immediately instead of looking idle while something's
        // actually happening. The reverse (backend restarted mid-turn) is
        // already handled server-side: GET /sessions/{id} self-heals a stale
        // turn_started_at before we ever see it, so data.turn_running is
        // already correct either way.
        if (data.turn_running) {
          setBusy(true);
          setStatusText("Duck is still looking into this…");
          lastEventAtRef.current = Date.now();
        }
        try {
          const repoData = await getRepo(data.repo_id);
          if (!cancelled) setRepo(repoData);
        } catch {
          // non-critical — the top bar just omits the repo link
        }
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Couldn't load this session.");
      })
      .finally(() => {
        if (!cancelled) setInitialLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleEvent = useCallback(
    (event: DuckEvent) => {
      lastEventAtRef.current = Date.now();
      switch (event.type) {
        case "tool_call":
          setTrace((t) => [...t, event]);
          setStatusText(`${TOOL_VERB[event.tool]} ${event.detail}`);
          break;
        case "phase":
        case "assistant_message":
        case "diff":
          void refreshSession();
          break;
        case "error":
          setBannerError(event.message);
          break;
        case "done":
          setBusy(false);
          setStatusText(undefined);
          break;
      }
    },
    [refreshSession]
  );

  const handleReconnect = useCallback(async () => {
    // A dropped-then-reopened SSE connection is exactly the situation where
    // the backend process could have restarted mid-turn and we'd otherwise
    // never see another event for this turn again — check the durable
    // turn_running flag (not just re-fetch-and-hope) so the input doesn't
    // stay disabled forever waiting for a "done" that's never coming.
    try {
      const data = await getSession(sessionId);
      setSession(data);
      if (!data.turn_running) {
        setBusy(false);
        setStatusText(undefined);
      }
    } catch (err) {
      setBannerError(err instanceof ApiError ? err.message : "Couldn't reconnect to this session.");
    }
  }, [sessionId]);

  useSessionStream(session ? sessionId : null, { onEvent: handleEvent, onReconnect: handleReconnect });

  // Escalate the status message if nothing's happened for a while — Gemini
  // itself can be slow, and a silent wait reads as frozen.
  useEffect(() => {
    if (!busy) return;
    const interval = setInterval(() => {
      if (Date.now() - lastEventAtRef.current > STUCK_THRESHOLD_MS) {
        setStatusText("Duck is thinking really hard about this one…");
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [busy]);

  function beginTurn(initialStatus: string) {
    setBannerError(null);
    setBusy(true);
    setStatusText(initialStatus);
    lastEventAtRef.current = Date.now();
  }

  async function handleSendMessage(text: string) {
    if (!session) return;
    stopSpeaking();
    beginTurn("Duck is thinking…");
    const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
    setSession((s) =>
      s
        ? {
            ...s,
            messages: [...s.messages, { role: "user", phase_at_time: s.current_phase, content: text, created_at: new Date().toISOString() }],
            words_spoken_count: s.words_spoken_count + wordCount,
            turn_running: true,
            deadline_hit: false,
          }
        : s
    );
    try {
      await sendMessage(sessionId, text);
    } catch (err) {
      setBusy(false);
      setStatusText(undefined);
      setBannerError(err instanceof ApiError ? err.message : "Couldn't send that message.");
    }
  }

  function handleKeepGoing() {
    void handleSendMessage("Keep going.");
  }

  async function handleAccept() {
    if (!session) return;
    const batch = latestFixBatch(session.fixes);
    if (batch.length === 0) return;
    setDecisionBusy(true);
    setBannerError(null);
    try {
      await acceptFix(sessionId, batch[0].id);
      beginTurn("Duck is wrapping up…");
    } catch (err) {
      setBannerError(err instanceof ApiError ? err.message : "Couldn't accept that fix.");
    } finally {
      setDecisionBusy(false);
    }
  }

  async function handleReject(feedback?: string) {
    if (!session) return;
    const batch = latestFixBatch(session.fixes);
    if (batch.length === 0) return;
    setDecisionBusy(true);
    setBannerError(null);
    try {
      await rejectFix(sessionId, batch[0].id, feedback);
      beginTurn("Duck is taking another look…");
    } catch (err) {
      setBannerError(err instanceof ApiError ? err.message : "Couldn't send that back to Duck.");
    } finally {
      setDecisionBusy(false);
    }
  }

  if (initialLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
        <DuckMascot mood="thinking" size={72} />
        <p className="font-heading text-lg font-bold">{wakingUp ? "Waking Duck up…" : "Loading session…"}</p>
        {wakingUp && <p className="max-w-sm text-sm text-muted-foreground">The backend naps when idle — this can take up to a minute on a cold start.</p>}
      </div>
    );
  }

  if (loadError || !session) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
        <DuckMascot mood="idle" size={64} />
        <ErrorBanner message={loadError ?? "Something went wrong loading this session."} className="max-w-md" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        repoOwner={repo?.owner}
        repoName={repo?.name}
        githubUrl={repo?.github_url}
        isSampleRepo={isSampleRepo}
        phase={session.current_phase}
        messages={session.messages}
        soundEnabled={soundEnabled}
        onSoundChange={handleSoundChange}
      />

      <div className="px-4 pt-3 sm:px-6">
        <AnimatePresence>{bannerError && <ErrorBanner message={bannerError} onDismiss={() => setBannerError(null)} />}</AnimatePresence>
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:grid lg:grid-cols-[1.2fr_1fr]">
        <ConversationColumn
          messages={session.messages}
          onSendMessage={handleSendMessage}
          busy={busy}
          statusText={statusText}
          wordsSpokenCount={session.words_spoken_count}
          phase={session.current_phase}
          deadlineHit={session.deadline_hit}
          onKeepGoing={handleKeepGoing}
        />
        <InvestigationColumn
          phase={session.current_phase}
          busy={busy}
          trace={trace}
          hypotheses={session.hypotheses}
          fixes={session.fixes}
          repoId={session.repo_id}
          onAccept={handleAccept}
          onReject={handleReject}
          decisionBusy={decisionBusy}
          resolutionSummary={session.resolution_summary}
          rootCause={session.root_cause}
          tags={session.tags}
          soundEnabled={soundEnabled}
        />
      </div>
    </div>
  );
}
