import { ReactNode } from "react";
import { StatusChip } from "./Status";

export const Loading = ({ what = "Loading" }: { what?: string }) => <div className="empty loading" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" />{what}…</div>;
export const Empty = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="empty"><h2>{title}</h2>{hint && <p>{hint}</p>}{action}</div>
);
export const ErrorBox = ({ error }: { error: unknown }) => <div className="err" role="alert">Something went wrong: {error instanceof Error ? error.message : String(error)}</div>;
export const Pct = ({ v }: { v: number | null | undefined }) => <>{v == null ? "–" : `${Math.round(v * 100)}%`}</>;
export const FitBar = ({ v }: { v: number | null | undefined }) => (
  <div className="row" title={`fit ${v == null ? "n/a" : Math.round(v * 100) + "%"}`}>
    <div className="bar" role="meter" aria-label="Fit score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((v ?? 0) * 100)}><i style={{ width: `${(v ?? 0) * 100}%` }} /></div>
    <span className="small"><Pct v={v} /></span>
  </div>
);
export const RiskBadge = ({ v, flags }: { v: number | null | undefined; flags?: string[] }) => {
  if (v == null) return <span className="badge">risk –</span>;
  const cls = v > 0.7 ? "bad" : v > 0.4 ? "warn" : "ok";
  return <span className={`badge ${cls}`} title={flags?.join(", ")}>risk {Math.round(v * 100)}%</span>;
};
export const StatusPill = ({ s }: { s: string }) => <StatusChip s={s} />;
