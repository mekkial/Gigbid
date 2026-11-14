import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { enc, raw } from "../lib/client";
import type { MessagePayload, ThreadItem } from "../lib/types";
import { ApprovalPanel, Decision } from "../components/ApprovalPanel";
import { Empty, ErrorBox, Loading } from "../components/Views";
import { Typing } from "../components/Status";

function ReplyDraft({ tid, onDone }: { tid: string; onDone: () => void }) {
  const p = useQuery({ queryKey: ["msgpayload", tid], queryFn: () => raw<MessagePayload>("GET", `/api/approvals/${enc(tid)}`), retry: false });
  const [text, setText] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>(null);
  if (p.isLoading) return <Loading what="Loading draft" />; if (p.isError || !p.data) return <p className="muted">Draft not ready yet.</p>;
  const cur = text ?? p.data.draft;
  async function decide(d: Decision) {
    setBusy(true); try { await raw("POST", `/api/approvals/${enc(tid)}`, { ...d, text: d.action === "edit" ? cur : undefined }); onDone(); } catch (e) { setErr(e); setBusy(false); }
  }
  return (
    <div className="stack" data-testid="reply-draft">
      <p className="small muted">Detected intent: <b>{p.data.intent.intent.replace(/_/g, " ")}</b></p>
      <label htmlFor={`r-${tid}`}>Suggested reply</label><textarea id={`r-${tid}`} style={{ minHeight: 120 }} value={cur} onChange={(e) => setText(e.target.value)} />
      {err != null && <ErrorBox error={err} />}
      <ApprovalPanel edited={cur !== p.data.draft} busy={busy} onDecide={decide} slots={p.data.proposed_slots} />
    </div>
  );
}

export function Messages() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["threads"], queryFn: () => raw<ThreadItem[]>("GET", "/api/messages"), refetchInterval: 4000 });
  const respond = useMutation({ mutationFn: (pid: string) => raw("POST", `/api/messages/${enc(pid)}/respond`), onSuccess: () => qc.invalidateQueries({ queryKey: ["threads"] }) });
  if (q.isLoading) return <Loading />; if (q.isError) return <ErrorBox error={q.error} />;
  const threads = q.data ?? [];
  return (
    <div className="stack">
      <h1>Messages</h1><p className="muted">Client replies, with suggested responses and interview slots. Nothing is sent until you approve.</p>
      {threads.length === 0 && <Empty title="No client messages yet" hint="When a client replies to a submitted proposal, it shows up here." />}
      {threads.map((t) => (
        <section className="card stack" key={t.thread_id} data-testid="thread">
          <h2>{t.title}</h2>
          {t.messages.map((m, i) => <p key={i} className="small" style={{ background: m.from === "client" ? "var(--surface-2)" : undefined, padding: 8, borderRadius: 8 }}><b>{m.from === "client" ? "Client" : "You"}:</b> {m.text}</p>)}
          {t.conversation?.status === "awaiting_approval" ? <ReplyDraft tid={t.conversation.thread_id} onDone={() => qc.invalidateQueries({ queryKey: ["threads"] })} />
            : t.conversation && ["queued", "running", "resuming"].includes(t.conversation.status) ? <p role="status" className="notice"><Typing label="Drafting" /> Drafting a reply. It will appear here for your approval.</p>
            : t.messages.length > 0 && t.messages[t.messages.length - 1].from !== "client"
              ? <p role="status" className="notice"><Typing label="Waiting" /> Reply sent. Waiting for the client to answer.</p>
              : <button className="btn primary" onClick={() => respond.mutate(t.proposal_id)}>{respond.isPending ? "Starting…" : "Draft a reply"}</button>}
        </section>))}
    </div>
  );
}
