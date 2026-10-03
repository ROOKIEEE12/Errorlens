"use client";
import { useEffect, useState } from "react";
import { history, resolveIncident, type Incident } from "@/lib/api";

export default function History() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Incident[]>([]);
  const [error, setError] = useState("");

  async function load(query?: string) {
    try { setItems(await history(query || undefined)); setError(""); }
    catch (e) { setError((e as Error).message); }
  }
  useEffect(() => { load(); }, []);

  async function resolve(fp: string) {
    const note = window.prompt("What fixed it?");
    if (!note) return;
    try { await resolveIncident(fp, note); await load(q); } catch (e) { setError((e as Error).message); }
  }

  return (
    <main>
      <div className="hero"><h1>History</h1><p>Recurring fingerprints and known resolutions. Only fingerprints and summaries are stored — never raw logs.</p></div>
      {error && <div className="err">{error}</div>}
      <div className="row" style={{ marginBottom: 12 }}>
        <input type="text" placeholder="Search past incidents…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load(q)} style={{ maxWidth: 420 }} />
        <button onClick={() => load(q)}>Search</button>
      </div>
      <div className="card">
        <table>
          <thead><tr><th>Fingerprint</th><th>Issue</th><th>Stack</th><th>Seen</th><th>Last</th><th>Resolution</th></tr></thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.fingerprint}>
                <td className="mono">{i.fingerprint}</td><td>{i.title}</td><td>{i.framework} / {i.platform}</td>
                <td>{i.count}×</td><td className="muted">{i.last_seen}</td>
                <td>{i.resolution ?? <button onClick={() => resolve(i.fingerprint)}>Mark resolved</button>}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={6} className="muted">No incidents yet — analyze a log first.</td></tr>}
          </tbody>
        </table>
      </div>
    </main>
  );
}
