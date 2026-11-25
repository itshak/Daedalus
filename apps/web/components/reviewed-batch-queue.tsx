"use client";
import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from "react";
import {useLanguage} from "./language-provider";
import {launchReviewedBatch,type QueuedReview,type BatchResult} from "../lib/reviewed-batch";
type Queue={entries:QueuedReview[];busy:boolean;add:(entry:QueuedReview)=>boolean;remove:(account:string)=>void;clear:()=>void;start:()=>Promise<void>;results:BatchResult[];message:string};
const Context=createContext<Queue|null>(null);
export function ReviewedBatchProvider({role,children}:{role:string;children:ReactNode}){
  const {t}=useLanguage();
  const [entries,setEntries]=useState<QueuedReview[]>([]),[busy,setBusy]=useState(false),[results,setResults]=useState<BatchResult[]>([]),[message,setMessage]=useState("");
  const flight=useRef(false),mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  function add(entry:QueuedReview){
    if(role==="viewer"||flight.current||entries.length>=32||entries.some(e=>e.account_id===entry.account_id)||entry.expiresAt<=Date.now())return false;
    setEntries(old=>[...old,entry]);return true;
  }
  async function start(){
    if(role==="viewer"||flight.current||!entries.length)return;
    if(entries.some(e=>e.expiresAt<=Date.now())){setMessage("A review has expired. Remove it and prepare a new preview.");return;}
    if(!window.confirm(t("Start these independently approved operations? Every account is checked first. Dispatch stops on uncertainty; earlier starts are not rolled back.")))return;
    flight.current=true;setBusy(true);setMessage("");setResults([]);
    const draft=entries.map(({account_id,task,preview_id})=>({account_id,task,preview_id}));
    try{
      const result=await launchReviewedBatch(draft,async(path,body)=>{
        const res=await fetch("/api/controller/"+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
        if(!res.ok)throw new Error("Request unavailable");return res.json();
      },()=>crypto.randomUUID(),()=>mounted.current);
      if(mounted.current){setResults(result);setEntries([]);setMessage("Inspect Activity before retrying any operation.");}
    }catch{if(mounted.current){setMessage("Batch check unavailable. Inspect Activity before preparing new reviews.");setEntries([]);}}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  }
  return <Context.Provider value={{entries,busy,add,remove:account=>{if(!flight.current)setEntries(old=>old.filter(e=>e.account_id!==account));},clear:()=>{if(!flight.current)setEntries([]);},start,results,message}}>{children}</Context.Provider>;
}
export function QueueReviewButton({account,accountName,task,previewId,ttl,summary,disabled,onQueued}:{account:string;accountName:string;task:string;previewId:string|null;ttl:number|null;summary:string;disabled:boolean;onQueued:()=>void}){
  const queue=useContext(Context);
  const {t}=useLanguage();
  const [created]=useState(()=>Date.now());
  if(!queue||!previewId||!ttl)return null;
  return <button type="button" className="secondary-button" disabled={disabled||queue.busy||queue.entries.length>=32||queue.entries.some(e=>e.account_id===account)} onClick={()=>{
    if(queue.add({account_id:account,accountName,task,preview_id:previewId,summary,expiresAt:created+ttl*1000}))onQueued();
  }}>{t("Queue approved review")}</button>;
}
export function ReviewedBatchPanel(){
  const queue=useContext(Context);
  const {t}=useLanguage();
  if(!queue)return null;
  return <section className="panel"><div className="panel-heading"><div><h3>{t("Independent account review queue")}</h3><p>{t("Prepare and approve a separate preview for each account. Up to 32 distinct accounts; tickets expire after two minutes.")}</p></div></div>
    {!queue.entries.length?<p className="subtle-message">{t("No queued reviews. Choose an account, prepare a supported operation and queue its approved preview.")}</p>:<>
      <div className="simple-list">{queue.entries.map(e=><div className="list-row" key={e.account_id}><div className="list-main"><strong>{e.accountName} · {e.task}</strong><span style={{whiteSpace:"pre-line"}}>{e.summary}</span></div><button className="secondary-button" disabled={queue.busy} onClick={()=>queue.remove(e.account_id)}>{t("Remove")}</button></div>)}</div>
      <div className="report-tools"><button className="secondary-button" disabled={queue.busy} onClick={queue.clear}>{t("Clear")}</button><button className="primary-button" disabled={queue.busy} onClick={()=>void queue.start()}>{t("Review and start queued accounts")}</button></div>
    </>}
    {queue.results.length>0&&<ul>{queue.results.map(r=><li key={r.account_id}>{r.account_id} · {t(r.status)}{r.reason?" · "+r.reason:""}{r.request_id?" · "+r.request_id:""}</li>)}</ul>}{queue.message&&<p role="status">{t(queue.message)}</p>}
  </section>;
}
