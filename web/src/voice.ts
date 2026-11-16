// Voice in and voice out, using what the browser already has. No audio leaves the machine through this file.
import type { Voice } from "./types";

export type Intent = "go" | "no-go" | "confirm" | "brief";

/** Turn what was heard into one of four commands, or nothing. "No-go" is checked first so it always wins. */
export function intentOf(heard: string): Intent | null {
  const text = heard.toLowerCase();
  if (/\bno[\s-]?go\b|\b(don'?t|do not|not)\s+go\b|\breject\b|\babort\b|\bcancel\b|\bstop\b/.test(text)) return "no-go";
  if (/\bconfirm(ed)?\b/.test(text)) return "confirm";
  if (/\bbrief\b|\bstatus\b|\brepeat\b|\bagain\b/.test(text)) return "brief";
  if (/\bgo\b|\bapproved?\b|\bproceed\b/.test(text)) return "go";
  return null;
}

let speaking = false;
let quietUntil = 0; // ignore the microphone until this time, so the assistant never hears itself say "go"

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
  speaking = true;
  line.onend = line.onerror = () => {
    speaking = false;
    quietUntil = Date.now() + 600;
  };
  speechSynthesis.speak(line);
}

export function stopSpeaking(): void {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

export const canListen = () => "SpeechRecognition" in window || "webkitSpeechRecognition" in window;

/** Start listening. Returns a function that stops it, or null when this browser cannot listen (use Chrome or Edge). */
export function startListening(onHeard: (text: string, intent: Intent | null) => void): (() => void) | null {
  const Recognition = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
  if (!Recognition) return null;
  const ear = new Recognition();
  ear.continuous = true;
  ear.lang = navigator.language || "en-GB";
  let wanted = true;
  ear.onresult = (event: any) => {
    const text: string = event.results[event.results.length - 1][0].transcript.trim();
    if (speaking || Date.now() < quietUntil) return;
    onHeard(text, intentOf(text));
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
