// The conversation: you, Aegis, the crew's reports, and the go / no-go, in one thread.
// All text is shown as plain text, never as HTML, so nothing an agent or a log says can run in the page.
import { useState } from "react";
import { iconOf, nameOf } from "../stations";
import type { Check, Drill, Gate, Result, ScanReport, Step } from "../types";

export type Entry =
  | { kind: "you"; id: string; ts: number; text: string }
  | { kind: "aegis"; id: string; ts: number; text: string; by?: string }
  | { kind: "drill"; id: string; ts: number; results: Drill[] }
  | { kind: "scan"; id: string; ts: number; report: ScanReport | null; problem: string }
  | { kind: "audit"; id: string; ts: number; ok: boolean; detail: string }
  | { kind: "outcome"; id: string; ts: number; status: string; result: Result };

const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });

function Icon({ agent }: { agent: string }) {
  const d = iconOf(agent);
  if (!d) return null;
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Details({ step }: { step: Step }) {
  const { abnormal, quarantined, checks, steps } = step.data;
  return (
    <>
      {Array.isArray(abnormal) && abnormal.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-dim">
          {abnormal.map((fact: string) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
      {Array.isArray(quarantined) && (
        <details className="mt-1">
          <summary className="cursor-pointer text-flag">Show what was quarantined</summary>
          {quarantined.map((item: { text: string; reasons: string[] }) => (
            <div key={item.text} className="mt-2 rounded-lg border border-flare/40 bg-night p-2">
              <p className="break-words font-display text-sm">{item.text}</p>
              <p className="mt-1 text-sm text-dim">Why: it {item.reasons.join(", and it ")}.</p>
            </div>
          ))}
        </details>
      )}
      {Array.isArray(checks) && (
        <details className="mt-1">
          <summary className="cursor-pointer text-dim">Show the {checks.length} checks</summary>
          <ul className="mt-1 text-sm">
            {checks.map((check: Check) => (
              <li key={check.check} className={check.ok ? "text-dim" : "text-flare"}>
                {check.ok ? "Pass" : "Fail"}: {check.check} ({check.detail})
              </li>
            ))}
          </ul>
        </details>
      )}
      {Array.isArray(steps) && steps.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-dim">Show the runbook steps</summary>
          <ul className="mt-1 text-sm text-dim">
            {steps.map((line: string) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function Report({ step }: { step: Step }) {
  return (
    <div className="report" data-kind={step.kind}>
      <div className="flex items-center gap-2" style={{ color: "var(--tone)" }}>
        <Icon agent={step.agent} />
        <span className="font-display font-semibold text-text">{nameOf(step.agent)}</span>
        <span className="ml-auto text-xs text-dim tabular-nums">
          {step.data.answered_by && <span className="mr-2">by {step.data.answered_by.startsWith("offline") ? "rules" : step.data.answered_by}</span>}
          {clock(step.ts)}
        </span>
      </div>
      <p className="mt-1">{step.text}</p>
      <Details step={step} />
    </div>
  );
}

export function DecisionCard({
  gate,
  armed,
  busy,
  by,
  onBy,
  onDecide,
}: {
  gate: Gate;
  armed: boolean;
  busy: boolean;
  by: string;
  onBy: (name: string) => void;
  onDecide: (decision: "go" | "no-go", note: string) => void;
}) {
  const [note, setNote] = useState("");
  const failed = gate.defender.checks.filter((check) => !check.ok);
  return (
    <section className="decision-card p-4" aria-label="Your decision">
      <p className="font-display text-ember">Your call</p>
      <h2 className="mt-1 font-display text-2xl leading-tight font-semibold first-letter:uppercase">{gate.plan_text}?</h2>
      <p className="mt-2">{gate.plan.root_cause}</p>
      <ul className="mt-3 space-y-1 text-sm text-dim">
        <li>
          Defender: {gate.defender.verdict === "pass" ? "passed" : "allowed with caution"}, risk {gate.defender.risk}.{" "}
          {gate.defender.checks.length - failed.length} of {gate.defender.checks.length} checks pass.
        </li>
        {gate.defender.quarantined > 0 && <li className="text-flag">An attack on the AI was quarantined before planning.</li>}
        <li>To undo: {gate.plan.undo}</li>
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <label className="text-dim">
          Deciding as
          <input className="control mt-1 block w-full" value={by} onChange={(event) => onBy(event.target.value)} maxLength={80} />
        </label>
        <label className="text-dim">
          Note
          <input className="control mt-1 block w-full" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} />
        </label>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          className={`go rounded-xl py-3 font-display text-2xl font-bold ${armed ? "ring-4 ring-ember" : ""}`}
          disabled={busy}
          onClick={() => onDecide("go", note)}
        >
          {armed ? "Confirm go" : "Go"}
        </button>
        <button className="nogo rounded-xl py-3 font-display text-2xl font-bold" disabled={busy} onClick={() => onDecide("no-go", note)}>
          No-go
        </button>
      </div>
      <p className="mt-2 text-sm text-dim">Say “no-go” to stop at once. Say “go”, then “confirm”, to proceed.</p>
    </section>
  );
}

const OUTCOMES: Record<string, { title: string; tone: string }> = {
  resolved: { title: "Resolved", tone: "text-calm" },
  not_resolved: { title: "Fix applied, not recovered", tone: "text-flag" },
  rejected: { title: "No-go. Nothing was changed", tone: "text-ember" },
  escalated: { title: "Handed to a human. Nothing was changed", tone: "text-ember" },
  failed: { title: "The flow stopped with an error", tone: "text-flare" },
};

export function OutcomeCard({ status, result }: { status: string; result: Result }) {
  const outcome = OUTCOMES[status] ?? OUTCOMES.failed;
  const [copied, setCopied] = useState(false);
  return (
    <section className="glass p-4" aria-label="Outcome">
      <h2 className={`font-display text-2xl font-semibold ${outcome.tone}`}>{outcome.title}</h2>
      {result.stakeholder_update && (
        <>
          <p className="mt-3 text-sm text-dim">Message for the team</p>
          <p className="mt-1">{result.stakeholder_update}</p>
          <button
            className="control mt-2 text-sm"
            onClick={async () => {
              await navigator.clipboard.writeText(result.stakeholder_update ?? "");
              setCopied(true);
            }}
          >
            {copied ? "Copied" : "Copy message"}
          </button>
        </>
      )}
      {result.postmortem && (
        <details className="mt-3">
          <summary className="cursor-pointer text-dim">Postmortem draft</summary>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-night p-3 font-sans text-sm">{result.postmortem}</pre>
        </details>
      )}
    </section>
  );
}

function Results({ entry }: { entry: Entry }) {
  if (entry.kind === "drill") {
    const held = entry.results.filter((item) => item.held).length;
    return (
      <div className="report" data-kind={held === entry.results.length ? "say" : "block"}>
        <p className="font-display font-semibold">
          Defences held {held} of {entry.results.length} attacks
        </p>
        <ul className="mt-1 space-y-1 text-sm">
          {entry.results.map((item) => (
            <li key={item.attack}>
              <span className={item.held ? "text-calm" : "text-flare"}>{item.held ? "Held" : "Failed"}:</span> {item.attack}.{" "}
              <span className="text-dim">{item.defence}.</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (entry.kind === "scan") {
    if (!entry.report) return <div className="report" data-kind="error">The scan did not finish: {entry.problem}</div>;
    return (
      <div className="report" data-kind={entry.report.findings.length ? "warn" : "say"}>
        <div className="flex items-center gap-2 text-calm">
          <Icon agent="codeguard" />
          <span className="font-display font-semibold text-text">Code Guard</span>
        </div>
        <p className="mt-1">{entry.report.summary}</p>
        <ul className="mt-1 text-sm text-dim">
          {entry.report.tools.map((tool) => (
            <li key={tool.check}>
              {tool.tool}: {tool.ran ? `${tool.found} found` : `could not run (${tool.problem})`}
            </li>
          ))}
        </ul>
        {entry.report.findings.map((finding) => (
          <p key={finding.title + finding.where} className="mt-1 text-sm">
            <span className="text-flag">{finding.severity}:</span> {finding.title} ({finding.where}). Fix: {finding.fix}
          </p>
        ))}
      </div>
    );
  }
  if (entry.kind === "audit") {
    return (
      <div className="report" data-kind={entry.ok ? "say" : "block"}>
        <p>
          <span className={`font-display font-semibold ${entry.ok ? "text-calm" : "text-flare"}`}>{entry.ok ? "Audit log intact" : "Audit log tampered"}</span>{" "}
          <span className="text-dim">({entry.detail}). Every message and decision is one line, chained to the line before it.</span>
        </p>
      </div>
    );
  }
  return null;
}

export default function Stream({ entries, steps }: { entries: Entry[]; steps: Step[] }) {
  const items = [
    ...entries.map((entry) => ({ ts: entry.ts, key: entry.id, entry, step: null as Step | null })),
    ...steps.filter((step) => step.agent !== "aegis" || step.kind !== "ask").map((step) => ({ ts: step.ts, key: `step-${step.seq}`, entry: null, step })),
  ].sort((a, b) => a.ts - b.ts);

  return (
    <ol className="flex flex-col gap-3" aria-live="polite" aria-label="Conversation">
      {items.map(({ key, entry, step }) => (
        <li key={key} className={entry?.kind === "you" ? "flex justify-end" : ""}>
          {step && <Report step={step} />}
          {entry?.kind === "you" && <p className="say-you max-w-[85%]">{entry.text}</p>}
          {entry?.kind === "aegis" && (
            <div className="say-aegis">
              <p className="font-display text-sm text-aegis">
                Aegis{entry.by && !entry.by.startsWith("offline") ? <span className="ml-2 text-dim">via {entry.by}</span> : null}
              </p>
              <p className="text-[1.05rem]">{entry.text}</p>
            </div>
          )}
          {entry?.kind === "outcome" && <OutcomeCard status={entry.status} result={entry.result} />}
          {entry && !["you", "aegis", "outcome"].includes(entry.kind) && <Results entry={entry} />}
        </li>
      ))}
    </ol>
  );
}
