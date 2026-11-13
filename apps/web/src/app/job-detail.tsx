import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { enc, raw } from "../lib/client";
import type { JobDetail } from "../lib/types";
import { ErrorBox, FitBar, Loading, RiskBadge, StatusPill } from "../components/Views";

export function JobDetailPage() {
  const { id = "" } = useParams();
  const q = useQuery({ queryKey: ["job", id], queryFn: () => raw<JobDetail>("GET", `/api/jobs/${enc(id)}`), refetchInterval: 4000 });
  if (q.isLoading) return <Loading />; if (q.isError) return <ErrorBox error={q.error} />;
  const d = q.data!; const spec = d.job_spec; const fit = d.fit_report; const risk = d.risk_report;
  return (
    <div className="stack">
      <div className="row between"><div><h1>{d.job?.title ?? d.run.title}</h1><div className="row"><StatusPill s={d.run.status} /><FitBar v={d.run.fit} /><RiskBadge v={d.run.risk} flags={risk?.flags} /></div></div>
        <div className="row">{d.run.status === "awaiting_approval" && <Link className="btn primary" to={`/studio/${enc(d.run.thread_id)}`}>Open proposal studio</Link>}<Link className="btn" to={`/runs/${enc(d.run.thread_id)}`}>Agent run</Link></div></div>
      <div className="grid cols-2">
        <section className="card"><h2>Job post</h2><p className="small" style={{ whiteSpace: "pre-wrap" }}>{d.job?.description}</p><div className="row">{d.job?.required_skills.map((s) => <span className="badge" key={s}>{s}</span>)}</div>
          {d.job && <p className="small muted">Budget ${d.job.budget.min}–${d.job.budget.max} · Connects {d.job.connects_cost}</p>}</section>
        <section className="card"><h2>Bid or skip</h2>{d.decision ? <><p><span className={`badge ${d.decision.action === "bid" ? "ok" : "warn"}`}>{d.decision.action}</span></p><p>{d.decision.reason}</p></> : <p className="muted">Analysis in progress…</p>}
          {d.price_quote && <><h3>Price rationale</h3><p className="small">{d.price_quote.rationale}</p><p><b>${d.price_quote.amount}</b> <span className="muted small">({d.price_quote.budget_type}, floor {d.price_quote.floor}, Connects {d.price_quote.connects_cost} {d.price_quote.connects_worth_it ? "worth it" : "not worth it"})</span></p></>}</section>
      </div>
      <div className="grid cols-2">
        <section className="card"><h2>Job spec</h2>{spec ? <><h3>Deliverables</h3><ul>{spec.deliverables.length ? spec.deliverables.map((x) => <li key={x}>{x}</li>) : <li className="muted">none stated</li>}</ul>
          <h3>Hidden needs</h3><ul>{spec.hidden_needs.length ? spec.hidden_needs.map((x) => <li key={x}>{x}</li>) : <li className="muted">none inferred</li>}</ul>
          <h3>Screening questions</h3><ul>{spec.screening_questions.length ? spec.screening_questions.map((x) => <li key={x}>{x}</li>) : <li className="muted">none</li>}</ul></> : <p className="muted">–</p>}</section>
        <section className="card"><h2>Risk report</h2>{risk ? <><p>{risk.explanation}</p><div className="row">{risk.flags.length ? risk.flags.map((f) => <span key={f} className="badge bad">{f.replace(/_/g, " ")}</span>) : <span className="badge ok">no flags</span>}</div>
          <p className="small muted">Client quality {Math.round(risk.client_quality * 100)}%{risk.injection_detected ? " · instructions inside the post were ignored" : ""}</p></> : <p className="muted">–</p>}</section>
      </div>
      <section className="card"><h2>Requirements and the portfolio evidence that proves them</h2>
        {fit ? <table aria-label="Requirement to evidence matrix"><thead><tr><th>Requirement</th><th>Evidence</th><th>Status</th></tr></thead><tbody>
          {fit.matches.map((m) => (<tr key={m.requirement} data-testid="matrix-row"><td>{m.requirement}</td><td>{m.evidence_ids.length ? m.evidence_ids.map((e) => <span className="badge" key={e} title={d.evidence?.find((x) => x.id === e)?.text.slice(0, 200)}>{e}</span>) : <span className="muted">no evidence</span>}</td>
            <td><span className={`badge ${m.supported ? "ok" : "bad"}`}>{m.supported ? "supported" : "gap"}</span></td></tr>))}</tbody></table> : <p className="muted">–</p>}
        {fit && <p className="small muted">{fit.reasons}</p>}</section>
    </div>
  );
}
