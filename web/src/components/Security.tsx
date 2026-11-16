// The defender's own corner: scan the code, attack the defences, check the audit log.
import { useState } from "react";
import { api } from "../api";
import type { Drill, ScanReport } from "../types";

export default function Security({ model }: { model: string }) {
  const [scan, setScan] = useState<ScanReport | null>(null);
  const [scanState, setScanState] = useState("");
  const [drill, setDrill] = useState<Drill[] | null>(null);
  const [audit, setAudit] = useState<{ ok: boolean; detail: string } | null>(null);
  const [problem, setProblem] = useState("");

  const guard = (work: () => Promise<void>) => () => work().catch((err) => setProblem(String(err.message ?? err)));

  const runScan = guard(async () => {
    setScanState("Scanning the code. This takes up to a minute.");
    await api.startScan(model);
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const { status, report } = await api.scanReport();
      if (status === "running") continue;
      setScan(report);
      setScanState(report ? "" : `The scan did not finish: ${status}`);
      return;
    }
  });

  return (
    <section className="border-t border-rule px-4 py-6 sm:px-6" aria-label="Security">
      <h2 className="font-display text-3xl">Defender's corner</h2>
      <p className="mt-1 max-w-[72ch] text-chalk-dim">
        The same checks run here, in the terminal and on every change in GitHub. Nothing on this row touches a live system.
      </p>
      {problem && <p className="mt-2 text-amber">{problem}</p>}

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <div>
          <button className="quiet-button" onClick={runScan} disabled={scanState.startsWith("Scanning")}>
            Scan this code for vulnerabilities
          </button>
          {scanState && <p className="mt-2 text-chalk-dim">{scanState}</p>}
          {scan && (
            <div className="mt-3">
              <p>{scan.summary}</p>
              <ul className="mt-2 text-chalk-dim">
                {scan.tools.map((tool) => (
                  <li key={tool.check} className={tool.ran ? "" : "text-amber"}>
                    {tool.tool}: {tool.ran ? `${tool.found} found` : `could not run (${tool.problem})`}
                  </li>
                ))}
              </ul>
              {scan.findings.map((finding) => (
                <div key={finding.title + finding.where} className="strip mt-2" data-kind={["high", "critical"].includes(finding.severity) ? "block" : "warn"}>
                  <p className="font-bold">
                    {finding.severity}: {finding.title}
                  </p>
                  <p className="text-sm text-ink-soft">{finding.where}</p>
                  <p>Fix: {finding.fix}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <button className="quiet-button" onClick={guard(async () => setDrill(await api.drill()))}>
            Attack the defences (security drill)
          </button>
          {drill && (
            <ul className="mt-3 flex flex-col gap-2">
              {drill.map((item) => (
                <li key={item.attack}>
                  <span className={item.held ? "text-[#5fd39a]" : "font-bold text-amber"}>{item.held ? "Held" : "Failed"}: </span>
                  {item.attack}. <span className="text-chalk-dim">{item.defence}.</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <button className="quiet-button" onClick={guard(async () => setAudit(await api.audit()))}>
            Check the audit log for tampering
          </button>
          {audit && (
            <p className="mt-3">
              <span className={audit.ok ? "text-[#5fd39a]" : "font-bold text-amber"}>{audit.ok ? "Intact" : "Tampered"}: </span>
              {audit.detail}. Every agent message and every decision is one line, chained to the line before it.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
