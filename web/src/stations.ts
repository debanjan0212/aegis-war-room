// The ten seats in the war room, in the order they speak.
export const STATIONS = [
  { id: "triage", name: "Triage", hue: "investigate", job: "How bad is it, and where?" },
  { id: "signals", name: "Signals", hue: "investigate", job: "Metrics, logs and traces" },
  { id: "changes", name: "Changes", hue: "investigate", job: "What changed just before?" },
  { id: "runbook", name: "Runbook", hue: "investigate", job: "The team's written procedure" },
  { id: "planner", name: "Planner", hue: "plan", job: "Root cause and one proposed fix" },
  { id: "defender", name: "Defender", hue: "defend", job: "Checks the fix against policy" },
  { id: "human", name: "You", hue: "human", job: "Go or no-go" },
  { id: "executor", name: "Executor", hue: "act", job: "Runs only what was approved" },
  { id: "verifier", name: "Verifier", hue: "act", job: "Did it really recover?" },
  { id: "scribe", name: "Scribe", hue: "record", job: "Postmortem and team update" },
] as const;

const HUES: Record<string, string> = {
  investigate: "var(--color-investigate)",
  plan: "var(--color-plan)",
  defend: "var(--color-defend)",
  human: "var(--color-amber)",
  act: "var(--color-act)",
  record: "var(--color-record)",
};

const find = (agent: string) => STATIONS.find((station) => station.id === agent);
export const hueOf = (agent: string) => HUES[find(agent)?.hue ?? "record"];
export const nameOf = (agent: string) => find(agent)?.name ?? "Aegis";
export const OPEN = ["investigating", "awaiting_decision", "executing"];
