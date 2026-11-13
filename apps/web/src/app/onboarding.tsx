import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, getToken } from "../lib/client";
import { ErrorBox, Loading } from "../components/Views";

const PERSONAS = [["ai_ml", "AI / ML engineer", "Python, PyTorch, RAG, MLOps"], ["fullstack", "Full-stack web developer", "React, Node, Postgres, Stripe"], ["data_analyst", "Data analyst", "SQL, Power BI, dbt, A/B testing"]] as const;

export function Onboarding() {
  const me = useQuery({ queryKey: ["me"], queryFn: async () => (await api.GET("/api/auth/me")).data });
  const [persona, setPersona] = useState<"ai_ml" | "fullstack" | "data_analyst">("ai_ml");
  const [floor, setFloor] = useState(30); const [budget, setBudget] = useState(100); const [keywords, setKeywords] = useState(""); const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null); const [err, setErr] = useState<unknown>(null); const nav = useNavigate();
  if (me.isLoading) return <Loading />;
  async function save(e: FormEvent) {
    e.preventDefault(); setErr(null);
    const r = await api.PUT("/api/settings", { body: { persona, settings: { floor_hourly: floor, weekly_connects_budget: budget, autonomy: "manual", marketplace_mode: "gigsim", keywords: keywords.split(",").map((s) => s.trim()).filter(Boolean), min_budget: 0 } } });
    if (r.error) { setErr(JSON.stringify(r.error)); return; }
    if (file) {
      const fd = new FormData(); fd.append("file", file);
      const u = await fetch("/api/portfolio/upload", { method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: fd });
      if (!u.ok) { setErr(`Portfolio upload failed: ${await u.text()}`); return; }
      setMsg("Portfolio item indexed.");
    }
    nav("/inbox");
  }
  return (
    <form className="stack" onSubmit={save} style={{ maxWidth: 720 }}>
      <h1>Set up GigBid</h1>
      <p className="muted">Four quick steps. You can change everything later in Settings.</p>
      <fieldset className="card"><legend><b>1. Choose your profile</b></legend>
        <div className="grid cols-3">{PERSONAS.map(([id, name, sub]) => (
          <label key={id} className="card" style={{ cursor: "pointer", borderColor: persona === id ? "var(--brand)" : undefined, margin: 0 }}>
            <input type="radio" name="persona" value={id} checked={persona === id} onChange={() => setPersona(id)} style={{ width: "auto", minHeight: 0 }} /> <b>{name}</b><br /><span className="muted small">{sub}</span>
          </label>))}</div>
        <p className="small muted">Using your own Upwork profile? Connect it in step 2; your portfolio items go in step 3.</p>
      </fieldset>
      <fieldset className="card"><legend><b>2. Connect a marketplace</b></legend>
        <div className="row"><span className="badge ok">GigSim (simulator) connected</span><button type="button" className="btn" disabled title="Needs Upwork OAuth credentials configured on the server">Connect Upwork (live)</button></div>
        <p className="small muted">Live mode only creates drafts you confirm on Upwork, and never scrapes the site.</p>
      </fieldset>
      <fieldset className="card"><legend><b>3. Add portfolio</b></legend>
        <label htmlFor="pf">Case study or CV (Markdown or text)</label><input id="pf" type="file" accept=".md,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </fieldset>
      <fieldset className="card"><legend><b>4. Rates, filters and Connects budget</b></legend>
        <div className="grid cols-2">
          <div><label htmlFor="floor">Minimum hourly rate (USD)</label><input id="floor" type="number" min={1} value={floor} onChange={(e) => setFloor(+e.target.value)} /></div>
          <div><label htmlFor="budget">Weekly Connects budget</label><input id="budget" type="number" min={0} value={budget} onChange={(e) => setBudget(+e.target.value)} /></div>
        </div>
        <label htmlFor="kw">Search keywords (comma separated)</label><input id="kw" value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="python, rag, dashboard" />
      </fieldset>
      {err != null && <ErrorBox error={err} />}{msg && <p role="status">{msg}</p>}
      <button className="btn primary">Finish setup</button>
    </form>
  );
}
