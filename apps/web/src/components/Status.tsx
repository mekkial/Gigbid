import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { enc, raw } from "../lib/client";
import type { RunDetail } from "../lib/types";

/** Plain-language meaning of every run status: what is happening, and whether the user has to do anything. */
export const STATUS: Record<string, { label: string; hint: string; tone: "work" | "act" | "done" | "wait" | "stop" | "idle" }> = {
  queued: { label: "In line", hint: "Waiting for a free agent. Nothing for you to do.", tone: "wait" },
  running: { label: "Agents working", hint: "Reading, judging and drafting. This page updates by itself.", tone: "work" },
  resuming: { label: "Sending", hint: "Your decision is being applied. Do not close the tab.", tone: "work" },
  awaiting_approval: { label: "Ready for you", hint: "The draft is finished and waiting for your approval.", tone: "act" },
  submitted: { label: "Sent", hint: "Submitted to the marketplace. Waiting for the client to reply.", tone: "done" },
  skipped: { label: "Skipped", hint: "GigBid decided this job is not worth bidding on.", tone: "idle" },
  rejected: { label: "Rejected", hint: "You rejected this draft.", tone: "idle" },
  blocked: { label: "Blocked", hint: "The compliance check stopped this proposal.", tone: "stop" },
  dead_letter: { label: "Failed", hint: "The run failed after retries. Open the run to see why.", tone: "stop" },
  needs_attention: { label: "Needs attention", hint: "A budget or step limit was hit. Open the run.", tone: "stop" },
  waiting_marketplace: { label: "Paused", hint: "The marketplace is unreachable. It resumes by itself.", tone: "wait" },
};
export const isActive = (s: string) => ["queued", "running", "resuming", "waiting_marketplace"].includes(s);

export function LiveDot({ tone }: { tone: string }) {
  return <span className={`live-dot ${tone}`} aria-hidden="true" />;
}

/** A status chip that says what is happening in words, and pulses while work is in progress. */
export function StatusChip({ s, showHint = false }: { s: string; showHint?: boolean }) {
  const m = STATUS[s] ?? { label: s.replace(/_/g, " "), hint: "", tone: "idle" as const };
  return (
    <span className={`chip ${m.tone}`} title={m.hint}>
      <LiveDot tone={m.tone} />{m.label}{showHint && <span className="chip-hint">{m.hint}</span>}
    </span>
  );
}

export function useElapsed(active: boolean) {
  const start = useRef(Date.now()); const [n, setN] = useState(0);
  useEffect(() => { if (!active) return; start.current = Date.now(); setN(0); const t = setInterval(() => setN(Math.floor((Date.now() - start.current) / 1000)), 1000); return () => clearInterval(t); }, [active]);
  return n;
}
const fmt = (s: number) => (s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`);

const STAGES = [
  { key: "read", label: "Read the post", nodes: ["intake", "analyst", "risk_assessor", "fit_matcher", "scout_intake"] },
  { key: "decide", label: "Decide and price", nodes: ["decide", "pricing"] },
  { key: "write", label: "Write the draft", nodes: ["writer"] },
  { key: "check", label: "Check claims", nodes: ["verify", "critic", "compliance"] },
  { key: "you", label: "Your approval", nodes: ["approval"] },
  { key: "send", label: "Send once", nodes: ["submit"] },
];
const stageOf = (node: string) => STAGES.findIndex((s) => s.nodes.some((n) => node.includes(n)));

/** Where a run is on the bid graph, with a ticking timer and the last completed step. Polls while the run is active. */
export function RunProgress({ threadId, status }: { threadId: string; status: string }) {
  const active = isActive(status);
  const q = useQuery({ queryKey: ["progress", threadId, status], queryFn: () => raw<RunDetail>("GET", `/api/runs/${enc(threadId)}`), refetchInterval: active ? 2500 : false });
  const elapsed = useElapsed(active);
  const trace = q.data?.trace ?? [];
  const done = trace.reduce((m, t) => Math.max(m, stageOf(t.node)), -1);
  let cur = status === "awaiting_approval" ? 4 : status === "submitted" ? 6 : status === "resuming" ? 5 : status === "skipped" ? Math.max(done + 1, 2) : done + 1;
  if (status === "queued") cur = 0;
  const last = trace[trace.length - 1];
  const m = STATUS[status] ?? STATUS.queued;
  const total = trace.reduce((s, t) => s + (t.latency_s ?? 0), 0);
  return (
    <section className={`progress ${m.tone}`} aria-label="Run progress">
      <div className="progress-head">
        <StatusChip s={status} />
        <span className="progress-hint" role="status" aria-live="polite">{m.hint}</span>
        <span className="progress-time mono">{active ? `${fmt(elapsed)} elapsed` : total ? `${total.toFixed(0)}s of agent time` : ""}</span>
      </div>
      <ol className="rail">
        {STAGES.map((s, i) => {
          const state = status === "skipped" && i >= cur ? "off" : i < cur ? "done" : i === cur && (active || status === "awaiting_approval") ? "now" : "todo";
          return <li key={s.key} className={state} aria-current={state === "now" ? "step" : undefined}><i /><span>{s.label}</span></li>;
        })}
      </ol>
      {last && active && <p className="progress-last mono">last step: {last.node.replace(/_/g, " ")} · {last.latency_s}s{last.models?.length ? ` · ${last.models[0]}` : ""}</p>}
    </section>
  );
}

/** Shown in the sidebar: how many runs are being worked on right now, so the user knows whether to wait. */
export function ActivityPill({ running, queued, ready }: { running: number; queued: number; ready: number }) {
  const busy = running + queued;
  return (
    <div className={`activity ${busy ? "work" : ready ? "act" : "done"}`} role="status" aria-live="polite">
      <LiveDot tone={busy ? "work" : ready ? "act" : "done"} />
      <span>{busy ? `${running} working · ${queued} in line` : ready ? `${ready} ready for you` : "All caught up"}</span>
    </div>
  );
}

/** Three animated dots: someone (the agent, or the client) is still to answer. */
export function Typing({ label }: { label: string }) {
  return <span className="typing" role="status"><i /><i /><i /><span className="sr">{label}</span></span>;
}
