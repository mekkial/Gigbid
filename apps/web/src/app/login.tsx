import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/client";
import { useAuth } from "../lib/auth";
import { ErrorBox } from "../components/Views";
import { PixelField } from "../components/PixelField";

export function Login() {
  const [sp] = useSearchParams();
  const [mode, setMode] = useState<"login" | "register">(sp.get("mode") === "register" ? "register" : "login");
  const [email, setEmail] = useState(sp.get("email") ?? ""); const [password, setPassword] = useState(""); const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const { login } = useAuth(); const nav = useNavigate();
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    const res = mode === "login" ? await api.POST("/api/auth/login", { body: { email, password } }) : await api.POST("/api/auth/register", { body: { email, password, persona: "ai_ml" } });
    setBusy(false);
    if (res.error || !res.data) { setErr(typeof (res.error as any)?.detail === "string" ? (res.error as any).detail : "Could not sign in. Check your details."); return; }
    login(res.data.access_token); nav(mode === "register" ? "/onboarding" : "/inbox");
  }
  return (
    <div className="auth">
      <main className="auth-form">
        <Link to="/" className="brand" aria-label="GigBid home"><i />GigBid</Link>
        <h1>{mode === "login" ? "Sign in" : "Create your account"}</h1>
        <p className="muted">Your freelance copilot. It finds, judges and drafts. You decide.</p>
        <form className="stack" onSubmit={submit}>
          <div><label htmlFor="email">Email</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div><label htmlFor="password">Password</label><input id="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          {err && <ErrorBox error={err} />}
          <button className="btn primary wide" disabled={busy}>{busy ? <><span className="spinner" aria-hidden="true" />Please wait…</> : mode === "login" ? "Sign in" : "Create account"}</button>
          <button type="button" className="btn wide" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "New here? Create an account" : "I already have an account"}</button>
        </form>
      </main>
      <aside className="auth-art" aria-hidden="true">
        <PixelField height={9999} cell={22} className="fill" />
        <p className="auth-quote">Every claim links to your evidence.<br />Every send needs your approval.</p>
      </aside>
    </div>
  );
}
