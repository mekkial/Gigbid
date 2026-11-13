import { useState } from "react";
import type { Claim, Evidence } from "../lib/types";

/** A claim in the draft. Hover or keyboard-focus shows the portfolio evidence behind it. */
export function EvidenceHover({ text, ids, evidence, claim }: { text: string; ids: string[]; evidence: Evidence[]; claim?: Claim }) {
  const [open, setOpen] = useState(false);
  const items = evidence.filter((e) => ids.includes(e.id));
  const cls = claim?.verdict === "unsupported" ? "unsup" : claim?.verdict === "partly_supported" ? "partly" : "";
  return (
    <span className={`ev ${cls}`} tabIndex={0} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
      aria-describedby={open ? "evpop" : undefined} data-testid="evidence-claim">
      {text}
      {open && (
        <span className="pop" role="tooltip" id="evpop" data-testid="evidence-popover">
          <strong>{claim ? claim.verdict.replace("_", " ") : "cited evidence"}</strong>
          {items.length === 0 && <span> — no matching portfolio item</span>}
          {items.map((e) => (
            <span key={e.id} style={{ display: "block", marginTop: 6 }}>
              <b>{e.id}</b> <span className="muted">({e.type}, {e.date}{e.outcome ? `, ${e.outcome}` : ""})</span>
              <span style={{ display: "block" }}>{e.text.slice(0, 220)}…</span>
            </span>
          ))}
        </span>
      )}
    </span>
  );
}
