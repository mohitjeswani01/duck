"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { WisprInput } from "@/components/duck/wispr-input";
import { ErrorBanner } from "@/components/duck/error-banner";
import { getRepo, createSession, ApiError, type RepoOut } from "@/lib/api";

export function NewSessionClient({ repoId }: { repoId: string }) {
  const router = useRouter();
  const [repo, setRepo] = useState<RepoOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!repoId) return;
    let cancelled = false;
    getRepo(repoId)
      .then((data) => {
        if (!cancelled) setRepo(data);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Couldn't load that repo.");
      });
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  const missingRepoError = !repoId ? "No repo was connected — go back and connect one first." : null;

  async function handleSubmit(text: string) {
    setSubmitError(null);
    setBusy(true);
    try {
      const { session_id } = await createSession(repoId, text);
      router.push(`/workspace/${session_id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Couldn't start that session. Try again?");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between gap-3 border-b-2 border-ink bg-cream/95 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <DuckMascot mood="idle" size={28} />
          <span className="font-heading text-lg font-extrabold">Duck</span>
        </Link>
        {repo && (
          <a
            href={repo.github_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-paper px-3 py-1 text-xs font-semibold shadow-brutal-sm sm:text-sm"
          >
            <span className="font-mono">{repo.owner}/{repo.name}</span>
            <ExternalLink className="size-3" aria-hidden />
          </a>
        )}
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center gap-6 px-4 py-12 text-center">
        <DuckMascot mood="listening" size={64} />
        <div>
          <h1 className="font-heading text-2xl font-extrabold sm:text-3xl">Now explain your bug out loud.</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {repo ? (
              <>Duck has connected <span className="font-mono font-semibold">{repo.owner}/{repo.name}</span> and is ready to listen.</>
            ) : (
              "Connecting your repo…"
            )}
          </p>
        </div>

        {(missingRepoError ?? loadError) && (
          <ErrorBanner message={missingRepoError ?? loadError ?? ""} className="w-full max-w-md" />
        )}
        {submitError && <ErrorBanner message={submitError} onDismiss={() => setSubmitError(null)} className="w-full max-w-md" />}

        {repo && (
          <WisprInput
            onSubmit={handleSubmit}
            disabled={busy}
            autoFocus
            placeholder="Hold your Wispr key and just talk."
            statusText={busy ? "Connecting you to Duck…" : undefined}
            className="w-full"
          />
        )}
      </main>
    </div>
  );
}
