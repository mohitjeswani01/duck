/** Synthesizes a short, cheerful "quack" with the Web Audio API — no audio
 * asset to license, just two quick descending square-wave bursts. */
export function playQuack(): void {
  if (typeof window === "undefined") return;
  const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) return;

  const ctx = new AudioContextClass();

  function burst(startAt: number, fromFreq: number, toFreq: number, duration: number) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square";
    osc.frequency.setValueAtTime(fromFreq, startAt);
    osc.frequency.exponentialRampToValueAtTime(toFreq, startAt + duration);
    gain.gain.setValueAtTime(0.0001, startAt);
    gain.gain.exponentialRampToValueAtTime(0.18, startAt + duration * 0.2);
    gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(startAt);
    osc.stop(startAt + duration);
  }

  const now = ctx.currentTime;
  burst(now, 650, 280, 0.14);
  burst(now + 0.16, 600, 260, 0.12);

  setTimeout(() => ctx.close(), 400);
}
