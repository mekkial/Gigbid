import { useState } from "react";
import type { DryRun } from "../lib/types";

export interface Decision { action: "approve" | "edit" | "reject"; text?: string; reason?: string; slot?: string }

/** The human gate: approve, edit (diffed, saved for style memory, re-checked by Compliance) or reject with a reason. */
export function ApprovalPanel({ dryRun, edited, blocked, busy, onDecide, slots }: {
  dryRun?: DryRun; edited: boolean; blocked?: boolean; busy: boolean; onDecide: (d: Decision) => void; slots?: string[];
}) {
  const [reason, setReason] = useState(""); const [rejecting, setRejecting] = useState(false); const [slot, setSlot] = useState(slots?.[0] ?? "");
  return (
    <section className="card stack" aria-label="Approval">
      <h2>Your decision</h2>
      {dryRun && dryRun.would_send && (
        <div className="card" style={{ background: "var(--surface-2)" }} data-testid="dry-run">
          <h3>Dry-run preview</h3>
          <p className="small">Exactly what will be sent: <b>{dryRun.would_send.cover_letter.length}</b> characters, bid <b>${dryRun.would_send.bid_amount}</b>.</p>
          <p className="small">Connects cost <b>{dryRun.connects_cost}</b> · balance after <b>{dryRun.balance_after}</b></p>
        </div>
      )}
      {slots && slots.length > 0 && (<div><label htmlFor="slot">Interview slot to hold</label>
        <select id="slot" value={slot} onChange={(e) => setSlot(e.target.value)}>{slots.map((s) => <option key={s}>{s}</option>)}</select></div>)}
      {blocked && <div className="err" role="alert">Compliance blocked this draft. Edit it to remove the violation.</div>}
      {!rejecting ? (
        <div className="row">
          <button className="btn primary" disabled={busy || edited || !!blocked} onClick={() => onDecide({ action: "approve", slot: slot || undefined })}>Approve &amp; send</button>
          <button className="btn" disabled={busy || !edited} onClick={() => onDecide({ action: "edit", slot: slot || undefined })} title={edited ? "" : "Change the text first"}>Save edits &amp; approve</button>
          <button className="btn danger" disabled={busy} onClick={() => setRejecting(true)}>Reject…</button>
        </div>
      ) : (
        <div className="stack">
          <label htmlFor="reason">Why are you rejecting this?</label>
          <input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. too generic" />
          <div className="row">
            <button className="btn danger" disabled={busy || !reason.trim()} onClick={() => onDecide({ action: "reject", reason })}>Confirm reject</button>
            <button className="btn" onClick={() => setRejecting(false)}>Cancel</button>
          </div>
        </div>
      )}
      <p className="small muted">Nothing is sent until you approve. Edits are saved so GigBid can learn your style.</p>
    </section>
  );
}
