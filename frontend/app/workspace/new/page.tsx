import type { Metadata } from "next";
import { NewSessionClient } from "@/components/workspace/new-session-client";

export const metadata: Metadata = {
  title: "New session",
};

// Reads a dynamic search param (repoId) and talks to the backend — nothing
// here is prerenderable, same reasoning as /workspace/[id].
export const instant = false;

export default async function NewSessionPage({ searchParams }: PageProps<"/workspace/new">) {
  const params = await searchParams;
  const repoId = typeof params.repoId === "string" ? params.repoId : "";
  return <NewSessionClient repoId={repoId} />;
}
