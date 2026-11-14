import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, enc, getToken, raw } from "../lib/client";
import type { RunDetail, TraceItem } from "../lib/types";
import { RunTimeline } from "../components/RunTimeline";
import { Empty, ErrorBox, Loading, StatusPill } from "../components/Views";
import { RunProgress } from "../components/Status";

export function RunsList() {
  const q = useQuery({ queryKey: ["runs"], refetchInterval: 4000, queryFn: async () => (await api.GET("/api/runs")).data ?? [] });
  if (q.isLoading) return <Loading />;
  return (
    <div className="stack"><h1>Agent runs</h1>
      {!q.data?.length && <Empty title="No runs yet" hint="Scout for jobs from the inbox to start one." />}
      {q.data?.map((r) => <Link key={r.thread_id} to={`/runs/${enc(r.thread_id)}`} className="card row between" style={{ textDecoration: "none", color: "inherit" }}><span>{r.title ?? r.job_id}</span><StatusPill s={r.status} /></Link>)}
    </div>
  );
}

/** Live node-by-node progress from LangGraph, streamed over SSE. */
export function RunViewer() {
  const { id = "" } = useParams(); const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["run", id], queryFn: () => raw<RunDetail>("GET", `/api/runs/${enc(id)}`), refetchInterval: 5000 });
  const hist = useQuery({ queryKey: ["hist", id], queryFn: () => raw<{ checkpoint_id: string; next: string[]; step: number; status?: string }[]>("GET", `/api/runs/${enc(id)}/history`) });
  const [live, setLive] = useState<TraceItem[]>([]); const [status, setStatus] = useState<string>(""); const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    const es = new EventSource(`/api/runs/${enc(id)}/stream?token=${getToken()}`);
    es.addEventListener("node", (e) => { const d = JSON.parse((e as MessageEvent).data); const t = d.update?.trace; if (t) setLive((p) => (p.some((x) => x.node === t.node && x.latency_s === t.latency_s) ? p : [...p, t])); });
    es.addEventListener("status", (e) => { const d = JSON.parse((e as MessageEvent).data); setStatus(d.status); qc.invalidateQueries({ queryKey: ["run", id] }); if (["awaiting_approval", "submitted", "skipped", "blocked", "rejected"].includes(d.status)) es.close(); });
    es.addEventListener("degraded", (e) => { setMsg(JSON.parse((e as MessageEvent).data).message); es.close(); });
    es.addEventListener("error", () => es.close());
    return () => es.close();
  }, [id, qc]);
  if (detail.isLoading) return <Loading />; if (detail.isError) return <ErrorBox error={detail.error} />;
  const d = detail.data!; const items = live.length ? live : d.trace; const st = status || d.run.status; const running = ["queued", "running", "resuming"].includes(st);
  return (
    <div className="stack">
      <div className="row between"><div><h1>{d.run.title ?? "Run"}</h1></div>
        <div className="row">{d.trace_url ? <a className="btn" href={d.trace_url} target="_blank" rel="noreferrer">Open full trace</a> : <span className="muted small">Tracing not configured</span>}</div></div>
      <RunProgress threadId={id} status={st} />
      {msg && <div className="err" role="alert">{msg}</div>}
      <div className="grid cols-2">
        <section className="card"><h2>Timeline</h2><RunTimeline items={items} live={running} /></section>
        <section className="card stack"><h2>Totals</h2><p>Steps <b>{d.totals.steps ?? 0}</b> · Tokens <b>{d.totals.tokens ?? 0}</b> · List-price cost <b>${(d.totals.cost_usd ?? 0).toFixed(4)}</b></p>
          <h3>Checkpoint history</h3><ul className="small">{hist.data?.slice(0, 12).map((h) => <li key={h.checkpoint_id}>step {h.step} → {h.next.join(", ") || "end"} {h.status ? `(${h.status})` : ""}
            <button className="btn" style={{ marginLeft: 6, minHeight: 28, padding: "2px 8px" }} onClick={async () => { await raw("POST", `/api/runs/${enc(id)}/replay?checkpoint_id=${enc(h.checkpoint_id)}`); setMsg("Replay queued from this checkpoint."); }}>Replay from here</button></li>)}</ul></section>
      </div>
    </div>
  );
}
