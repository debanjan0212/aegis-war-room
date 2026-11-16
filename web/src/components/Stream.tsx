// The comms channel: you, Aegis, the crew's reports, and the go / no-go, in one thread.
// Every report wears its agent's colour. All text is shown as plain text, never as HTML, so nothing an agent
// or a log says can run in the page.
import { type CSSProperties, useEffect, useState } from "react";
import { colorOf, iconOf, nameOf } from "../stations";
import type { Check, Drill, Gate, Result, ScanReport, Step } from "../types";

export type Entry =
  | { kind: "you"; id: string; ts: number; text: string }
  | { kind: "aegis"; id: string; ts: number; text: string; by?: string }
  | { kind: "drill"; id: string; ts: number; results: Drill[] }
  | { kind: "scan"; id: string; ts: number; report: ScanReport | null; problem: string }
  | { kind: "audit"; id: string; ts: number; ok: boolean; detail: string }
  | { kind: "outcome"; id: string; ts: number; status: string; result: Result };

const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
const tone = (color: string) => ({ "--tone": color }) as CSSProperties;
const KIND_TONE: Record<string, string> = { block: "#ff3d5a", error: "#ff3d5a", warn: "#f7e04b" };

/** Aegis's newest line types itself out, the way it would on a terminal. */
function Typed({ text, live }: { text: string; live: boolean }) {
  const [shown, setShown] = useState(live ? 0 : text.length);
  useEffect(() => {
    if (!live || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(text.length);
      return;
    }
    setShown(0);
    const timer = setInterval(() => setShown((n) => Math.min(n + 2, text.length)), 22);
    return () => clearInterval(timer);
  }, [text, live]);
  return (
    <span aria-label={text}>
      <span aria-hidden="true" className={shown < text.length ? "caret" : ""}>
        {text.slice(0, shown)}
      </span>
    </span>
  );
}

export function Badge({ agent, color }: { agent: string; color: string }) {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden="true" style={{ filter: `drop-shadow(0 0 6px ${color})` }}>
      <polygon points="16,1 29,8.5 29,23.5 16,31 3,23.5 3,8.5" fill={`${color}22`} stroke={color} strokeWidth="1.5" />
      <g transform="translate(7 7) scale(0.75)">
        <path d={iconOf(agent)} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

function Details({ step }: { step: Step }) {
  const { abnormal, quarantined, checks, steps } = step.data;
  return (
    <>
      {Array.isArray(abnormal) && abnormal.length > 0 && (
        <ul className="mt-1 space-y-0.5 font-mono text-[13px] text-dim">
          {abnormal.map((fact: string) => (
            <li key={fact}>&gt; {fact}</li>
          ))}
        </ul>
      )}
      {Array.isArray(quarantined) && (
        <details className="mt-1">
          <summary className="hud-label cursor-pointer" style={{ color: "#f7e04b" }}>
            Show what was quarantined
          </summary>
          {quarantined.map((item: { text: string; reasons: string[] }) => (
            <div key={item.text} className="hud mt-2 p-2" style={tone("#ff3d5a")}>
              <p className="break-words font-mono text-[13px] text-flare">{item.text}</p>
              <p className="mt-1 text-sm text-dim">Why: it {item.reasons.join(", and it ")}.</p>
            </div>
          ))}
        </details>
      )}
      {Array.isArray(checks) && (
        <details className="mt-1">
          <summary className="hud-label cursor-pointer">Show the {checks.length} checks</summary>
          <ul className="mt-1 font-mono text-[13px]">
            {checks.map((check: Check) => (
              <li key={check.check} className={check.ok ? "text-calm" : "text-flare"}>
                [{check.ok ? "PASS" : "FAIL"}] {check.check} ({check.detail})
              </li>
            ))}
          </ul>
        </details>
      )}
      {Array.isArray(steps) && steps.length > 0 && (
        <details className="mt-1">
          <summary className="hud-label cursor-pointer">Show the runbook steps</summary>
          <ul className="mt-1 font-mono text-[13px] text-dim">
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
  const own = colorOf(step.agent);
  const frame = step.agent !== "human" && KIND_TONE[step.kind] ? KIND_TONE[step.kind] : own;
  const by = step.data.answered_by as string | undefined;
  return (
    <div className="hud materialize p-3" style={tone(frame)}>
      <div className="flex items-center gap-2.5">
        {iconOf(step.agent) ? <Badge agent={step.agent} color={own} /> : <span className="live-dot ml-1" />}
        <span className="font-display text-[15px] font-bold tracking-[0.14em] uppercase glow-text" style={{ color: own }}>
          {nameOf(step.agent)}
        </span>
        <span className="ml-auto text-right font-mono text-[11px] leading-tight text-dim">
          {by && <span className="block uppercase">{by.startsWith("offline") ? "rules" : by}</span>}
          {clock(step.ts)}
        </span>
      </div>
      <p className="mt-1.5 text-[1.02rem] leading-snug">{step.text}</p>
      <Details step={step} />
    </div>
  );
}

export function DecisionCard({
  gate,
  armed,
  by,
  onBy,
  onDecide,
}: {
  gate: Gate;
  armed: boolean;
  by: string;
  onBy: (name: string) => void;
  onDecide: (decision: "go" | "no-go", note: string) => void;
}) {
  const [note, setNote] = useState("");
  const failed = gate.defender.checks.filter((check) => !check.ok);
  return (
    <section className="hud materialize p-4" style={{ ...tone("#ffc24d"), boxShadow: "0 0 50px -12px #ffc24d" }} aria-label="Your decision">
      <p className="hud-label" style={{ color: "#ffc24d" }}>
        Authorisation required
      </p>
      <h2 className="mt-2 font-display text-xl leading-snug font-bold text-white glow-text first-letter:uppercase">{gate.plan_text}?</h2>
      <p className="mt-2">{gate.plan.root_cause}</p>
      <ul className="mt-3 space-y-0.5 font-mono text-[13px] text-dim">
        <li>
          &gt; Defender: {gate.defender.verdict === "pass" ? "passed" : "allowed with caution"}, risk {gate.defender.risk},{" "}
          {gate.defender.checks.length - failed.length}/{gate.defender.checks.length} checks
        </li>
        {gate.defender.quarantined > 0 && <li className="text-flag">&gt; An attack on the AI was quarantined before planning</li>}
        <li>&gt; Undo: {gate.plan.undo}</li>
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="hud-label">
          Deciding as
          <input className="hud-input mt-1 block h-9 w-full text-base" value={by} onChange={(event) => onBy(event.target.value)} maxLength={80} />
        </label>
        <label className="hud-label">
          Note
          <input className="hud-input mt-1 block h-9 w-full text-base" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} />
        </label>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <button className={`go py-3 text-xl ${armed ? "ring-4 ring-ember" : ""}`} onClick={() => onDecide("go", note)}>
          {armed ? "Confirm" : "Go"}
        </button>
        <button className="nogo py-3 text-xl" onClick={() => onDecide("no-go", note)}>
          No-go
        </button>
      </div>
      <p className="mt-3 text-sm text-dim">Say “no-go” to stop at once. Say “go”, then “confirm”, to proceed.</p>
    </section>
  );
}

const OUTCOMES: Record<string, { title: string; color: string }> = {
  resolved: { title: "Resolved", color: "#3df5a0" },
  not_resolved: { title: "Fix applied, not recovered", color: "#f7e04b" },
  rejected: { title: "Stood down. Nothing was changed", color: "#ffc24d" },
  escalated: { title: "Handed to a human. Nothing was changed", color: "#ffc24d" },
  failed: { title: "The flow stopped with an error", color: "#ff3d5a" },
};

export function OutcomeCard({ status, result }: { status: string; result: Result }) {
  const outcome = OUTCOMES[status] ?? OUTCOMES.failed;
  const [copied, setCopied] = useState(false);
  return (
    <section className="hud materialize p-4" style={tone(outcome.color)} aria-label="Outcome">
      <p className="hud-label">Incident closed</p>
      <h2 className="mt-1 font-display text-xl font-bold glow-text" style={{ color: outcome.color }}>
        {outcome.title}
      </h2>
      {result.stakeholder_update && (
        <>
          <p className="hud-label mt-3">Message for the team</p>
          <p className="mt-1">{result.stakeholder_update}</p>
          <button
            className="hud-btn mt-2"
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
          <summary className="hud-label cursor-pointer">Postmortem draft</summary>
          <pre className="mt-2 max-h-80 overflow-auto bg-void/70 p-3 font-mono text-[13px] whitespace-pre-wrap text-text/90">{result.postmortem}</pre>
        </details>
      )}
    </section>
  );
}

function Header({ agent, color, title, right }: { agent: string; color: string; title: string; right?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <Badge agent={agent} color={color} />
      <span className="font-display text-[15px] font-bold tracking-[0.14em] uppercase glow-text" style={{ color }}>
        {title}
      </span>
      {right && (
        <span className="ml-auto font-display text-lg font-bold" style={{ color }}>
          {right}
        </span>
      )}
    </div>
  );
}

function Results({ entry }: { entry: Entry }) {
  if (entry.kind === "drill") {
    const held = entry.results.filter((item) => item.held).length;
    const color = held === entry.results.length ? colorOf("defender") : "#ff3d5a";
    return (
      <div className="hud materialize p-3" style={tone(color)}>
        <Header agent="defender" color={color} title="Security drill" right={`${held}/${entry.results.length} held`} />
        <ul className="mt-2 space-y-1 font-mono text-[13px]">
          {entry.results.map((item) => (
            <li key={item.attack}>
              <span className={item.held ? "text-calm" : "text-flare"}>[{item.held ? "HELD" : "FAILED"}]</span> {item.attack}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (entry.kind === "scan") {
    const color = colorOf("codeguard");
    if (!entry.report)
      return (
        <div className="hud p-3" style={tone("#ff3d5a")}>
          The scan did not finish: {entry.problem}
        </div>
      );
    return (
      <div className="hud materialize p-3" style={tone(color)}>
        <Header agent="codeguard" color={color} title="Code Guard" right={`${entry.report.findings.length} found`} />
        <p className="mt-1.5">{entry.report.summary}</p>
        <ul className="mt-1 font-mono text-[13px] text-dim">
          {entry.report.tools.map((tool) => (
            <li key={tool.check}>
              &gt; {tool.tool}: {tool.ran ? `${tool.found} found` : `could not run (${tool.problem})`}
            </li>
          ))}
        </ul>
        {entry.report.findings.map((finding) => (
          <p key={finding.title + finding.where} className="mt-1 text-sm">
            <span className="text-flag uppercase">{finding.severity}</span> {finding.title} ({finding.where}). Fix: {finding.fix}
          </p>
        ))}
      </div>
    );
  }
  if (entry.kind === "audit") {
    const color = entry.ok ? "#3df5a0" : "#ff3d5a";
    return (
      <div className="hud materialize p-3" style={tone(color)}>
        <Header agent="scribe" color={color} title={entry.ok ? "Audit log intact" : "Audit log tampered"} />
        <p className="mt-1.5 font-mono text-[13px] text-dim">&gt; {entry.detail}. Every message and decision is chained to the one before it.</p>
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
  const newestAegis = [...entries].reverse().find((entry) => entry.kind === "aegis")?.id;

  return (
    <ol className="flex flex-col gap-3" aria-live="polite" aria-label="Conversation">
      {items.map(({ key, entry, step }) => (
        <li key={key} className={entry?.kind === "you" ? "flex flex-col items-end" : ""}>
          {step && <Report step={step} />}
          {entry?.kind === "you" && (
            <>
              <span className="hud-label mb-1" style={{ color: "#ffc24d" }}>
                You
              </span>
              <p className="msg-you materialize max-w-[85%]">{entry.text}</p>
            </>
          )}
          {entry?.kind === "aegis" && (
            <div className="msg-aegis materialize">
              <p className="flex items-center gap-2">
                <span className="live-dot" style={{ background: "#4ff3ff", boxShadow: "0 0 10px #4ff3ff" }} />
                <span className="font-display text-[13px] font-bold tracking-[0.2em] text-aegis glow-text">AEGIS</span>
                {entry.by && !entry.by.startsWith("offline") && <span className="hud-label">via {entry.by}</span>}
              </p>
              <p className="mt-0.5 text-[1.12rem] leading-snug font-semibold text-white">
                <Typed text={entry.text} live={entry.id === newestAegis} />
              </p>
            </div>
          )}
          {entry?.kind === "outcome" && <OutcomeCard status={entry.status} result={entry.result} />}
          {entry && !["you", "aegis", "outcome"].includes(entry.kind) && <Results entry={entry} />}
        </li>
      ))}
    </ol>
  );
}
