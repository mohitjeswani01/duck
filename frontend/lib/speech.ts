"use client";

/** Thin wrapper around the browser's SpeechSynthesis API — "the rubber duck
 * literally talks back." Only ever called with short text (a question, a
 * one-line hypothesis, the resolved summary); never fed code or file paths. */

let cachedVoice: SpeechSynthesisVoice | null | undefined;

function pickVoice(): SpeechSynthesisVoice | null {
  if (cachedVoice !== undefined) return cachedVoice;
  if (typeof window === "undefined" || !window.speechSynthesis) {
    cachedVoice = null;
    return cachedVoice;
  }
  const voices = window.speechSynthesis.getVoices();
  const english = voices.filter((v) => v.lang.startsWith("en"));
  const preferred =
    english.find((v) => /\b(natural|online|neural)\b/i.test(v.name)) ??
    english.find((v) => v.name.includes("Google") && v.lang === "en-US") ??
    english.find((v) => v.default) ??
    english[0] ??
    voices[0] ??
    null;
  cachedVoice = preferred ?? null;
  return cachedVoice;
}

if (typeof window !== "undefined" && window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () => {
    cachedVoice = undefined;
  };
}

export function speak(text: string) {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) utterance.voice = voice;
  utterance.rate = 1.02;
  utterance.pitch = 1.05;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}
