import type { TraceItem } from "../lib/types";

export function RunTimeline({ items, live }: { items: TraceItem[]; live?: boolean }) {
  return (
    <ol className="tl" aria-label="Agent run timeline" aria-live="polite">
      {items.map((t, i) => (
        <li key={i} data-testid="timeline-node">
          <span className="dot" />
          <span><b>{t.node.replace(/_/g, " ")}</b> {t.models && t.models.length > 0 && <span className="muted small">· {t.models.join(", ")}</span>}</span>
          <span className="muted small">{t.latency_s}s{t.tokens_in != null ? ` · ${(t.tokens_in ?? 0) + (t.tokens_out ?? 0)} tok` : ""}</span>
        </li>
      ))}
      {live && <li><span className="dot run" /><span className="muted">working…</span><span /></li>}
    </ol>
  );
}
