import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { enc, raw } from "../lib/client";
import type { Claim, ProposalPayload } from "../lib/types";
import { EvidenceHover } from "../components/EvidenceHover";
import { ApprovalPanel, Decision } from "../components/ApprovalPanel";
import { ErrorBox, Loading, RiskBadge } from "../components/Views";
import { RunProgress, LiveDot } from "../components/Status";

const words = (s: string) => new Set(s.toLowerCase().match(/\w+/g) ?? []);
function matchClaim(sentence: string, claims: Claim[]): Claim | undefined {
  const a = words(sentence);
  return claims.find((c) => { const b = words(c.text); let n = 0; b.forEach((w) => a.has(w) && n++); return b.size > 0 && n / Math.min(a.size, b.size) >= 0.6; });
}
const MARK = /\s*\[evidence:\s*([^\]]+)\]/g;

export function Studio() {
  const { id = "" } = useParams(); const nav = useNavigate();
  const q = useQuery({ queryKey: ["studio", id], queryFn: () => raw<ProposalPayload>("GET", `/api/proposals/${enc(id)}/studio`) });
  const [text, setText] = useState<string | null>(null); const [mode, setMode] = useState<"view" | "edit">("view");
  const [busy, setBusy] = useState(false); const [phase, setPhase] = useState<0 | 1 | 2 | 3>(0); const [err, setErr] = useState<unknown>(null); const [regen, setRegen] = useState<number | null>(null);
  const d = q.data; const current = text ?? d?.send_text ?? ""; const edited = !!d && current !== d.send_text;
  const paragraphs = useMemo(() => (d?.draft ?? "").split(/\n\s*\n/).filter(Boolean), [d]);

  if (q.isLoading) return <Loading what="Loading proposal" />; if (q.isError) return <ErrorBox error={q.error} />; if (!d) return null;

  async function decide(dec: Decision) {
    setBusy(true); setErr(null); setPhase(1);
    try {
      await raw("POST", `/api/approvals/${enc(id)}`, { ...dec, text: dec.action === "edit" ? current : undefined });
      setPhase(2);
      for (let i = 0; i < 80; i++) {                                           // wait for the graph to finish resuming
        const r = await raw<{ run: { status: string } }>("GET", `/api/runs/${enc(id)}`);
        if (!["resuming", "running", "awaiting_approval"].includes(r.run.status)) break;
        await new Promise((r2) => setTimeout(r2, 500));
      }
      setPhase(3); await new Promise((r2) => setTimeout(r2, 700));
      nav(dec.action === "reject" ? "/inbox" : "/pipeline");
    } catch (e) { setErr(e); setBusy(false); setPhase(0); }
  }
  async function regenerate(i: number) {
    setRegen(i); setErr(null);
    try {
      const r = await raw<{ text: string }>("POST", `/api/proposals/${enc(id)}/regenerate`, { paragraph_index: i });
      const ps = current.split(/\n\s*\n/); ps[i] = r.text; setText(ps.join("\n\n"));
    } catch (e) { setErr(e); } finally { setRegen(null); }
  }

  return (
    <div className="stack">
      <div className="row between"><div><h1>Proposal studio</h1><p className="muted">Hover or focus any underlined claim to see the portfolio evidence behind it.</p></div>
        <div className="row"><RiskBadge v={d.risk_report?.score} flags={d.risk_report?.flags} /><span className="badge">bid ${d.price_quote?.amount}</span></div></div>
      {d.pending ? <RunProgress threadId={id} status="awaiting_approval" /> : <div className="card">This proposal is no longer waiting for approval.</div>}
      {phase > 0 && (
        <ol className="sendsteps card" role="status" aria-live="polite" aria-label="Sending progress">
          {["Recording your decision", "Submitting to the marketplace (once)", "Added to your pipeline"].map((t, i) => (
            <li key={t} className={phase > i + 1 ? "done" : phase === i + 1 ? "now" : "todo"}>{phase === i + 1 ? <LiveDot tone="work" /> : <i className="tick" />}{t}</li>))}
        </ol>
      )}
      <div className="split">
        <section className="card stack" aria-label="Draft">
          <div className="row" role="tablist" aria-label="Draft mode">
            <button role="tab" aria-selected={mode === "view"} className={`btn ${mode === "view" ? "primary" : ""}`} onClick={() => setMode("view")}>Evidence view</button>
            <button role="tab" aria-selected={mode === "edit"} className={`btn ${mode === "edit" ? "primary" : ""}`} onClick={() => setMode("edit")}>Edit text</button>
          </div>
          {mode === "view" ? (
            <div className="draft" data-testid="draft-view">
              {paragraphs.map((p, pi) => (<p key={pi}>{p.split(/(?<=[.!?])\s+/).map((s, si) => {
                const ids = [...s.matchAll(MARK)].flatMap((m) => m[1].split(",").map((x) => x.trim())); const clean = s.replace(MARK, "").trim(); const claim = matchClaim(clean, d.claims);
                return ids.length || claim ? <EvidenceHover key={si} text={clean + " "} ids={ids.length ? ids : (claim?.evidence_ids ?? [])} evidence={d.evidence} claim={claim} /> : <span key={si}>{clean} </span>;
              })}</p>))}
            </div>
          ) : (
            <div className="stack">
              <label htmlFor="draft-text">Text that will be sent</label>
              <textarea id="draft-text" value={current} onChange={(e) => setText(e.target.value)} data-testid="draft-textarea" />
              <div className="row">{current.split(/\n\s*\n/).map((_, i) => <button key={i} className="btn" disabled={regen !== null} onClick={() => regenerate(i)}>{regen === i ? "Rewriting…" : `Regenerate paragraph ${i + 1}`}</button>)}</div>
              {edited && <button className="btn" onClick={() => setText(null)}>Undo my edits</button>}
            </div>
          )}
          <h3>Reviewer notes</h3>
          <ul className="small" aria-label="Critic and compliance comments">
            {d.critiques.map((c, i) => <li key={i}><b>Critic {i + 1}:</b> {c.approved ? "approved" : c.issues.join("; ")} <span className="muted">(grounding {Math.round(c.grounding * 100)}%, personalisation {Math.round(c.personalisation * 100)}%)</span></li>)}
            <li><b>Compliance:</b> {d.compliance?.violations?.length ? `cleaned: ${d.compliance.violations.join(", ")}` : "no violations"}</li>
            {d.claims.filter((c) => c.verdict !== "supported").map((c, i) => <li key={`u${i}`} className="muted">Claim “{c.text}” is {c.verdict.replace("_", " ")}</li>)}
          </ul>
        </section>
        <div className="stack">
          {err != null && <ErrorBox error={err} />}
          {d.pending && <ApprovalPanel dryRun={d.dry_run} edited={edited} blocked={d.compliance ? !d.compliance.allowed : false} busy={busy} onDecide={decide} />}
          <section className="card"><h3>Price rationale</h3><p className="small">{d.price_quote?.rationale}</p></section>
          <section className="card"><h3>Evidence used ({d.evidence.length})</h3>{d.evidence.slice(0, 5).map((e) => <p key={e.id} className="small"><b>{e.id}</b> <span className="muted">{e.type}, {e.date}</span></p>)}</section>
        </div>
      </div>
    </div>
  );
}
