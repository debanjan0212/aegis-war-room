// The row of stations across the top, like a mission-control go / no-go poll:
// each seat lights up when it has reported, and "You" lights up when it is your call.
import { hueOf, OPEN, STATIONS } from "../stations";
import type { Step } from "../types";

type Props = { steps: Step[]; status: string };

function stateOf(id: string, steps: Step[], status: string): { state: string; word: string; color: string } {
  const mine = steps.filter((step) => step.agent === id);
  const last = steps[steps.length - 1];
  if (id === "human") {
    const decision = mine.find((step) => step.kind === "decision")?.data.decision;
    if (decision === "go") return { state: "reported", word: "go", color: "var(--color-act)" };
    if (decision === "no-go") return { state: "reported", word: "no-go", color: "var(--color-nogo)" };
    if (status === "awaiting_decision") return { state: "live", word: "your call", color: hueOf(id) };
    return { state: "idle", word: "waiting", color: hueOf(id) };
  }
  if (!mine.length) return { state: "idle", word: "waiting", color: hueOf(id) };
  if (mine.some((step) => ["block", "error"].includes(step.kind))) return { state: "flagged", word: "stopped it", color: "var(--color-nogo)" };
  if (mine.some((step) => step.kind === "warn")) return { state: "flagged", word: "flagged", color: "var(--color-amber)" };
  const live = OPEN.includes(status) && status !== "awaiting_decision" && last?.agent === id;
  return { state: live ? "live" : "reported", word: live ? "reporting" : "reported", color: hueOf(id) };
}

export default function Stations({ steps, status }: Props) {
  return (
    <ol className="flex gap-1 overflow-x-auto border-b border-rule px-4 py-3 sm:px-6" aria-label="Stations">
      {STATIONS.map((station) => {
        const { state, word, color } = stateOf(station.id, steps, status);
        return (
          <li key={station.id} className="flex min-w-24 flex-1 flex-col items-center gap-1 text-center" title={station.job}>
            <span
              className="lamp size-5 rounded-full border-2"
              data-state={state}
              style={{ color, borderColor: color, background: state === "idle" ? "transparent" : color }}
            />
            <span className={`font-display text-lg leading-none ${state === "idle" ? "text-chalk-dim" : "text-chalk"}`}>{station.name}</span>
            <span className="text-sm leading-none text-chalk-dim">{word}</span>
          </li>
        );
      })}
    </ol>
  );
}
