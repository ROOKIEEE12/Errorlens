export const API = process.env.NEXT_PUBLIC_ERRORLENS_API ?? "http://localhost:8000";

export type Evidence = { line: number; text: string };
export type Diagnosis = {
  rule_id: string; error_type: string; title: string; root_cause: string; severity: string; confidence: number;
  context: { platform: string; framework: string; package_manager: string | null };
  evidence: Evidence[]; cascade: Evidence[];
  suspected_file: { path: string; line: number | null; confidence: number } | null;
  fix_steps: string[]; verification_commands: string[];
  risk: { level: "low" | "medium" | "high" | "critical"; reason: string };
  fingerprint: string; redaction_summary: Record<string, number>;
  suggested_diff: string | null; diff_note: string | null; risk_flags: string[];
  related: { fingerprint: string; title: string; count: number; last_seen: string; resolution: string | null }[];
  ai: { explanation_en: string; explanation_hi: string; alternative_hypotheses: string[]; risk_explanation: string } | null;
};
export type AnalyzeResponse = {
  analysis_id: string; diagnosis: Diagnosis; redacted_log: string; ocr_text: string | null;
  recurrence: { count: number; first_seen: string; last_seen: string; resolution: string | null } | null;
  ai_status: string; privacy: { mode: string; raw_log_stored: boolean };
};
export type Incident = { fingerprint: string; title: string; error_type: string; framework: string; platform: string; count: number; first_seen: string; last_seen: string; resolution: string | null };

async function fail(r: Response): Promise<never> {
  let msg = `Request failed (${r.status})`;
  try { const j = await r.json(); if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
  throw new Error(msg);
}

export async function analyze(text: string, mode: "local_only" | "sanitized_ai", includeDiff: boolean): Promise<AnalyzeResponse> {
  const fd = new FormData();
  fd.set("text", text); fd.set("privacy_mode", mode); fd.set("include_diff", String(includeDiff));
  const r = await fetch(`${API}/v1/analyze`, { method: "POST", body: fd });
  return r.ok ? r.json() : fail(r);
}
export async function ocr(file: File): Promise<string> {
  const fd = new FormData(); fd.set("file", file);
  const r = await fetch(`${API}/v1/ocr`, { method: "POST", body: fd });
  return r.ok ? (await r.json()).text : fail(r);
}
export async function safeReport(text: string, format: "markdown" | "github" | "json" | "text"): Promise<string> {
  const r = await fetch(`${API}/v1/reports/safe`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, format }) });
  return r.ok ? (await r.json()).report : fail(r);
}
export async function history(q?: string): Promise<Incident[]> {
  const r = await fetch(`${API}/v1/history${q ? `?q=${encodeURIComponent(q)}` : ""}`, { cache: "no-store" });
  return r.ok ? (await r.json()).items : fail(r);
}
export async function resolveIncident(fp: string, note: string): Promise<void> {
  const r = await fetch(`${API}/v1/history/${fp}/resolve`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ note }) });
  if (!r.ok) await fail(r);
}
