// The crew, in the order they work, and how to tell what each one is doing right now.
import type { Step } from "./types";

export const OPEN = ["investigating", "awaiting_decision", "executing"];

// A small line icon per bay, drawn on a 24 x 24 grid.
export const CREW = [
  { id: "triage", name: "Triage", job: "How bad is it, and where?", about: "It decides how bad the incident is and which service is hurt.", icon: "M2 12h4l3-7 4 14 3-7h6" },
  { id: "signals", name: "Signals", job: "Metrics, logs and traces", about: "It reads the metrics, logs and traces, and quarantines any log line that tries to give the AI orders.", icon: "M5 20v-6M12 20V5M19 20V10" },
  { id: "changes", name: "Changes", job: "What changed just before?", about: "It finds what changed just before the trouble started.", icon: "M6 3v18M6 13c7 0 12-3 12-8M18 3v4" },
  { id: "runbook", name: "Runbook", job: "The team's written procedure", about: "It finds the team\'s written procedure that fits.", icon: "M4 5h6a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H4zM20 5h-6a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h6z" },
  { id: "planner", name: "Planner", job: "Root cause and one fix", about: "It names the root cause and proposes one fix, chosen from an allowed list.", icon: "M12 3a9 9 0 1 0 .01 0M12 8a4 4 0 1 0 .01 0M12 11.5v1" },
  { id: "defender", name: "Defender", job: "Checks the fix against the rules", about: "It checks every plan against fixed rules. It uses no AI, so it cannot be talked into anything.", icon: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" },
  { id: "human", name: "You", job: "Go or no-go", about: "Nothing is changed until you say go.", icon: "M12 4a4 4 0 1 0 .01 0M4 21c1-4.5 4.5-6.5 8-6.5s7 2 8 6.5" },
  { id: "executor", name: "Executor", job: "Runs only what you approved", about: "It carries out the fix you approved, and nothing else.", icon: "M13 2L4 14h7l-1 8 9-12h-7z" },
  { id: "verifier", name: "Verifier", job: "Did it really recover?", about: "It checks the numbers again after the fix, because applied is not the same as worked.", icon: "M4 12.5l5 5L20 6" },
  { id: "scribe", name: "Scribe", job: "Postmortem and team update", about: "It writes the postmortem and the message for the team, from the record.", icon: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4" },
  { id: "codeguard", name: "Code Guard", job: "Scans this code for weaknesses", about: "It scans this code for vulnerabilities and leaked secrets.", icon: "M8 6l-6 6 6 6M16 6l6 6-6 6" },
] as const;

export type BayState = "asleep" | "standby" | "working" | "done" | "flagged" | "blocked" | "yourcall" | "ready";
export type Room = { status: string; steps: Step[]; working: string[]; scanning: boolean; scanned: boolean };

const KIND_STATE: Record<string, BayState> = { block: "blocked", error: "blocked", warn: "flagged" };

/** One bay's state, and the word shown under it. Words, not only colours, so it reads at a glance. */
export function bayState(id: string, room: Room): { state: BayState; label: string } {
  if (id === "codeguard") {
    if (room.scanning) return { state: "working", label: "Scanning" };
    return room.scanned ? { state: "done", label: "Scanned" } : { state: "asleep", label: "Asleep" };
  }
  if (id === "human") {
    if (room.status === "awaiting_decision") return { state: "yourcall", label: "Your call" };
    const said = [...room.steps].reverse().find((step) => step.agent === "human");
    if (said) return { state: "done", label: said.data.decision === "go" ? "Said go" : "Said no-go" };
    return { state: "ready", label: "Here" };
  }
  if (room.status === "idle") return { state: "asleep", label: "Asleep" };
  if (room.working.includes(id)) return { state: "working", label: "Working" };
  const last = [...room.steps].reverse().find((step) => step.agent === id);
  if (last) {
    const state = KIND_STATE[last.kind] ?? "done";
    return { state, label: state === "blocked" ? (last.kind === "error" ? "Error" : "Blocked") : state === "flagged" ? "Flagged" : "Done" };
  }
  return OPEN.includes(room.status) ? { state: "standby", label: "Standing by" } : { state: "asleep", label: "Not needed" };
}

export const nameOf = (agent: string) => CREW.find((member) => member.id === agent)?.name ?? (agent === "aegis" ? "Aegis" : agent);
export const iconOf = (agent: string) => CREW.find((member) => member.id === agent)?.icon ?? "";
