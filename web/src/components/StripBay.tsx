// The conversation: one paper strip per message, newest at the bottom.
// All text is shown as plain text, never as HTML, so nothing an agent or a log says can run in the page.
import { hueOf, nameOf } from "../stations";
import type { Check, Step } from "../types";

const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });

function Extras({ step }: { step: Step }) {
  const { abnormal, quarantined, checks, steps } = step.data;
  return (
    <>
      {Array.isArray(abnormal) && abnormal.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-ink-soft">
          {abnormal.map((fact: string) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
      {Array.isArray(quarantined) && (
        <details className="mt-2">
          <summary className="cursor-pointer font-bold">Show what was quarantined</summary>
          {quarantined.map((item: { text: string; reasons: string[] }) => (
            <div key={item.text} className="mt-2 rounded border border-ink/30 bg-white/60 p-2">
              <p className="break-words">{item.text}</p>
              <p className="mt-1 text-sm text-ink-soft">Why: it {item.reasons.join(", and it ")}.</p>
            </div>
          ))}
        </details>
      )}
      {Array.isArray(checks) && (
        <details className="mt-2">
          <summary className="cursor-pointer font-bold">Show the {checks.length} checks</summary>
          <ul className="mt-1">
            {checks.map((check: Check) => (
              <li key={check.check} className={check.ok ? "" : "font-bold text-nogo"}>
                {check.ok ? "Pass" : "Fail"}: {check.check} <span className="text-ink-soft">({check.detail})</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {Array.isArray(steps) && steps.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer font-bold">Show the runbook steps</summary>
          <ul className="mt-1 text-ink-soft">
            {steps.map((line: string) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

export default function StripBay({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-col gap-2" aria-live="polite" aria-label="What the agents are saying">
      {steps.map((step) => (
        <li key={step.seq} className="strip" data-kind={step.kind} style={{ borderLeftColor: hueOf(step.agent) }}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-display text-xl leading-tight">{nameOf(step.agent)}</span>
            <span className="text-sm text-ink-soft tabular-nums">
              {step.data.answered_by ? `answered by ${step.data.answered_by}, ` : ""}
              <time>{clock(step.ts)}</time>
            </span>
          </div>
          <p className="max-w-[72ch]">{step.text}</p>
          <Extras step={step} />
        </li>
      ))}
    </ol>
  );
}
