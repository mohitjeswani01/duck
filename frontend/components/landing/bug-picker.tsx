"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { ArrowRight, FolderGit2, Info, Loader2 } from "lucide-react";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/duck/error-banner";
import { useSlowRequestNotice } from "@/hooks/use-slow-request-notice";
import { TASKBOARD_GITHUB_URL } from "@/lib/constants";
import { connectRepo, createSession, ApiError, type RepoOut } from "@/lib/api";

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
  const wakingUp = useSlowRequestNotice(busy !== null);

  async function startSession(repo: RepoOut, message: string) {
    const { session_id } = await createSession(repo.id, message);
    router.push(`/workspace/${session_id}`);
  }

  async function handleChipClick(index: number) {
    setError(null);
    setBusy({ kind: "chip", index });
    try {
      const { repo } = await connectRepo(TASKBOARD_GITHUB_URL);
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
      router.push(`/workspace/new?repoId=${repo.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't connect that repo. Try again?");
      setBusy(null);
    }
  }

  return (
    <section id="try-a-bug" className="flex flex-col gap-5 pt-4">
      <div>
        <h2 className="font-heading text-2xl font-bold sm:text-3xl">Try it on a real bug</h2>
        <p className="mt-1 text-muted-foreground">
          Click a symptom below — Duck connects the sample repo and starts investigating immediately. No typing needed.
        </p>
      </div>

      <div className="flex items-start gap-2.5 rounded-xl border-2 border-ink/15 bg-paper/60 px-4 py-3">
        <Info className="mt-0.5 size-4 shrink-0 text-beak" aria-hidden />
        <p className="text-sm text-ink/80">
          These three symptoms come from <span className="font-mono font-semibold">taskboard</span>, a small task-manager app built
          for this demo with three real bugs planted in it. Pick one and watch Duck find it — no setup needed.{" "}
          <a
            href={TASKBOARD_GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="font-semibold underline decoration-2 underline-offset-2 hover:text-beak"
          >
            View taskboard on GitHub →
          </a>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {BUGS.map((bug, i) => (
          <Chip
            key={i}
            disabled={busy !== null}
            onClick={() => handleChipClick(i)}
            className="h-full min-h-[96px] w-full items-center justify-center rounded-2xl px-4 py-3 text-center text-sm leading-snug whitespace-normal"
          >
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

      <div className="flex flex-col gap-3 rounded-xl border-2 border-ink bg-paper p-5 shadow-brutal-sm">
        <div>
          <h3 className="font-heading text-lg font-bold">&hellip;or debug your own repo</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Works with any public GitHub repo, small to medium sized — up to ~500 files.
          </p>
        </div>
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
      </div>
    </section>
  );
}
