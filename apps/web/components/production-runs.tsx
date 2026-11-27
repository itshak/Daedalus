"use client";

import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {verifyProductionRuns,verifyReconciliation,type ProductionRun,type ReconcileReview} from "../lib/production-contract";
type Account={id:string;name:string;enabled:boolean};
const expiresAt=(seconds:number)=>Date.now()+seconds*1000;

export function ProductionRuns({accounts,role}:{accounts:Account[];role:string}){
  const {t}=useLanguage();
  const [runs,setRuns]=useState<{account:Account;run:ProductionRun}[]>([]);
  const [loading,setLoading]=useState(false),[message,setMessage]=useState("");
  const [review,setReview]=useState<{value:ReconcileReview;deadline:number}|null>(null);
  const active=useRef(true),busy=useRef(false);
  useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
  async function call(path:string,body?:unknown){
    const res=await fetch("/api/controller/"+path,body===undefined?{cache:"no-store"}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!res.ok)throw Error("Unavailable");
    return res.json();
  }
  async function refresh(){
    if(busy.current)return;
    busy.current=true;setLoading(true);setReview(null);setMessage("");
    const found:typeof runs=[],failed:string[]=[];
    try{
      for(const account of accounts){
        if(!active.current)return;
        try{const raw=await call("accounts/"+encodeURIComponent(account.id)+"/production-runs");
          found.push(...verifyProductionRuns(raw,account.id).map(run=>({account,run})));
        }catch{failed.push(account.name);}
      }
      if(active.current){setRuns(found);setMessage(failed.length?t("Some accounts could not be retrieved:")+" "+failed.join(", "):found.length?"":"No production receipts");}
    }finally{busy.current=false;if(active.current)setLoading(false);}
  }
  async function reconcile(account:string,run:string){
    if(busy.current||role==="viewer"||!accounts.some(a=>a.id===account&&a.enabled))return;
    busy.current=true;setLoading(true);setReview(null);setMessage("");
    try{
      const value=verifyReconciliation(await call("accounts/"+encodeURIComponent(account)+"/production-runs/"+run+"/reconcile-plan",{}),account,run);
      if(active.current)setReview({value,deadline:expiresAt(value.expires_in!)});
    }catch{if(active.current)setMessage("Reconciliation unavailable. Stop the worker and resolve any uncertain launch in Activity first.");}
    finally{busy.current=false;if(active.current)setLoading(false);}
  }
  async function confirm(){
    if(!review||busy.current||role==="viewer")return;
    if(review.deadline<=Date.now()){setReview(null);setMessage("A review has expired. Prepare a new preview.");return;}
    if(!window.confirm(t("Acknowledge these actual counts and clear the production fence? This does not change any workers.")))return;
    const r=review.value;busy.current=true;setLoading(true);
    try{
      verifyReconciliation(await call("accounts/"+encodeURIComponent(r.account_id)+"/production-runs/"+r.run_id+"/reconcile",
        {preview_id:r.preview_id,request_id:crypto.randomUUID(),confirmed:true}),r.account_id,r.run_id,true);
      if(active.current){setReview(null);setRuns(previous=>previous.map(x=>x.account.id===r.account_id&&x.run.run_id===r.run_id?{...x,run:{...x.run,status:"reconciled"}}:x));setMessage("Production fence cleared. No workers were changed.");}
    }catch{if(active.current){setReview(null);setMessage("Reconciliation unavailable. Prepare a new review.");}}
    finally{busy.current=false;if(active.current)setLoading(false);}
  }
  return <section className="panel">
    <div className="panel-heading"><div><h3>{t("Production execution history")}</h3><p>{t("Actual stage receipts, not merely task launches. Pending assignments are never retried automatically.")}</p></div><button className="secondary-button" disabled={loading||!accounts.length} onClick={()=>void refresh()}>{t("Refresh")}</button></div>
    {message&&<p role="status">{t(message)}</p>}{loading&&<p role="status">{t("Loading…")}</p>}
    {runs.map(({account,run})=><div className="content-stack" key={account.id+":"+run.run_id}>
      <div className="report-tools"><strong>{account.name} · {t(run.status==="prepared"?"Running or needs review":run.status)}</strong>{run.status==="prepared"&&role!=="viewer"&&<button className="secondary-button" disabled={loading||!account.enabled} onClick={()=>void reconcile(account.id,run.run_id)}>{t("Review actual allocations")}</button>}</div>
      <div className="table-scroll"><table><thead><tr><th>{t("City")}</th><th>{t("Resource")}</th><th>{t("Status")}</th><th>{t("Execution stage")}</th><th>{t("Verified result")}</th></tr></thead><tbody>{run.cities.map(row=><tr key={row.city_id}>
        <td>{row.city_id}</td><td>{t(row.resource[0].toUpperCase()+row.resource.slice(1))}</td><td>{t(row.status)}</td>
        <td>{row.stages.map(s=><div key={s.stage}>{t(s.stage)}: {s.value} · {t(s.status)}{s.observed?" ("+t("Wood")+": "+s.observed.resource+", "+t("Luxury resource")+": "+s.observed.tradegood+")":""}</div>)}</td>
        <td>{row.result?t("Target")+": "+row.result.target+" · "+t("Donor")+": "+row.result.donor+" · "+t("Shortfall")+": "+row.result.shortfall:"—"}</td>
      </tr>)}</tbody></table></div>
    </div>)}
    {review&&<div className="content-stack">
      <p>{t("Review current counts. Acknowledging them does not restore or change workers; any further allocation requires a new plan.")}</p>
      <div className="table-scroll"><table><thead><tr><th>{t("City")}</th><th>{t("Wood")}</th><th>{t("Luxury resource")}</th></tr></thead><tbody>{review.value.observations.map(row=><tr key={row.city_id}><td>{row.city_name}</td><td>{row.resource}</td><td>{t(row.luxury[0].toUpperCase()+row.luxury.slice(1))}: {row.tradegood}</td></tr>)}</tbody></table></div>
      <div className="report-tools"><button className="secondary-button" disabled={loading} onClick={()=>setReview(null)}>{t("Cancel")}</button><button className="primary-button" disabled={loading} onClick={()=>void confirm()}>{t("Acknowledge reviewed counts")}</button></div>
    </div>}
  </section>;
}
