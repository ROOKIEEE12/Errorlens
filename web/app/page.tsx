"use client";
import { useRef, useState } from "react";
import { analyze, ocr, safeReport, type AnalyzeResponse } from "@/lib/api";
import { SAMPLE_ENV, SAMPLE_VERCEL } from "@/lib/samples";

const IMG = /\.(png|jpe?g|webp|bmp|gif)$/i;

function Diff({ diff }: { diff: string }) {
  return (
    <div className="log diff">
      {diff.split("\n").map((l, i) => (
        <div key={i} className={l.startsWith("+++") || l.startsWith("---") ? "muted" : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : l.startsWith("@@") ? "hunk" : ""}>{l || " "}</div>
      ))}
    </div>
  );
}

export default function Home() {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"local_only" | "sanitized_ai">("local_only");
  const [diff, setDiff] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [res, setRes] = useState<AnalyzeResponse | null>(null);
  const [report, setReport] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function run() {
    setBusy(true); setError(""); setReport("");
    try { setRes(await analyze(text, mode, diff)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function onFile(f: File | undefined) {
    if (!f) return;
    setError(""); setNote("");
    try {
      if (IMG.test(f.name)) {
        setBusy(true); setNote("Reading screenshot…");
        setText(await ocr(f));
        setNote("OCR text is editable — fix any recognition mistakes, then analyze.");
      } else { setText(await f.text()); }
    } catch (e) { setError((e as Error).message); setNote(""); }
    finally { setBusy(false); }
  }

  async function makeReport(fmt: "markdown" | "github") {
    try { setReport(await safeReport(text, fmt)); } catch (e) { setError((e as Error).message); }
  }

  const d = res?.diagnosis;
  const hits = new Set(d?.evidence.map((e) => e.line));
  const casc = new Set(d?.cascade.map((e) => e.line));
  const total = d ? Object.values(d.redaction_summary).reduce((a, b) => a + b, 0) : 0;

  return (
    <main>
      <div className="hero">
        <h1>Paste a failure. Get the real fix.</h1>
        <p>Build logs, tracebacks and screenshots → root cause, evidence, safe fix. Secrets are redacted locally before anything else.</p>
      </div>
      {error && <div className="err">{error}</div>}
      <div className="grid">
        {/* LEFT: input */}
        <section>
          <div className="card">
            <h3>Input</h3>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste a build log, terminal output or traceback…" spellCheck={false} />
            <div className="row" style={{ marginTop: 8 }}>
              <button onClick={() => fileRef.current?.click()}>Upload log / screenshot</button>
              <button onClick={() => setText(SAMPLE_VERCEL)}>Sample: Vercel</button>
              <button onClick={() => setText(SAMPLE_ENV)}>Sample: env + secrets</button>
              <input ref={fileRef} type="file" hidden accept=".log,.txt,.json,.yml,.yaml,.png,.jpg,.jpeg,.webp,Dockerfile" onChange={(e) => onFile(e.target.files?.[0])} />
            </div>
            {note && <p className="small muted">{note}</p>}
            <label>Privacy mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="local_only">Local only — nothing leaves your machine</option>
              <option value="sanitized_ai">Sanitized AI — only redacted, structured facts</option>
            </select>
            <label><input type="checkbox" checked={diff} onChange={(e) => setDiff(e.target.checked)} /> Include suggested diff</label>
            <button className="primary" disabled={busy || !text.trim()} onClick={run}>{busy ? "Working…" : "Analyze"}</button>
          </div>
          {d && (
            <div className="card">
              <h3>Detected</h3>
              <span className="chip">{d.context.platform}</span><span className="chip">{d.context.framework}</span>
              {d.context.package_manager && <span className="chip">{d.context.package_manager}</span>}
              <span className="chip">{d.error_type}</span>
            </div>
          )}
        </section>

        {/* CENTER: result */}
        <section>
          {!d && <div className="card muted">Results appear here. Try a sample to see the flow.</div>}
          {d && res && (
            <>
              <div className="card root">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="chip">{Math.round(d.confidence * 100)}% confidence</span>
                  <span className="mono muted">{d.fingerprint}</span>
                </div>
                <h2>{d.title}</h2>
                <p style={{ margin: 0 }}>{d.root_cause}</p>
                {d.suspected_file && (
                  <p className="mono">📍 {d.suspected_file.path}{d.suspected_file.line ? `:${d.suspected_file.line}` : ""} <span className="muted">(probable, {Math.round(d.suspected_file.confidence * 100)}%)</span></p>
                )}
                {res.recurrence && res.recurrence.count > 1 && (
                  <p className="small" style={{ color: "var(--yellow)" }}>↻ Recurring — seen {res.recurrence.count}× since {res.recurrence.first_seen}{res.recurrence.resolution ? ` · Known resolution: ${res.recurrence.resolution}` : ""}</p>
                )}
              </div>

              <div className="card">
                <h3>Evidence (redacted log)</h3>
                <div className="log">
                  {res.redacted_log.split("\n").map((l, i) => (
                    <div key={i} className={hits.has(i + 1) ? "hit" : casc.has(i + 1) ? "casc" : ""}><span className="n">{i + 1}</span>{l || " "}</div>
                  ))}
                </div>
                <p className="small muted">Red = root cause · grey = cascade (consequences, not causes)</p>
              </div>

              <div className="card">
                <h3>Fix</h3>
                <ol>{d.fix_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              </div>

              {d.suggested_diff ? (
                <div className="card"><h3>Suggested diff</h3><Diff diff={d.suggested_diff} /><p className="small muted">{d.diff_note}</p></div>
              ) : d.diff_note ? (
                <div className="card small muted">{d.diff_note.replace("--repo <path> (CLI)", "`errorlens analyze --repo <path>`")}</div>
              ) : null}

              {d.ai && (
                <div className="card">
                  <h3>AI explanation</h3>
                  <p>{d.ai.explanation_en}</p><p>{d.ai.explanation_hi}</p>
                  {d.ai.alternative_hypotheses.map((h, i) => <p key={i} className="small muted">Maybe: {h}</p>)}
                </div>
              )}
              {mode === "sanitized_ai" && !d.ai && <div className="card small muted">AI: {res.ai_status}</div>}
            </>
          )}
        </section>

        {/* RIGHT: risk, verify, related, share */}
        <section>
          {d && res && (
            <>
              <div className="card">
                <h3>Risk</h3>
                <span className={`chip ${d.risk.level}`}>{d.risk.level.toUpperCase()}</span>
                <p style={{ margin: "6px 0 0" }}>{d.risk.reason}</p>
              </div>
              {d.verification_commands.length > 0 && (
                <div className="card">
                  <h3>Verify locally</h3>
                  <pre>{d.verification_commands.map((c) => `$ ${c}`).join("\n")}</pre>
                  <button style={{ marginTop: 8 }} onClick={() => navigator.clipboard.writeText(d.verification_commands.join("\n"))}>Copy</button>
                </div>
              )}
              <div className="card">
                <h3>Security scan</h3>
                {total > 0
                  ? <p className="shield">🛡 {total} sensitive value(s) redacted: {Object.entries(d.redaction_summary).map(([k, v]) => `${v}× ${k}`).join(", ")}</p>
                  : <p className="shield">🛡 No sensitive values detected.</p>}
                <p className="small muted">Raw log was not stored.</p>
              </div>
              {d.related.length > 0 && (
                <div className="card">
                  <h3>Related past issues</h3>
                  {d.related.map((r) => <p key={r.fingerprint} className="small"><span className="mono">{r.fingerprint}</span> · {r.count}× · {r.title}{r.resolution ? ` — ${r.resolution}` : ""}</p>)}
                </div>
              )}
              <div className="card">
                <h3>Share-safe report</h3>
                <div className="row"><button onClick={() => makeReport("markdown")}>Markdown</button><button onClick={() => makeReport("github")}>GitHub comment</button></div>
                {report && (
                  <>
                    <textarea readOnly value={report} style={{ minHeight: 160, marginTop: 8 }} />
                    <button style={{ marginTop: 8 }} onClick={() => navigator.clipboard.writeText(report)}>Copy</button>
                  </>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
