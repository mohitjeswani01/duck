"use client";

import { useSyncExternalStore } from "react";
import { Volume2, VolumeX } from "lucide-react";

const STORAGE_KEY = "duck-sound-enabled";
const listeners = new Set<() => void>();

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function getSnapshot() {
  return window.localStorage.getItem(STORAGE_KEY) === "true";
}

function getServerSnapshot() {
  return false;
}

export function useSoundEnabled() {
  const enabled = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  function update(value: boolean) {
    window.localStorage.setItem(STORAGE_KEY, String(value));
    listeners.forEach((l) => l());
  }

  return { enabled, setEnabled: update };
}

export function SoundToggle({ enabled, onChange }: { enabled: boolean; onChange: (value: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!enabled)}
      aria-pressed={enabled}
      aria-label={enabled ? "Mute Duck's quack" : "Unmute Duck's quack"}
      title={enabled ? "Quack sound on" : "Quack sound off"}
      className="press-down inline-flex size-8 items-center justify-center rounded-full border-2 border-ink bg-paper shadow-brutal-sm"
    >
      {enabled ? <Volume2 className="size-4" aria-hidden /> : <VolumeX className="size-4" aria-hidden />}
    </button>
  );
}
