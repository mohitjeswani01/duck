import { FolderGit2 } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { DUCK_GITHUB_URL } from "@/lib/constants";

export function SiteFooter() {
  return (
    <footer className="border-t-2 border-ink/10 px-6 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 text-center text-sm text-muted-foreground sm:flex-row sm:justify-between sm:text-left">
        <div className="flex items-center gap-2">
          <DuckMascot mood="idle" size={22} />
          <span className="font-heading font-bold text-ink">Duck</span>
        </div>
        <p>Built for the No Hands Wispr Challenge by WeMakeDevs and Wispr Flow.</p>
        <div className="flex items-center gap-4">
          <a href={DUCK_GITHUB_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-beak">
            <FolderGit2 className="size-4" aria-hidden />
            GitHub
          </a>
          <span>Made by Mohit Jeswani</span>
        </div>
      </div>
    </footer>
  );
}
