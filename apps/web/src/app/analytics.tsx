import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/client";
import { Empty, ErrorBox, Loading, Pct } from "../components/Views";
import { CountUp } from "../components/PixelField";

export function Analytics() {
  const q = useQuery({ queryKey: ["analytics"], queryFn: async () => { const r = await api.GET("/api/analytics"); if (r.error) throw new Error("load failed"); return r.data!; } });
  if (q.isLoading) return <Loading />; if (q.isError) return <ErrorBox error={q.error} />;
  const a = q.data!; const t = a.totals as any; const c = a.connects as any; const cl = a.cost_latency as any; const cats = a.by_category as any[];
  const tile = (label: string, value: string) => { const m = value.match(/^([$]?)([0-9.]+)(s?)$/); return <div className="card lift" key={label}><div className="kicker">{label}</div><div className="tile">{m ? <CountUp to={parseFloat(m[2])} decimals={m[2].includes(".") ? m[2].split(".")[1].length : 0} prefix={m[1]} suffix={m[3]} /> : value}</div></div>; };
  return (
    <div className="stack"><h1>Analytics</h1>
      <div className="grid cols-3">{tile("Jobs analysed", String(t.runs ?? 0))}{tile("Proposals sent", String(t.submitted ?? 0))}{tile("Awaiting approval", String(t.pending ?? 0))}
        {tile("Connects spent", String(c.spent ?? 0))}{tile("Avg cost / proposal", `$${(cl.avg_cost_per_proposal ?? 0).toFixed(4)}`)}{tile("p95 latency / proposal", `${(cl.p95_latency_s ?? 0).toFixed(1)}s`)}</div>
      <section className="card"><h2>Reply and hire rate by category</h2>
        {cats.filter((x) => x.sent > 0).length === 0 ? <Empty title="No outcomes yet" hint="Rates appear once proposals are sent and clients respond." /> : (
          <table aria-label="Outcomes by category"><thead><tr><th>Category</th><th>Sent</th><th>Reply rate</th><th>Hire rate</th><th /></tr></thead><tbody>
            {cats.filter((x) => x.sent > 0).map((x) => <tr key={x.category}><td>{x.category}</td><td>{x.sent}</td><td><Pct v={x.reply_rate} /></td><td><Pct v={x.hire_rate} /></td>
              <td style={{ width: "30%" }}><svg width="100%" height="12" role="img" aria-label={`reply rate ${Math.round((x.reply_rate ?? 0) * 100)} percent`}><rect width="100%" height="12" rx="6" fill="var(--surface-2)" /><rect width={`${(x.reply_rate ?? 0) * 100}%`} height="12" rx="6" fill="var(--brand)" /></svg></td></tr>)}</tbody></table>)}</section>
      <section className="card"><h2>Top rejection reasons</h2>{a.rejection_reasons.length === 0 ? <p className="muted">None yet.</p> : <ul>{a.rejection_reasons.map((r: any) => <li key={r.reason}>{r.reason ?? "(no reason)"} — {r.n}</li>)}</ul>}</section>
    </div>
  );
}
