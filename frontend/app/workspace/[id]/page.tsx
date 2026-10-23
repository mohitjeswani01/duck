import type { Metadata } from "next";
import { WorkspaceClient } from "@/components/workspace/workspace-client";

export const metadata: Metadata = {
  title: "Workspace",
};

// Every session id is unique and the page is fully client-rendered (session
// state + SSE), so there's nothing to prerender a static shell for — allow
// this route to block instead of fighting Cache Components over it.
export const instant = false;

export default async function WorkspacePage({ params }: PageProps<"/workspace/[id]">) {
  const { id } = await params;
  return <WorkspaceClient sessionId={id} />;
}
