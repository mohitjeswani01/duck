"use client";

import { useState } from "react";
import { Check, Loader2, ThumbsDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/textarea";

interface FixDecisionProps {
  onAccept: () => void;
  onReject: (feedback?: string) => void;
  busy: boolean;
}

export function FixDecision({ onAccept, onReject, busy }: FixDecisionProps) {
  const [feedback, setFeedback] = useState("");
  const [rejecting, setRejecting] = useState(false);

  return (
    <div className="flex flex-col gap-2 rounded-xl border-2 border-ink bg-paper p-3 shadow-brutal-sm">
      {!rejecting ? (
        <div className="flex gap-2">
          <Button className="flex-1" size="lg" disabled={busy} onClick={onAccept}>
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Check className="size-4" aria-hidden />}
            Accept fix
          </Button>
          <Button className="flex-1" variant="outline" size="lg" disabled={busy} onClick={() => setRejecting(true)}>
            <ThumbsDown className="size-4" aria-hidden />
            This doesn&apos;t fix it
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Input
            autoFocus
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional: what still looks wrong?"
            disabled={busy}
          />
          <div className="flex gap-2">
            <Button
              className="flex-1"
              variant="destructive"
              disabled={busy}
              onClick={() => {
                onReject(feedback || undefined);
                setRejecting(false);
                setFeedback("");
              }}
            >
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : "Send back to Duck"}
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
