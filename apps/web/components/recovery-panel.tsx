"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, PlayCircle, RefreshCw, ShieldCheck } from "lucide-react";

type Account = { id: string; email?: string | null; player?: string; world?: string; name?: string; enabled?: boolean };
type Policy = { enabled: boolean; auto_resume: boolean; grace_seconds: number; revision: number; pause_until: number | null; pause_indefinite: boolean };
type Event = { phase: string; lost_at: number; due_at: number; attempts: number; last_reason: string | null } | null;
type Recovery = { account_id: string; policy: Policy; event: Event; desired_jobs: number; auto_resume_eligible: number; manual_review: number; server_token_available: boolean; session_status: string };
type Index = { enabled: boolean; supervisor_enabled: boolean; accounts: Recovery[] };

async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch("/api/controller/" + path, {
    method, cache: "no-store",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.error === "string" ? result.error : "Recovery action failed");
  return result as T;
}
function name(a: Account) { return a.email || a.name || a.player || a.id; }
function label(status: string) { return status.replace(/_/g, " ").replace(/\b\w/g, char => char.toUpperCase()); }
function recoveryClassLabel(kind: string) {
  switch (kind) {
    case "continuous": return "Restarts if absent";
    case "reconcile_construction": return "Checks remaining target levels";
    case "convergent_transport": return "Resumes source-stock threshold policy";
    default: return "Manual review (no replay)";
  }
}
function deadline(event: Event, now: number) {
  if (!event || !["grace", "retry"].includes(event.phase)) return "";
  const seconds = Math.max(0, Math.ceil(event.due_at - now / 1000));
  return seconds === 0 ? "Recovery eligible now" : "Not before " + Math.floor(seconds / 60) + "m " + String(seconds % 60).padStart(2, "0") + "s";
}

export function RecoveryPanel({ accounts, role }: { accounts: Account[]; role: string }) {
  const [data, setData] = useState<Index | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState("");
  const [now, setNow] = useState(0);
  const [jobAccount, setJobAccount] = useState("");
  const [jobs, setJobs] = useState<{jobs:{id:string;task:string;restart_class:string;desired_state:string}[];receipts:{status:string;logical_id:string}[]} | null>(null);
  const canWrite = role !== "viewer";
  const byId = useMemo(() => Object.fromEntries(accounts.map(a => [a.id, a])) as Record<string,Account>, [accounts]);
  const refresh = useCallback(async () => {
    try { setData(await api<Index>("recovery")); }
    catch { setData(null); setMessage("Recovery status is unavailable from the backend."); }
  }, []);
  useEffect(() => { const startup = setTimeout(() => { void refresh(); }, 0); return () => clearTimeout(startup); }, [refresh]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const records = data?.accounts ?? [];

  async function act(id: string, success: string, path: string, method: "POST" | "PUT", payload: unknown, confirmText: string) {
    if (!window.confirm(confirmText)) return;
    setWorking(id); setMessage("");
    try {
      await api(path, method, payload);
      setMessage(success + " for " + name(byId[id] || { id }) + ".");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Outcome uncertain. Refresh before retrying.");
    } finally { setWorking(""); }
  }
  const url = (id:string,action:string) => "accounts/" + encodeURIComponent(id) + "/recovery/" + action;
  const importToken = (r:Recovery) => act(r.account_id,"Protected token imported",url(r.account_id,"import-saved-token"),"POST",{confirmed:true},
    "Import this account's existing saved Gameforge lobby token into the encrypted SERVER store? No game login or task is started.");
  const save = (r:Recovery,enabled:boolean) => act(r.account_id,enabled?"Auto recovery enabled":"Auto recovery disabled",url(r.account_id,"policy"),"PUT",
    {confirmed:true,enabled,auto_resume:enabled,grace_seconds:300,expected_revision:r.policy.revision},
    enabled ? "Enable automatic reconnection and safe task restoration after five minutes? A new login may sign an active game browser out. Only audited background tasks will auto-resume." :
      "Disable this account's automatic Gameforge reconnection and task restoration?");
  const pause = (r:Recovery,seconds:number|null) => act(r.account_id,"Browser-use pause saved",url(r.account_id,"pause"),"POST",{confirmed:true,seconds},
    seconds ? "Pause automatic reconnection for " + seconds/60 + " minutes while you use the browser?" :
      "Pause automatic reconnection until you manually resume it?");
  const resume = (r:Recovery) => act(r.account_id,"Recovery queued",url(r.account_id,"resume-now"),"POST",{confirmed:true},
    "Reconnect NOW, possibly signing your active game browser out? Your exact player must verify before any approved safe job is restored.");
  async function bulk(enabled: boolean) {
    if (!selected.length || !window.confirm((enabled?"Enable":"Disable")+" delayed reconnection for "+selected.length+" selected accounts? This may later log an active game browser out.")) return;
    setWorking("bulk");setMessage("");
    try {
      const result=await api<{results:{account_id:string;status:string}[]}>("recovery/policy/bulk","POST",
        {confirmed:true,account_ids:selected,enabled,auto_resume:enabled,grace_seconds:300});
      setMessage(result.results.map(r=>name(byId[r.account_id]||{id:r.account_id})+": "+label(r.status)).join(" · "));
      await refresh();
    } catch (error) {setMessage(error instanceof Error?error.message:"Bulk outcome uncertain");}
    finally {setWorking("");}
  }
  async function review(id:string) {
    if (jobAccount===id){setJobAccount("");setJobs(null);return;}
    setJobAccount(id);setJobs(null);
    try {setJobs(await api("accounts/"+encodeURIComponent(id)+"/recovery/jobs"));}
    catch {setMessage("Saved job catalog unavailable.");}
  }

  return <section className="panel recovery-dashboard" aria-label="Automatic game session recovery">
    <div className="panel-heading"><div><h3>Browser-friendly recovery</h3>
      <p>Five-minute grace after confirmed session loss, followed by verified reconnection and safe job restoration.</p>
    </div><button className="secondary-button" onClick={() => void refresh()}><RefreshCw size={15}/> Refresh</button></div>
    <div className="recovery-explainer"><ShieldCheck size={20}/>
      <span>Recovery is <strong>opt-in per account</strong>. It cannot tell whether you are still browsing after five minutes; use Pause to extend the window. Native construction resumes unfinished target levels and recurring threshold transports recalculate current stock. Fixed-quantity shipments or uncertain game actions are not replayed.</span>
    </div>
    {message && <div role="status" className="notice"><CircleAlert size={17}/><span>{message}</span></div>}
    {!data?.enabled ? <div className="empty-state"><strong>Recovery controller unavailable</strong><p>No automatic login is authorized from this panel.</p></div> :
      <><div className="recovery-toolbar">
        <strong>{records.filter(r=>r.policy.enabled).length} of {records.length} policies enabled</strong>
        <span>{data.supervisor_enabled?"Host supervisor available":"Host supervisor off — no unattended logins"}</span>
        {canWrite && <div className="recovery-actions">
          <button className="secondary-button" disabled={!selected.length||!!working} onClick={()=>void bulk(true)}>Enable selected</button>
          <button className="secondary-button" disabled={!selected.length||!!working} onClick={()=>void bulk(false)}>Disable selected</button>
        </div>}
      </div>
      <div className="recovery-items">{records.map(r=>{
        const a=byId[r.account_id]||{id:r.account_id};
        const paused=r.policy.pause_indefinite||(r.policy.pause_until!==null&&r.policy.pause_until>now/1000);
        return <article className="recovery-account" key={r.account_id}>
          <div className="recovery-account-top">
            {canWrite&&<label aria-label={"Select "+name(a)}><input type="checkbox" checked={selected.includes(r.account_id)} onChange={e=>setSelected(ids=>e.target.checked?[...ids,r.account_id]:ids.filter(id=>id!==r.account_id))}/></label>}
            <div className="row-avatar">{name(a).charAt(0).toUpperCase()}</div>
            <div className="recovery-account-name"><strong>{name(a)}</strong><small>{a.world||"Unknown world"} · {a.player||"Unknown player"}</small></div>
            <span className={"recovery-state "+(r.policy.enabled?"recovery-on":"")}>{r.policy.enabled?"Auto recovery on":"Manual only"}</span>
          </div>
          <div className="recovery-metrics">
            <div><small>Game session</small><strong>{label(r.session_status)}</strong></div>
            <div><small>Recovery</small><strong>{paused?"Paused for browser":label(r.event?.phase||"Idle")}</strong></div>
            <div><small>Countdown</small><strong>{paused?"Paused":deadline(r.event,now)||"—"}</strong></div>
            <div><small>Desired / restartable</small><strong>{r.desired_jobs} / {r.auto_resume_eligible}</strong></div>
          </div>
          {r.event?.last_reason&&<p className="recovery-hint">{label(r.event.last_reason)} · {r.event.attempts} attempt(s)</p>}
          {r.manual_review>0&&<p className="recovery-hint">{r.manual_review} ongoing task(s) require review, not automatic replay.</p>}
          <div className="recovery-account-actions">
            {r.server_token_available?<span className="recovery-token"><CheckCircle2 size={15}/> Protected lobby token available</span>:
            <span className="recovery-token recovery-token-missing"><CircleAlert size={15}/> Server lobby token not imported</span>}
            {canWrite&&!r.server_token_available&&<button className="secondary-button" disabled={!!working} onClick={()=>void importToken(r)}>Import saved token</button>}
            {canWrite&&<button className="secondary-button" disabled={!!working||!r.server_token_available&&!r.policy.enabled} onClick={()=>void save(r,!r.policy.enabled)}>{r.policy.enabled?"Disable":"Enable recovery"}</button>}
            {canWrite&&r.policy.enabled&&<>
              <select aria-label={"Pause recovery for "+name(a)} disabled={!!working} value="" onChange={e=>{if(e.target.value)void pause(r,e.target.value==="indefinite"?null:Number(e.target.value));e.target.value="";}}>
                <option value="" disabled>Pause browser use…</option><option value="900">15 minutes</option>
                <option value="1800">30 minutes</option><option value="3600">60 minutes</option>
                <option value="indefinite">Until I resume</option>
              </select>
              <button className="secondary-button" disabled={!!working||!data.supervisor_enabled} onClick={()=>void resume(r)}><PlayCircle size={15}/> Resume now</button>
            </>}
            <button className="secondary-button" onClick={()=>void review(r.account_id)}>Review jobs</button>
          </div>
          {jobAccount===r.account_id&&<div className="recovery-jobs">
            {!jobs?<p>Loading saved job records…</p>:jobs.jobs.length?<>{jobs.jobs.map(job=>
              <div className="recovery-job" key={job.id}><span><strong>{job.task}</strong><small>{label(job.desired_state)}</small></span>
                <span>{recoveryClassLabel(job.restart_class)}</span></div>)}
              {jobs.receipts.length>0&&<p>{jobs.receipts.length} restoration receipt(s). Unknown outcomes require manual reconciliation.</p>}
            </>:<p>No managed job configurations captured for this account. Old task IDs alone cannot reconstruct them.</p>}
          </div>}
        </article>;
      })}</div>
      <div className="panel-footer"><Clock3 size={17}/><span>The grace period begins after the server <strong>confirms</strong> session loss. No job restarts without verified player identity.</span></div>
      </>}
  </section>;
}
