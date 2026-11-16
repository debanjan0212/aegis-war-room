// Voice in and voice out, using what the browser already has.
import type { Voice } from "./types";

export type Intent = "go" | "no-go" | "confirm" | "brief";

/** The decision words, matched word for word and never by a model. "No-go" is checked first so it always wins. */
export function intentOf(heard: string): Intent | null {
  const text = heard.toLowerCase();
  if (/\bno[\s-]?go\b|\b(don'?t|do not|not)\s+go\b|\breject\b|\babort\b|\bcancel\b|\bstop\b/.test(text)) return "no-go";
  if (/\bconfirm(ed)?\b/.test(text)) return "confirm";
  if (/\bbrief\b|\brepeat\b|\bagain\b/.test(text)) return "brief";
  if (/^\s*(go|go ahead|approved?|proceed)\W*$/.test(text)) return "go";
  return null;
}

let speaking = false;
let quietUntil = 0; // ignore the microphone until this time, so the assistant never hears itself
const watchers = new Set<(on: boolean) => void>();

/** Be told when the assistant starts and stops speaking: the core pulses while it talks. */
export function onSpeaking(watch: (on: boolean) => void): () => void {
  watchers.add(watch);
  return () => watchers.delete(watch);
}
const setSpeaking = (on: boolean) => {
  speaking = on;
  watchers.forEach((watch) => watch(on));
};

if ("speechSynthesis" in window) speechSynthesis.getVoices(); // browsers load their voice list lazily; ask early

export function speak(text: string, voice?: Voice): void {
  if (!("speechSynthesis" in window) || !text) return;
  speechSynthesis.cancel();
  const line = new SpeechSynthesisUtterance(text);
  const installed = speechSynthesis.getVoices();
  const wanted = voice?.prefer?.map((name) => installed.find((v) => v.name.includes(name))).find(Boolean);
  const chosen = wanted ?? installed.find((v) => v.lang === voice?.lang) ?? installed.find((v) => v.lang.startsWith("en"));
  if (chosen) line.voice = chosen;
  line.lang = chosen?.lang ?? voice?.lang ?? "en-GB";
  line.rate = voice?.rate ?? 1;
  line.pitch = voice?.pitch ?? 1;
  line.onstart = () => setSpeaking(true);
  line.onend = line.onerror = () => {
    setSpeaking(false);
    quietUntil = Date.now() + 600;
  };
  speechSynthesis.speak(line);
}

export function stopSpeaking(): void {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  setSpeaking(false);
}

const Recognition = () => (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
export const canListen = () => Boolean(Recognition());

/** Keep listening until stopped. Everything heard goes to onHeard, except while the assistant itself is talking. */
export function startListening(onHeard: (text: string) => void): (() => void) | null {
  const Ear = Recognition();
  if (!Ear) return null;
  const ear = new Ear();
  ear.continuous = true;
  ear.lang = navigator.language || "en-GB";
  let wanted = true;
  ear.onresult = (event: any) => {
    const text: string = event.results[event.results.length - 1][0].transcript.trim();
    if (speaking || Date.now() < quietUntil || !text) return;
    onHeard(text);
  };
  ear.onend = () => {
    if (wanted) try { ear.start(); } catch { /* already starting */ } // the browser stops after a silence; keep going
  };
  ear.start();
  return () => {
    wanted = false;
    ear.stop();
  };
}

/** Listen for one sentence (the microphone button). */
export function listenOnce(onHeard: (text: string) => void, onDone: () => void): (() => void) | null {
  const Ear = Recognition();
  if (!Ear) return null;
  stopSpeaking();
  const ear = new Ear();
  ear.continuous = false;
  ear.lang = navigator.language || "en-GB";
  ear.onresult = (event: any) => {
    const text: string = event.results[0][0].transcript.trim();
    if (text) onHeard(text);
  };
  ear.onend = onDone;
  ear.start();
  return () => ear.stop();
}
