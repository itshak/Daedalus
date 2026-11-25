"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
type Plan={account_id:string;city_id:number;city_name:string;active_jobs:number;managed_active:boolean;recovery_disabled:boolean;ready:boolean;preview_id:string|null;expires_in:number|null};
const TASK="vacationMode";
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function VacationEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[city,setCity]=useState(0);
  const [ready,setReady]=useState(false),[approved,setApproved]=useState(false);
  const [plan,setPlan]=useState<Plan|null>(null),[busy,setBusy]=useState(false),[locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const mounted=useRef(false),flight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  useEffect(()=>{
    let live=true;mounted.current=true;
    if(account&&enabled)Promise.all([api(prefix+"/cities"),api(prefix+"/tasks/preflight?task="+TASK)]).then(([c,p])=>{
      if(live){setCities(scopedCities(c,account));setReady(readyPreflight(p,account,TASK));}
    }).catch(()=>{if(live)setMessage("Current inventory unavailable");});
    return ()=>{live=false;mounted.current=false;};
  },[account,enabled,prefix]);
  useEffect(()=>{
    if(!plan?.expires_in)return;
    const timer=window.setTimeout(()=>{setPlan(null);setApproved(false);setMessage("Review expired; prepare a new preview.");},plan.expires_in*1000);
    return ()=>window.clearTimeout(timer);
  },[plan]);
  const clear=()=>{setPlan(null);setApproved(false);setMessage("");};
  const valid=cities.some(c=>c.id===city);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/vacation-plan",{}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||typeof p.city_name!=="string"||
         !Number.isInteger(p.active_jobs)||p.active_jobs<0||p.active_jobs>10000||
         typeof p.managed_active!=="boolean"||typeof p.recovery_disabled!=="boolean"||
         p.ready!==(p.active_jobs===0&&!p.managed_active&&p.recovery_disabled)||
         (p.ready&&(typeof p.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||typeof p.expires_in!=="number"||!Number.isInteger(p.expires_in)||p.expires_in<1||p.expires_in>120)))throw new Error("Invalid preview");
      setPlan(p);
    }catch{if(mounted.current)setMessage("Vacation preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const r=await api(prefix+"/tasks/vacation-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task===TASK?"Vacation request started. Verify in game; keep recovery disabled.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Activate vacation mode")}</legend>
      <p role="alert">{t("Vacation mode affects the entire account and may suspend game access. Stop every job and disable automatic recovery first. Keep recovery disabled until you manually end vacation.")}</p>
      <label className="field"><span>{t("City (account identity)")}</span><select value={city||""} onChange={e=>{clear();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <button type="button" className="secondary-button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview vacation activation")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName}</h4>
      <p>{t("Active jobs")}: {plan.active_jobs} · {t("Automatic recovery")}: {t(plan.recovery_disabled?"Disabled":"Enabled")}</p>
      {(plan.active_jobs>0||plan.managed_active)&&<p>{t("Stop all active account jobs first.")}</p>}
      {!plan.recovery_disabled&&<p>{t("Disable automatic recovery in Recovery settings first.")}</p>}
      {plan.ready&&<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve activating vacation mode for this entire account")}</label><button className="primary-button" type="button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Activate vacation mode")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="vacationMode" previewId={plan.preview_id} ttl={plan.expires_in} summary={plan.city_name+" · activate vacation mode for the entire account"} disabled={disabled||!approved||!valid||!plan.ready} onQueued={()=>{setLocked(true);setApproved(false);}}/></>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
