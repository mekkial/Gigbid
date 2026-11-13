import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, enc, raw } from "../lib/client";
import { Empty, ErrorBox, Loading } from "../components/Views";

export function SettingsPage() {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: async () => (await api.GET("/api/auth/me")).data });
  const searches = useQuery({ queryKey: ["searches"], queryFn: async () => (await api.GET("/api/saved-searches")).data ?? [] });
  const memory = useQuery({ queryKey: ["memory"], queryFn: async () => (await api.GET("/api/memory")).data ?? [] });
  const [floor, setFloor] = useState(30); const [budget, setBudget] = useState(100); const [autonomy, setAutonomy] = useState<"manual" | "auto_skip_low_fit">("manual"); const [saved, setSaved] = useState(false);
  const [sq, setSq] = useState(""); const [every, setEvery] = useState(180);
  useEffect(() => { const s = me.data?.settings; if (s) { setFloor(s.floor_hourly); setBudget(s.weekly_connects_budget); setAutonomy(s.autonomy); } }, [me.data]);
  const save = useMutation({ mutationFn: async (e: FormEvent) => { e.preventDefault(); await api.PUT("/api/settings", { body: { settings: { ...me.data!.settings, floor_hourly: floor, weekly_connects_budget: budget, autonomy } } }); }, onSuccess: () => { setSaved(true); qc.invalidateQueries({ queryKey: ["me"] }); } });
  const addSearch = useMutation({ mutationFn: async (e: FormEvent) => { e.preventDefault(); await api.POST("/api/saved-searches", { body: { query: sq, interval_min: every } }); setSq(""); }, onSuccess: () => qc.invalidateQueries({ queryKey: ["searches"] }) });
  const delSearch = useMutation({ mutationFn: (id: number) => raw("DELETE", `/api/saved-searches/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["searches"] }) });
  const forget = useMutation({ mutationFn: (m: { namespace: string; key: string }) => raw("DELETE", `/api/memory/${m.namespace}/${enc(m.key)}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["memory"] }) });
  if (me.isLoading) return <Loading />; if (me.isError) return <ErrorBox error={me.error} />;
  return (
    <div className="stack" style={{ maxWidth: 860 }}><h1>Settings</h1>
      <form className="card stack" onSubmit={(e) => save.mutate(e)} aria-label="Preferences"><h2>Autonomy and budgets</h2>
        <div className="grid cols-2"><div><label htmlFor="fl">Minimum hourly rate (USD)</label><input id="fl" type="number" min={1} value={floor} onChange={(e) => setFloor(+e.target.value)} /></div>
          <div><label htmlFor="wb">Weekly Connects budget</label><input id="wb" type="number" min={0} value={budget} onChange={(e) => setBudget(+e.target.value)} /></div></div>
        <label htmlFor="au">Autonomy</label><select id="au" value={autonomy} onChange={(e) => setAutonomy(e.target.value as any)}><option value="manual">Manual: I review every job</option><option value="auto_skip_low_fit">Auto-skip low-fit jobs (never auto-send)</option></select>
        <div className="row"><button className="btn primary">Save</button>{saved && <span role="status" className="badge ok">Saved</span>}</div></form>
      <section className="card stack"><h2>Saved searches</h2><p className="small muted">Scouted by the background worker. Intervals are never shorter than 60 minutes.</p>
        {searches.data?.length ? <ul>{searches.data.map((s) => <li key={s.id} className="row between"><span>{s.query} <span className="muted small">every {s.interval_min} min</span></span><button className="btn" onClick={() => delSearch.mutate(s.id)}>Remove</button></li>)}</ul> : <p className="muted">No saved searches.</p>}
        <form className="row" onSubmit={(e) => addSearch.mutate(e)}><label className="sr" htmlFor="nsq">Search</label><input id="nsq" style={{ flex: 1 }} required placeholder="e.g. rag chatbot" value={sq} onChange={(e) => setSq(e.target.value)} />
          <label className="sr" htmlFor="ev">Interval minutes</label><input id="ev" type="number" min={60} style={{ width: 100 }} value={every} onChange={(e) => setEvery(+e.target.value)} /><button className="btn">Add</button></form></section>
      <section className="card"><h2>Connected accounts</h2><div className="row"><span className="badge ok">GigSim (simulator)</span>{me.data?.connected?.includes("upwork") ? <span className="badge ok">Upwork (live)</span> : <span className="badge">Upwork not connected</span>}</div></section>
      <section className="card stack"><h2>What GigBid has learned</h2><p className="small muted">Only promoted knowledge is stored here. You can delete anything.</p>
        {memory.data?.length ? <ul aria-label="Memory items">{memory.data.map((m) => <li key={m.namespace + m.key} className="row between" data-testid="memory-item"><span><span className="badge">{m.namespace}</span> {(m.value as any).rule ?? `${(m.value as any).category}: reply rate ${Math.round(((m.value as any).reply_rate ?? 0) * 100)}% over ${(m.value as any).n}`}</span>
          <button className="btn danger" onClick={() => forget.mutate({ namespace: m.namespace, key: m.key })}>Forget</button></li>)}</ul> : <Empty title="Nothing learned yet" hint="Style rules appear after you repeat the same edit across jobs." />}</section>
    </div>
  );
}
