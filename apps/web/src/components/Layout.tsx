import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { raw } from "../lib/client";
import type { Health } from "../lib/types";
import { useAuth } from "../lib/auth";

const LINKS = [["/inbox", "Inbox"], ["/pipeline", "Pipeline"], ["/messages", "Messages"], ["/runs", "Agent runs"], ["/analytics", "Analytics"], ["/settings", "Settings"]];

/** Degraded-mode banner: shown whenever the marketplace tool server is unreachable; work is queued and resumes by itself. */
function DegradedBanner() {
  const h = useQuery({ queryKey: ["health"], queryFn: () => raw<Health>("GET", "/api/health/tools"), refetchInterval: 5000, retry: false });
  if (h.data?.marketplace !== "down" && !h.isError) return null;
  return <div className="banner" role="alert" data-testid="degraded-banner">Marketplace unavailable. Your work is queued and will resume automatically when it is back.</div>;
}

export function Layout() {
  const [open, setOpen] = useState(false); const { logout } = useAuth(); const nav = useNavigate();
  const pending = useQuery({ queryKey: ["approvals"], queryFn: () => raw<unknown[]>("GET", "/api/approvals"), refetchInterval: 4000 });
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <DegradedBanner />
      <div className="shell">
        <button className="btn menu-btn" aria-expanded={open} aria-controls="nav" onClick={() => setOpen(!open)}>Menu</button>
        <nav id="nav" className={`nav ${open ? "open" : ""}`} aria-label="Main">
          <div className="brand"><i />GigBid</div>
          {LINKS.map(([to, label]) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)}>{label}{label === "Inbox" && (pending.data?.length ?? 0) > 0 && <span className="badge brand" aria-label={`${pending.data!.length} awaiting approval`}>{pending.data!.length}</span>}</NavLink>
          ))}
          <div className="spacer" />
          <button className="btn" onClick={() => { logout(); nav("/login"); }}>Sign out</button>
        </nav>
        <main id="main" className="main"><Outlet /></main>
      </div>
    </>
  );
}
