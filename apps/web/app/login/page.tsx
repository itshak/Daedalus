"use client";
import { useState, type FormEvent } from "react";
import { createBrowserClient } from "@supabase/ssr";
import { ArrowRight, ShieldCheck } from "lucide-react";
import Image from "next/image";
export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const signIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!url || !key) { setError("Administrator authentication is not configured."); return; }
    setBusy(true); setError("");
    try {
      const supabase = createBrowserClient(url, key);
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      window.location.assign("/");
    } catch { setError("Unable to sign in. Check credentials or contact the administrator."); }
    finally { setBusy(false); }
  };
  return <main className="login-shell"><section className="login-card">
    <div className="login-mark"><Image src="/brand/daedalus-horizontal-light.svg" alt="Daedalus" width={1700} height={520} priority /></div>
    <div className="login-hero"><p className="eyebrow">PRIVATE CONTROL CENTER</p><h1>Welcome back.</h1><p>One workspace for your worlds, warehouses, and automations.</p></div>
    <form onSubmit={signIn} className="login-form">
      <label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required placeholder="you@example.com" />
      <label htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required placeholder="Your password" />
      {error && <p role="alert" className="form-error">{error}</p>}
      <button className="primary-button login-submit" type="submit" disabled={busy}>{busy ? "Verifying…" : "Sign in securely"}<ArrowRight size={16} /></button>
    </form>
    <div className="login-foot"><ShieldCheck size={16} /> Invite-only access · Secure administrator session</div>
  </section><div className="login-aside"><div className="aside-orb" aria-hidden="true" /><p>Everything in its right place.</p><span>Daedalus Management Suite</span></div></main>;
}