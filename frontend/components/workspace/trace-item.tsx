import { motion } from "framer-motion";
import { FileText, FolderTree, Search } from "lucide-react";
import type { ToolCallEvent } from "@/lib/events";

const TOOL_META: Record<ToolCallEvent["tool"], { icon: typeof FileText; verb: string }> = {
  read_file: { icon: FileText, verb: "Duck is reading" },
  search_code: { icon: Search, verb: "Duck is searching for" },
  list_files: { icon: FolderTree, verb: "Duck is listing files in" },
};

export function TraceItem({ event }: { event: ToolCallEvent }) {
  const meta = TOOL_META[event.tool];
  const Icon = meta.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-2 border-l-2 border-beak/50 py-1 pl-3 text-sm"
    >
      <Icon className="size-3.5 shrink-0 text-beak" aria-hidden />
      <span className="text-ink/70">{meta.verb}</span>
      <span className="truncate font-mono text-xs font-semibold text-ink sm:text-sm">{event.detail}</span>
    </motion.div>
  );
}
