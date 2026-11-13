import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, enc, raw } from "../lib/client";
import { Empty, ErrorBox, Loading } from "../components/Views";

const STAGES = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"] as const;

export function Pipeline() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["pipeline"], refetchInterval: 4000, queryFn: async () => { const r = await api.GET("/api/pipeline"); if (r.error) throw new Error("load failed"); return r.data!; } });
  const sync = useMutation({ mutationFn: () => raw("POST", "/api/pipeline/sync"), onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline"] }) });
  if (q.isLoading) return <Loading />; if (q.isError) return <ErrorBox error={q.error} />;
  const cards = q.data ?? [];
  return (
    <div className="stack">
      <div className="row between"><div><h1>Pipeline</h1><p className="muted">Cards move as the marketplace reports events.</p></div><button className="btn" onClick={() => sync.mutate()} disabled={sync.isPending}>{sync.isPending ? "Syncing…" : "Sync marketplace events"}</button></div>
      {cards.length === 0 && <Empty title="Nothing in the pipeline" hint="Approve a proposal from your inbox and it will appear here." />}
      <div className="kanban" aria-label="Pipeline board">
        {STAGES.map((s) => { const col = cards.filter((c) => c.stage === s); return (
          <section className="col" key={s} aria-label={s} data-testid={`col-${s}`}><h3>{s}<span className="badge">{col.length}</span></h3>
            {col.map((c) => (<div className="card" key={c.thread_id}><b className="small">{c.title}</b><p className="small muted">{c.price ? `$${c.price}` : ""}</p>
              {s === "drafted" ? <Link to={`/studio/${enc(c.thread_id)}`}>Review</Link> : <Link to={`/messages`}>Open thread</Link>}</div>))}
          </section>); })}
      </div>
    </div>
  );
}
