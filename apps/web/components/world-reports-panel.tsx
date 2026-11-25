"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {collectWorldCsv,parseWorldReports,type WorldReports} from "../lib/world-reports";
export function WorldReportsPanel({accounts}:{accounts:{id:string;name:string}[]}){
  const {t}=useLanguage();
  const [selected,setSelected]=useState(""),[report,setReport]=useState(""),[value,setValue]=useState<WorldReports|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const flight=useRef(false),mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const account=accounts.some(a=>a.id===selected)?selected:"";
  const api=async(path:string)=>{const response=await fetch("/api/controller/accounts/"+encodeURIComponent(account)+"/world-reports"+path,{cache:"no-store"});if(!response.ok)throw new Error("Unavailable");return response.json();};
  async function read(){
    if(!account||flight.current)return;
    flight.current=true;setBusy(true);setReport("");setValue(null);setMessage("");
    try{setValue(parseWorldReports(await api(""),account));}
    catch{setMessage("Aggregate map reports unavailable. Refresh before retrying.");}
    finally{flight.current=false;setBusy(false);}
  }
  async function download(){
    if(!account||!value?.reports.some(r=>r.report_id===report)||flight.current)return;
    flight.current=true;setBusy(true);setMessage("");
    try{
      const csv=await collectWorldCsv(offset=>api("/"+report+"?offset="+offset),account,report);
      if(!mounted.current)return;
      const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
      try{const a=document.createElement("a");a.href=url;a.download="Daedalus-world-map-"+report.slice(0,8)+".csv";document.body.appendChild(a);a.click();a.remove();}
      finally{window.setTimeout(()=>URL.revokeObjectURL(url),1000);}
      setMessage("Complete aggregate report exported.");
    }catch{setMessage("Aggregate map reports unavailable. Refresh before retrying.");}
    finally{flight.current=false;setBusy(false);}
  }
  return <section className="panel"><div className="panel-heading"><div><h3>{t("Aggregate world map reports")}</h3><p>{t("Completed managed scans, without player names or raw game responses.")}</p></div></div>
    <label className="field"><span>{t("Account")}</span><select value={account} disabled={busy} onChange={e=>{setSelected(e.target.value);setValue(null);setReport("");setMessage("");}}><option value="">{t("Choose an account")}</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
    <button type="button" className="secondary-button" disabled={!account||busy} onClick={()=>void read()}>{t("Read completed map reports")}</button>
    {value&&value.account_id===account&&<>{value.reports.length?<label className="field"><span>{t("Report")}</span><select value={report} disabled={busy} onChange={e=>setReport(e.target.value)}><option value="">{t("Choose report")}</option>{value.reports.map(r=><option value={r.report_id} key={r.report_id}>{new Date(r.completed_at*1000).toLocaleString()} · {t(r.shallow?"Shallow":"Detailed aggregate")} · {t(r.partial?"Partial":"Whole map")} · {r.island_count} {t("islands")}</option>)}</select></label>:<p>{t("No completed map reports")}</p>}
    <button type="button" className="secondary-button" disabled={!report||busy} onClick={()=>void download()}>{t("Export selected report to CSV")}</button></>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
