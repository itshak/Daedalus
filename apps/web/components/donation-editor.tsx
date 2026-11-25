"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {MAX_AMOUNT,scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
type Project="resource"|"tradegood";
type Plan={account_id:string;city_id:number;city_name:string;project:Project;project_name:string;amount:number;stock:number;level:number;remaining:number;required:number;donated:number;upgrading:boolean;ready:boolean;preview_id:string|null;expires_in:number|null};
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function DonationEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [city,setCity]=useState(0);
  const [project,setProject]=useState<Project>("resource");
  const [amount,setAmount]=useState(1);
  const [ready,setReady]=useState(false);
  const [plan,setPlan]=useState<Plan|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const mounted=useRef(false);
  const flight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  useEffect(()=>{
    let live=true;mounted.current=true;
    if(account&&enabled)Promise.all([api(prefix+"/cities"),api(prefix+"/tasks/preflight?task=donate")]).then(([c,p])=>{
      if(live){setCities(scopedCities(c,account));setReady(readyPreflight(p,account,"donate"));}
    }).catch(()=>{if(live)setMessage("Current inventory unavailable");});
    return ()=>{live=false;mounted.current=false;};
  },[account,enabled,prefix]);
  useEffect(()=>{
    if(!plan?.expires_in)return;
    const timer=window.setTimeout(()=>{setPlan(null);setApproved(false);setMessage("Review expired; prepare a new preview.");},plan.expires_in*1000);
    return ()=>window.clearTimeout(timer);
  },[plan]);
  const clear=()=>{setPlan(null);setApproved(false);setMessage("");};
  const valid=cities.some(c=>c.id===city)&&Number.isSafeInteger(amount)&&amount>=1&&amount<=MAX_AMOUNT;
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const result=await api(prefix+"/cities/"+city+"/donation-plan",{project,amount}) as Plan;
      if(!mounted.current)return;
      if(result.account_id!==account||result.city_id!==city||result.project!==project||result.amount!==amount||
         typeof result.ready!=="boolean"||typeof result.upgrading!=="boolean"||
         ![result.stock,result.remaining,result.level,result.required,result.donated].every(n=>Number.isSafeInteger(n)&&n>=0)||
         typeof result.city_name!=="string"||typeof result.project_name!=="string"||
         (result.ready&&(!result.preview_id||!/^[A-Za-z0-9_-]{43}$/.test(result.preview_id)||!result.expires_in||result.expires_in>120)))throw new Error("Invalid preview");
      setPlan(result);
    }catch{if(mounted.current)setMessage("Donation preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const result=await api(prefix+"/tasks/donation-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(result.status==="started"&&result.account_id===account&&result.task==="donate"?"Donation task started. Verify the island balance.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    {!ready&&<p>{t("Task prerequisites are not ready. Check the account and notifications.")}</p>}
    <fieldset disabled={disabled}><legend>{t("Donate once")}</legend>
      <label className="field"><span>{t("City")}</span><select value={city||""} onChange={e=>{clear();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}{c.coords?" · "+c.coords:""}</option>)}</select></label>
      <label className="field"><span>{t("Island project")}</span><select value={project} onChange={e=>{clear();setProject(e.target.value as Project);}}><option value="resource">{t("Forest")}</option><option value="tradegood">{t("Luxury resource")}</option></select></label>
      <label className="field"><span>{t("Wood to donate")}</span><input type="number" min={1} max={MAX_AMOUNT} value={Number.isNaN(amount)?"":amount} onChange={e=>{clear();setAmount(e.target.value===""?NaN:Number(e.target.value));}}/></label>
      <button type="button" className="secondary-button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview island donation")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName}</h4><p>{plan.city_name} · {plan.project_name} · {t("Level")} {plan.level}</p>
      <p>{t("Wood available")}: {plan.stock.toLocaleString()} · {t("Project remaining")}: {plan.remaining.toLocaleString()}</p>
      <p>{t("Wood to donate")}: {plan.amount.toLocaleString()}</p>
      {plan.ready&&plan.preview_id?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button type="button" className="primary-button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="donate" previewId={plan.preview_id} ttl={plan.expires_in} summary={plan.city_name+" · "+plan.project_name+" · "+plan.amount.toLocaleString()+" wood"} disabled={disabled||!approved||!valid||!plan.ready} onQueued={()=>{setLocked(true);setApproved(false);}}/></>:<p role="alert">{t("Project is upgrading or the amount is unavailable.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
