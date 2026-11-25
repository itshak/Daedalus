"use client";
import {useEffect,useState} from "react";
import {useLanguage} from "./language-provider";
import {ACTIVITY_STATUSES,activityCsv,scopedActivity,type ActivityFilter,type ActivityPage} from "@/lib/activity-history";
export function ActivityHistory({accounts,revision}:{accounts:{id:string;name:string}[];revision:number}){
  const {t}=useLanguage();
  const [account,setAccount]=useState("");
  const [status,setStatus]=useState<ActivityFilter>("all");
  const [before,setBefore]=useState<number|null>(null);
  const [result,setResult]=useState<{key:string;page:ActivityPage|null}|null>(null);
  const [refresh,setRefresh]=useState(0);
  const selected=accounts.some(a=>a.id===account)?account:(accounts[0]?.id??"");
  const requestKey=JSON.stringify([selected,status,before,refresh,revision]);
  const loading=Boolean(selected&&result?.key!==requestKey);
  const error=result?.key===requestKey&&result.page===null;
  useEffect(()=>{
    let live=true;
    if(!selected)return;
    const query=new URLSearchParams({limit:"50",status});
    if(before!==null)query.set("before",String(before));
    fetch("/api/controller/accounts/"+encodeURIComponent(selected)+"/activity?"+query,{cache:"no-store"})
      .then(async response=>{if(!response.ok)throw new Error("Unavailable");return scopedActivity(await response.json(),selected,before,status);})
      .then(page=>{if(live)setResult({key:requestKey,page});}).catch(()=>{if(live)setResult({key:requestKey,page:null});});
    return ()=>{live=false;};
  },[selected,status,before,requestKey]);
  const current=result?.key===requestKey&&result.page?.account_id===selected?result.page:null;
  const when=(v:number|null)=>v===null?t("Unknown"):new Date(v*1000).toLocaleString();
  const download=()=>{
    if(!current)return;
    const url=URL.createObjectURL(new Blob([activityCsv(current.events)],{type:"text/csv;charset=utf-8"}));
    const a=document.createElement("a");a.href=url;a.download="daedalus-receipts.csv";a.click();URL.revokeObjectURL(url);
  };
  return <section className="panel"><div className="panel-heading"><div><h3>{t("Server receipt history")}</h3><p>{t("Durable dispatch history; not raw engine logs or proof of task completion.")}</p></div></div>
    <div className="market-fields"><label className="field"><span>{t("Account")}</span><select value={selected} onChange={e=>{setAccount(e.target.value);setBefore(null);}}>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label className="field"><span>{t("Status")}</span><select value={status} onChange={e=>{setStatus(e.target.value as ActivityFilter);setBefore(null);}}><option value="all">{t("All statuses")}</option>{ACTIVITY_STATUSES.map(s=><option key={s} value={s}>{t(s.replaceAll("_"," "))}</option>)}</select></label></div>
    <div className="category-tabs"><button className="secondary-button" disabled={!selected||loading} onClick={()=>{setBefore(null);setRefresh(n=>n+1);}}>{t("Refresh")}</button><button className="secondary-button" disabled={loading||!current?.next_before} onClick={()=>setBefore(current?.next_before??null)}>{t("Older")}</button><button className="secondary-button" disabled={!current?.events.length||loading} onClick={download}>{t("Export CSV")}</button></div>
    {loading&&<p role="status">{t("Checking controller activity…")}</p>}{error&&<p role="alert">{t("Server receipt history unavailable.")}</p>}
    {current&&<>{current.events.length?<div className="activity-items">{current.events.map(row=><div className="activity-item" key={row.request_id}><div><strong>{row.task} · {t(row.status.replaceAll("_"," "))}</strong><small>{when(row.updated_at)} · {row.request_id}</small></div></div>)}</div>:<p>{t("No matching server receipts.")}</p>}</>}
  </section>;
}
