// Every call the screen makes to the backend, in one place.
import type { Config, Drill, ScanReport } from "./types";

// If the backend is protected (AEGIS_API_TOKEN), open the screen once with ?token=... and it is kept for this tab only.
const fromUrl = new URLSearchParams(location.search).get("token");
if (fromUrl) {
  sessionStorage.setItem("aegis_token", fromUrl);
  history.replaceState(null, "", location.pathname); // keep the token out of the address bar and history
}
const token = sessionStorage.getItem("aegis_token");

async function call<T>(path: string, body?: unknown): Promise<T> {
  const reply = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!reply.ok) {
    const problem = await reply.json().catch(() => ({}));
    throw new Error(problem.detail ?? `The server answered ${reply.status}`);
  }
  return reply.json();
}

export const api = {
  config: () => call<Config>("/api/config"),
  trigger: (scenario: string, model: string) => call<{ id: string }>("/api/incidents/trigger", { scenario, model }),
  scanLive: (model: string) => call<{ ids: string[] }>("/api/incidents/scan-live", { model }),
  decide: (id: string, decision: "go" | "no-go", plan_hash: string, by: string, note: string) =>
    call<{ ok: boolean }>(`/api/incidents/${id}/decision`, { decision, plan_hash, by, note }),
  startScan: (model: string) => call<{ status: string }>("/api/security/scan", { model }),
  scanReport: () => call<{ status: string; report: ScanReport | null }>("/api/security/report"),
  drill: () => call<Drill[]>("/api/security/drill", {}),
  audit: () => call<{ ok: boolean; detail: string }>("/api/security/audit"),
};
