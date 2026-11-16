// The desk on the right: what you can do right now.
// Before an incident: start one. During: watch. At the gate: go or no-go. After: the write-up.
import { useState } from "react";
import type { Config, Gate, Result, Step } from "../types";

type Props = {
  config: Config;
  status: string;
  steps: Step[];
  gate: Gate | null;
  result: Result;
  armed: boolean;
  busy: boolean;
  by: string;
  onBy: (name: string) => void;
  onStart: (scenario: string) => void;
  onScanLive: () => void;
  onDecide: (decision: "go" | "no-go", note: string) => void;
  onReset: () => void;
};

const OUTCOMES: Record<string, { title: string; tone: string }> = {
  resolved: { title: "Resolved", tone: "bg-go text-white" },
  not_resolved: { title: "Fix applied, not recovered", tone: "bg-amber text-ink" },
  rejected: { title: "No-go. Nothing was changed", tone: "bg-strip text-ink" },
  escalated: { title: "Handed to a human. Nothing was changed", tone: "bg-amber text-ink" },
  failed: { title: "The flow stopped with an error", tone: "bg-nogo text-white" },
};

function Start({ config, busy, onStart, onScanLive }: Pick<Props, "config" | "busy" | "onStart" | "onScanLive">) {
  if (config.source !== "simulator") {
    return (
      <section>
        <h2 className="font-display text-3xl">Watching the live system</h2>
        <p className="mt-2 text-chalk-dim">Connected to {config.source}. Break something there, wait a minute for the numbers to move, then scan.</p>
        <button className="mt-4 w-full rounded-md bg-chalk px-4 py-3 text-lg font-bold text-ink" disabled={busy} onClick={onScanLive}>
          Scan the live system now
        </button>
      </section>
    );
  }
  return (
    <section>
      <h2 className="font-display text-5xl leading-none">All quiet. Start a drill</h2>
      <p className="mt-3 max-w-[64ch] text-chalk-dim">
        Pick an incident. The agents investigate and report in along the row above, the defender checks their plan, and nothing is changed
        until you say go. These run on the built-in simulator, so nothing real can break.
      </p>
      <ul className="mt-6 grid gap-4 lg:grid-cols-3">
        {config.scenarios.map((scenario) => (
          <li key={scenario.id} className="strip flex flex-col" style={{ borderLeftColor: "var(--color-amber)" }}>
            <h3 className="font-display text-3xl leading-tight">{scenario.title}</h3>
            <p className="mt-1 mb-4 text-ink-soft">{scenario.story}</p>
            <button
              className="mt-auto self-start rounded-md bg-ink px-4 py-2 font-bold text-strip"
              disabled={busy}
              onClick={() => onStart(scenario.id)}
            >
              Start this incident
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Numbers({ steps }: { steps: Step[] }) {
  const metrics = [...steps].reverse().find((step) => step.data.metrics?.error_rate !== undefined)?.data.metrics;
  if (!metrics) return null;
  return (
    <dl className="mt-4 grid grid-cols-2 gap-3">
      <div className="rounded-md bg-well p-3">
        <dt className="text-sm text-chalk-dim">Error rate</dt>
        <dd className="font-display text-4xl tabular-nums">{(metrics.error_rate * 100).toFixed(1)}%</dd>
      </div>
      <div className="rounded-md bg-well p-3">
        <dt className="text-sm text-chalk-dim">Slowest 5% of requests</dt>
        <dd className="font-display text-4xl tabular-nums">{Math.round(metrics.p95_ms ?? 0)} ms</dd>
      </div>
    </dl>
  );
}

function Decide({ gate, armed, busy, by, onBy, onDecide }: Pick<Props, "armed" | "busy" | "by" | "onBy" | "onDecide"> & { gate: Gate }) {
  const [note, setNote] = useState("");
  const failed = gate.defender.checks.filter((check) => !check.ok);
  return (
    <section aria-label="Your decision">
      <p className="text-amber">Your call</p>
      <h2 className="mt-1 font-display text-4xl leading-[1.05] first-letter:uppercase">{gate.plan_text}?</h2>
      <p className="mt-3">{gate.plan.root_cause}</p>
      <dl className="mt-3 flex flex-col gap-1 border-y border-rule py-3 text-chalk-dim">
        <div>
          <dt className="inline text-chalk">Defender: </dt>
          <dd className="inline">
            {gate.defender.verdict}, risk {gate.defender.risk}. {gate.defender.checks.length - failed.length} of {gate.defender.checks.length} checks
            pass.{failed.map((check) => ` Weak point: ${check.check}.`)}
          </dd>
        </div>
        {gate.defender.quarantined > 0 && (
          <div>
            <dt className="inline text-chalk">Attack attempt: </dt>
            <dd className="inline">
              {gate.defender.quarantined === 1 ? "1 injected log line was" : `${gate.defender.quarantined} injected log lines were`} removed before
              planning.
            </dd>
          </div>
        )}
        <div>
          <dt className="inline text-chalk">To undo: </dt>
          <dd className="inline">{gate.plan.undo}</dd>
        </div>
      </dl>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <label className="block text-sm text-chalk-dim">
          Deciding as
          <input className="field mt-1 block w-full" value={by} onChange={(event) => onBy(event.target.value)} placeholder="Your name" maxLength={80} />
        </label>
        <label className="block text-sm text-chalk-dim">
          Note (optional)
          <input className="field mt-1 block w-full" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} />
        </label>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <button
          className={`rounded-md bg-go px-4 py-5 font-display text-4xl text-white ${armed ? "ring-4 ring-amber" : ""}`}
          disabled={busy}
          onClick={() => onDecide("go", note)}
        >
          {armed ? "Confirm go" : "Go"}
        </button>
        <button className="rounded-md bg-nogo px-4 py-5 font-display text-4xl text-white" disabled={busy} onClick={() => onDecide("no-go", note)}>
          No-go
        </button>
      </div>
      <p className="mt-3 text-sm text-chalk-dim">
        By voice: say “no-go” to stop at once. Say “go”, then “confirm”, to proceed. Acting always takes two steps; stopping takes one.
      </p>
    </section>
  );
}

function Outcome({ result, status, onReset }: Pick<Props, "result" | "status" | "onReset">) {
  const outcome = OUTCOMES[status] ?? OUTCOMES.failed;
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(result.stakeholder_update ?? "");
    setCopied(true);
  };
  return (
    <section>
      <h2 className={`rounded-md px-4 py-3 font-display text-3xl leading-tight ${outcome.tone}`}>{outcome.title}</h2>
      {result.stakeholder_update && (
        <>
          <h3 className="mt-5 font-display text-2xl">Message for the team</h3>
          <p className="mt-1 rounded-md bg-well p-3">{result.stakeholder_update}</p>
          <button className="quiet-button mt-2" onClick={copy}>
            {copied ? "Copied" : "Copy message"}
          </button>
        </>
      )}
      {result.postmortem && (
        <details className="mt-5">
          <summary className="cursor-pointer font-display text-2xl">Postmortem draft</summary>
          <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-well p-3 font-sans text-[0.95rem]">{result.postmortem}</pre>
        </details>
      )}
      <button className="quiet-button mt-6 w-full" onClick={onReset}>
        Back to the start
      </button>
    </section>
  );
}

export default function Desk(props: Props) {
  const { status, gate, steps } = props;
  if (status === "idle") return <Start {...props} />;
  if (status === "awaiting_decision" && gate) return <Decide {...props} gate={gate} />;
  if (status === "investigating" || status === "executing") {
    return (
      <section>
        <h2 className="font-display text-3xl">{status === "executing" ? "Carrying out your decision" : "The agents are investigating"}</h2>
        <p className="mt-2 text-chalk-dim">
          {status === "executing" ? "Only the approved action runs. Then the numbers are checked again." : "Nothing will be changed without your go."}
        </p>
        <Numbers steps={steps} />
      </section>
    );
  }
  return <Outcome {...props} />;
}
