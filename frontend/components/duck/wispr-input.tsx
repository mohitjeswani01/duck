"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, Send, X } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { cn } from "cn";

const BURST_CHAR_THRESHOLD = 15; // a single change event adding this many chars reads as a paste, not typing
const PAUSE_MS = 2000; // how long to wait after a burst before prompting
const COUNTDOWN_SECONDS = 3;
const AUTO_SEND_STORAGE_KEY = "duck-auto-send-enabled";

const autoSendListeners = new Set<() => void>();
function subscribeAutoSend(callback: () => void) {
  autoSendListeners.add(callback);
  return () => autoSendListeners.delete(callback);
}
function getAutoSendSnapshot() {
  const stored = window.localStorage.getItem(AUTO_SEND_STORAGE_KEY);
  return stored === null ? true : stored === "true";
}
function getAutoSendServerSnapshot() {
  return true;
}
function setAutoSendStored(value: boolean) {
  window.localStorage.setItem(AUTO_SEND_STORAGE_KEY, String(value));
  autoSendListeners.forEach((l) => l());
}

interface WisprInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  autoFocus?: boolean;
  placeholder?: string;
  statusText?: string;
  className?: string;
}

export function WisprInput({
  onSubmit,
  disabled = false,
  autoFocus = false,
  placeholder = "Hold your Wispr key and just talk.",
  statusText,
  className,
}: WisprInputProps) {
  const [value, setValue] = useState("");
  const autoSendEnabled = useSyncExternalStore(subscribeAutoSend, getAutoSendSnapshot, getAutoSendServerSnapshot);
  const [pendingAutoSend, setPendingAutoSend] = useState(false);
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);

  const pauseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    return () => {
      if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, []);

  function cancelPendingAutoSend() {
    if (pauseTimerRef.current) {
      clearTimeout(pauseTimerRef.current);
      pauseTimerRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    setPendingAutoSend(false);
  }

  function startAutoSendCountdown() {
    setPendingAutoSend(true);
    setCountdown(COUNTDOWN_SECONDS);
    countdownIntervalRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
          submit();
          return COUNTDOWN_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const newValue = e.target.value;
    const delta = newValue.length - value.length;
    setValue(newValue);
    cancelPendingAutoSend();

    if (pauseTimerRef.current) {
      clearTimeout(pauseTimerRef.current);
      pauseTimerRef.current = null;
    }

    if (autoSendEnabled && !disabled && delta >= BURST_CHAR_THRESHOLD && newValue.trim().length > 0) {
      pauseTimerRef.current = setTimeout(startAutoSendCountdown, PAUSE_MS);
    }
  }

  function submit() {
    cancelPendingAutoSend();
    const text = value.trim();
    if (!text || disabled) return;
    onSubmit(text);
    setValue("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  }

  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="relative">
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          autoFocus={autoFocus}
          placeholder={placeholder}
          disabled={disabled}
          rows={5}
          className="min-h-36 resize-none pb-10 text-lg leading-relaxed sm:min-h-44 sm:text-xl"
        />

        <div className="absolute bottom-3 left-4 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
          <Mic className="size-3.5" aria-hidden />
          <span>{wordCount} {wordCount === 1 ? "word" : "words"}</span>
        </div>

        <div className="absolute bottom-3 right-3">
          <Button type="button" size="sm" disabled={disabled || !value.trim()} onClick={submit} aria-label="Send to Duck">
            <Send className="size-3.5" aria-hidden />
            Send
          </Button>
        </div>

        <AnimatePresence>
          {pendingAutoSend && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.18 }}
              className="absolute inset-x-3 -top-3 flex items-center justify-between gap-3 rounded-lg border-2 border-ink bg-duck px-3 py-2 text-sm font-semibold text-ink shadow-brutal-sm"
            >
              <span>Sounds like you&apos;re done — sending in {countdown}&hellip;</span>
              <button
                type="button"
                onClick={cancelPendingAutoSend}
                className="press-down inline-flex items-center gap-1 rounded-md border-2 border-ink bg-paper px-2 py-1 text-xs font-bold"
              >
                <X className="size-3" aria-hidden />
                Cancel
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-muted-foreground">
        <label className="inline-flex items-center gap-1.5 select-none">
          <input
            type="checkbox"
            checked={autoSendEnabled}
            onChange={(e) => {
              setAutoSendStored(e.target.checked);
              if (!e.target.checked) cancelPendingAutoSend();
            }}
            className="size-3.5 accent-[var(--color-duck)]"
          />
          auto-send after a Wispr burst
        </label>
        <span className="font-mono">⌘/Ctrl + Enter to send</span>
      </div>

      {statusText && (
        <motion.p
          key={statusText}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="px-1 text-sm font-medium text-ink/70"
        >
          {statusText}
        </motion.p>
      )}
    </div>
  );
}
