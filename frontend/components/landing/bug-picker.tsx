"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { ArrowRight, FolderGit2, Loader2 } from "lucide-react";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { WisprInput } from "@/components/duck/wispr-input";
import { ErrorBanner } from "@/components/duck/error-banner";
import { useSlowRequestNotice } from "@/hooks/use-slow-request-notice";
import { connectRepo, createSession, ApiError, type RepoOut } from "@/lib/api";

const TASKBOARD_URL = "https://github.com/mohitjeswani01/taskboard";

const BUGS = [
  {
    label: "My task list skips items on page one.",
    message:
      "Pagination is broken, when I load page 1 it's missing the first five tasks. They only show up if... actually they never show up, page 1 just starts in the wrong place.",
  },
  {
    label: "I keep getting logged out randomly.",
    message:
      "I log in and then like fifteen seconds later I'm back at the login screen. It's supposed to keep me logged in for an hour, I didn't even get to look at anything.",
  },
  {
    label: "My status filter resets itself after a few seconds.",
    message:
      "I click 'Done' to filter the list, I see the done tasks for a second, and then it just goes back to showing everything. I didn't touch anything.",
  },
];

type BusyState = { kind: "chip"; index: number } | { kind: "custom" } | null;

export function BugPicker() {
  const router = useRouter();
  const [busy, setBusy] = useState<BusyState>(null);
  const [error, setError] = useState<string | null>(null);
  const [customUrl, setCustomUrl] = useState("");
  const [customRepo, setCustomRepo] = useState<RepoOut | null>(null);
  const wakingUp = useSlowRequestNotice(busy !== null);

  async function startSession(repo: RepoOut, message: string) {
    const { session_id } = await createSession(repo.id, message);
    router.push(`/workspace/${session_id}`);
  }

  async function handleChipClick(index: number) {
    setError(null);
    setBusy({ kind: "chip", index });
    try {
      const { repo } = await connectRepo(TASKBOARD_URL);
      await startSession(repo, BUGS[index].message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start that session. Try again?");
      setBusy(null);
    }
  }

  async function handleCustomConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!customUrl.trim()) return;
    setError(null);
    setBusy({ kind: "custom" });
    try {
      const { repo } = await connectRepo(customUrl.trim());
      setCustomRepo(repo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't connect that repo. Try again?");
    } finally {
      setBusy(null);
    }
  }

  async function handleCustomFirstMessage(message: string) {
    if (!customRepo) return;
    setError(null);
    setBusy({ kind: "custom" });
    try {
      await startSession(customRepo, message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start that session. Try again?");
      setBusy(null);
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <div>
        <h2 className="font-heading text-2xl font-bold sm:text-3xl">Try it on a real bug</h2>
        <p className="mt-1 text-muted-foreground">
          Click a symptom below — Duck connects the sample repo and starts investigating immediately. No typing needed.
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        {BUGS.map((bug, i) => (
          <Chip key={i} disabled={busy !== null} onClick={() => handleChipClick(i)} className="sm:max-w-xs">
            {busy?.kind === "chip" && busy.index === i ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
                Connecting taskboard&hellip;
              </span>
            ) : (
              <span>&ldquo;{bug.label}&rdquo;</span>
            )}
          </Chip>
        ))}
      </div>

      <AnimatePresence>
        {wakingUp && !error && (
          <ErrorBanner message="Waking Duck up — the backend naps when idle, this can take up to a minute on a cold start." />
        )}
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      </AnimatePresence>

      <div className="flex flex-col gap-3 rounded-xl border-2 border-ink/15 bg-paper/60 p-4">
        <p className="text-sm font-semibold text-muted-foreground">Or bring your own public GitHub repo</p>
        {!customRepo ? (
          <form onSubmit={handleCustomConnect} className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <FolderGit2 className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="pl-9"
                disabled={busy?.kind === "custom"}
              />
            </div>
            <Button type="submit" variant="secondary" disabled={busy?.kind === "custom" || !customUrl.trim()}>
              {busy?.kind === "custom" ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <ArrowRight className="size-3.5" aria-hidden />}
              Connect
            </Button>
          </form>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-sm">
              Connected <span className="font-mono font-semibold">{customRepo.owner}/{customRepo.name}</span> — describe the bug:
            </p>
            <WisprInput onSubmit={handleCustomFirstMessage} disabled={busy?.kind === "custom"} />
          </div>
        )}
      </div>
    </section>
  );
}
