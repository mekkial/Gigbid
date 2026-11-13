import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, enc, raw } from "../lib/client";
import { Empty, ErrorBox, FitBar, Loading, RiskBadge, StatusPill } from "../components/Views";

export function Inbox() {
  const qc = useQueryClient();
  const [status, setStatus] = useState(""); const [minFit, setMinFit] = useState(0); const [q, setQ] = useState(""); const [query, setQuery] = useState("");
  const jobs = useQuery({
    queryKey: ["jobs", status, minFit, q], refetchInterval: 3000,
    queryFn: async () => { const r = await api.GET("/api/jobs", { params: { query: { status: status || undefined, min_fit: minFit, q: q || undefined } } }); if (r.error) throw new Error("load failed"); return r.data!; },
  });
  const scout = useMutation({ mutationFn: () => raw("POST", "/api/jobs/scout", { query, limit: 6 }), onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }) });
  const skip = useMutation({ mutationFn: (id: string) => raw("POST", `/api/jobs/${enc(id)}/skip`), onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }) });
  return (
    <div className="stack">
      <div className="row between"><div><h1>Inbox</h1><p className="muted">New jobs ranked by fit. Anything you may bid on waits for you in the Proposal Studio.</p></div></div>
      <form className="card row" onSubmit={(e) => { e.preventDefault(); scout.mutate(); }} aria-label="Scout for jobs">
        <label htmlFor="sq" className="sr">Search</label><input id="sq" style={{ flex: 1, minWidth: 160 }} placeholder="Search the marketplace (e.g. dashboard, RAG, React)" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="btn primary" disabled={scout.isPending}>{scout.isPending ? "Queuing…" : "Scout now"}</button>
      </form>
      <div className="row" role="group" aria-label="Filters">
        <label htmlFor="st" className="sr">Status</label>
        <select id="st" style={{ width: "auto" }} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="awaiting_approval">Awaiting approval</option><option value="skipped">Skipped</option><option value="submitted">Submitted</option><option value="running">Running</option><option value="watch">Watch</option>
        </select>
        <label htmlFor="mf" className="small">Min fit {Math.round(minFit * 100)}%</label><input id="mf" type="range" min={0} max={1} step={0.1} value={minFit} onChange={(e) => setMinFit(+e.target.value)} style={{ width: 140, minHeight: 0 }} />
        <label htmlFor="ft" className="sr">Filter title</label><input id="ft" style={{ width: 180 }} placeholder="Filter by title" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {jobs.isLoading && <Loading what="Loading jobs" />}{jobs.isError && <ErrorBox error={jobs.error} />}
      {jobs.data && jobs.data.length === 0 && <Empty title="No jobs yet" hint="Use “Scout now” to pull jobs from the marketplace. GigBid analyses each one and flags risks." />}
      {jobs.data && jobs.data.length > 0 && (<>
        <table className="card jobtable" aria-label="Jobs"><thead><tr><th>Job</th><th>Fit</th><th>Risk</th><th>Recommendation</th><th>Price</th><th>Connects</th><th /></tr></thead><tbody>
          {jobs.data.map((j) => (
            <tr key={j.thread_id} data-testid="job-row">
              <td><Link to={`/jobs/${enc(j.job_id)}`}>{j.title}</Link><br /><StatusPill s={j.status} /></td>
              <td><FitBar v={j.fit} /></td><td><RiskBadge v={j.risk} flags={(j.summary as any)?.risk_flags} /></td>
              <td>{j.decision ? <span className={`badge ${j.decision === "bid" ? "ok" : j.decision === "watch" ? "warn" : ""}`}>{j.decision}</span> : "…"}</td>
              <td>{j.price ? `$${j.price}` : "–"}</td><td>{j.connects ?? "–"}</td>
              <td><div className="row">{j.status === "awaiting_approval" ? <Link className="btn primary" to={`/studio/${enc(j.thread_id)}`}>Review draft</Link> : <Link className="btn" to={`/jobs/${enc(j.job_id)}`}>Open</Link>}
                {!["submitted", "skipped"].includes(j.status) && <button className="btn" onClick={() => skip.mutate(j.job_id)}>Skip</button>}</div></td>
            </tr>))}
        </tbody></table>
        <div className="joblist">{jobs.data.map((j) => (
          <div className="card stack" key={j.thread_id}><Link to={`/jobs/${enc(j.job_id)}`}><b>{j.title}</b></Link><div className="row"><StatusPill s={j.status} /><RiskBadge v={j.risk} /><span className="badge">${j.price ?? "–"}</span></div><FitBar v={j.fit} />
            {j.status === "awaiting_approval" && <Link className="btn primary" to={`/studio/${enc(j.thread_id)}`}>Review draft</Link>}</div>))}</div>
      </>)}
    </div>
  );
}
