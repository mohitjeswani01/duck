import { FileCode2 } from "lucide-react";

interface DiffRow {
  type: "add" | "remove" | "context" | "hunk" | "file";
  content: string;
  oldNum?: number;
  newNum?: number;
}

function parseDiff(diffText: string): DiffRow[] {
  const rows: DiffRow[] = [];
  let oldNum = 0;
  let newNum = 0;

  for (const raw of diffText.split("\n")) {
    if (raw.startsWith("---") || raw.startsWith("+++")) {
      rows.push({ type: "file", content: raw });
      continue;
    }
    if (raw.startsWith("@@")) {
      const match = raw.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldNum = parseInt(match[1], 10);
        newNum = parseInt(match[2], 10);
      }
      rows.push({ type: "hunk", content: raw });
      continue;
    }
    if (raw.startsWith("+")) {
      rows.push({ type: "add", content: raw.slice(1), newNum });
      newNum++;
      continue;
    }
    if (raw.startsWith("-")) {
      rows.push({ type: "remove", content: raw.slice(1), oldNum });
      oldNum++;
      continue;
    }
    if (raw === "") continue;
    rows.push({ type: "context", content: raw.startsWith(" ") ? raw.slice(1) : raw, oldNum, newNum });
    oldNum++;
    newNum++;
  }

  return rows;
}

export function DiffViewer({ filePath, diffText }: { filePath: string; diffText: string }) {
  const rows = parseDiff(diffText);

  return (
    <div className="overflow-hidden rounded-xl border-2 border-ink shadow-brutal-sm">
      <div className="flex items-center gap-2 border-b-2 border-ink bg-ink px-3 py-2 text-cream">
        <FileCode2 className="size-3.5 shrink-0" aria-hidden />
        <span className="truncate font-mono text-xs font-semibold sm:text-sm">{filePath}</span>
      </div>
      <div className="overflow-x-auto bg-paper">
        <pre className="font-mono text-xs leading-relaxed sm:text-sm">
          {rows.map((row, i) => {
            if (row.type === "file") return null;
            if (row.type === "hunk") {
              return (
                <div key={i} className="bg-muted px-3 py-0.5 text-muted-foreground">
                  {row.content}
                </div>
              );
            }
            const bg = row.type === "add" ? "bg-diff-add-bg text-diff-add" : row.type === "remove" ? "bg-diff-remove-bg text-diff-remove" : "text-ink";
            const prefix = row.type === "add" ? "+" : row.type === "remove" ? "−" : " ";
            return (
              <div key={i} className={`flex ${bg}`}>
                <span className="w-9 shrink-0 select-none px-1 text-right text-muted-foreground">{row.oldNum ?? ""}</span>
                <span className="w-9 shrink-0 select-none px-1 text-right text-muted-foreground">{row.newNum ?? ""}</span>
                <span className="w-4 shrink-0 select-none text-center font-bold">{prefix}</span>
                <span className="flex-1 whitespace-pre-wrap break-all pr-3">{row.content}</span>
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
}
