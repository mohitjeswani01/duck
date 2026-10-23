"use client";

import { FolderGit2 } from "lucide-react";
import { DuckMascot } from "@/components/duck/duck-mascot";
import { DUCK_GITHUB_URL } from "@/lib/constants";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#why-voice", label: "Why voice" },
  { href: "#faq", label: "FAQ" },
];

function scrollTo(e: React.MouseEvent<HTMLAnchorElement>, href: string) {
  e.preventDefault();
  document.querySelector(href)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function SiteNav() {
  return (
    <header className="sticky top-0 z-30 border-b-2 border-ink bg-cream/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3.5">
        <a href="#top" className="flex items-center gap-2" onClick={(e) => scrollTo(e, "#top")}>
          <DuckMascot mood="idle" size={28} />
          <span className="font-heading text-lg font-extrabold">Duck</span>
        </a>

        <nav className="hidden items-center gap-6 text-sm font-semibold sm:flex">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={(e) => scrollTo(e, link.href)} className="hover:text-beak">
              {link.label}
            </a>
          ))}
          <a
            href={DUCK_GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 hover:text-beak"
          >
            <FolderGit2 className="size-4" aria-hidden />
            GitHub
          </a>
        </nav>

        <a
          href="#try-a-bug"
          onClick={(e) => scrollTo(e, "#try-a-bug")}
          className="press-down inline-flex items-center rounded-full border-2 border-ink bg-duck px-4 py-1.5 text-sm font-bold shadow-brutal-sm"
        >
          Try Duck
        </a>
      </div>
    </header>
  );
}
