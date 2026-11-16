// The shapes the backend sends. They mirror aegis/store.py and aegis/server.py.

export type Step = { seq: number; ts: number; agent: string; kind: string; text: string; data: Record<string, any> };
export type Check = { check: string; ok: boolean; detail: string };
export type Plan = { root_cause: string; action: string; target: string; value: string; reason: string; undo: string; confidence: number };
export type Gate = {
  plan: Plan;
  plan_text: string;
  plan_hash: string;
  briefing: string;
  defender: { verdict: string; risk: string; checks: Check[]; quarantined: number };
};
export type Result = { outcome?: string; postmortem?: string; stakeholder_update?: string; closing?: string };
export type Model = { id: string; label: string; ready: boolean; missing: string[] };
export type Voice = {
  id: string;
  name: string;
  description?: string;
  engine: string;
  ready: boolean;
  problem: string;
  lang?: string;
  prefer?: string[];
  rate?: number;
  pitch?: number;
};
export type Scenario = { id: string; title: string; story: string };
export type Config = { assistant: string; source: string; models: Model[]; default_model: string; scenarios: Scenario[]; voices: Voice[] };

export type ScanReport = {
  summary: string;
  top_fixes: string[];
  worst: string;
  complete: boolean;
  tools: { check: string; tool: string; ran: boolean; found?: number; problem?: string }[];
  findings: { tool: string; severity: string; title: string; where: string; fix: string }[];
};
export type Drill = { attack: string; defence: string; held: boolean };
