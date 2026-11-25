"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
type Plan={account_id:string;city_id:number;target_city_id:number;city_name:string;target_name:string;send_notifications:boolean;level:number;requirements:{name:string;required:number;available:number}[];required_ships:number;available_ships:number;destroyed:boolean;notifications_ready:boolean;ready:boolean;preview_id:string|null;expires_in:number|null};
const TASK="autoBarbarians";
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function GrindEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[city,setCity]=useState(0),[target,setTarget]=useState(0),[notify,setNotify]=useState(false);
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
  const valid=cities.some(c=>c.id===city)&&cities.some(c=>c.id===target);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/grind-plan",{target_city_id:target,send_notifications:notify}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||p.target_city_id!==target||p.send_notifications!==notify||
         !Number.isInteger(p.level)||p.level<1||p.level>39||typeof p.city_name!=="string"||typeof p.target_name!=="string"||
         ![p.required_ships,p.available_ships].every(n=>Number.isSafeInteger(n)&&n>=0)||
         !Array.isArray(p.requirements)||!p.requirements.length||p.requirements.length>100||
         p.requirements.some(r=>typeof r.name!=="string"||!Number.isSafeInteger(r.required)||r.required<=0||!Number.isSafeInteger(r.available)||r.available<0)||
         typeof p.destroyed!=="boolean"||typeof p.notifications_ready!=="boolean"||
         p.ready!==(!p.destroyed&&p.notifications_ready&&p.available_ships>=p.required_ships&&p.requirements.every(r=>r.available>=r.required))||
         (p.ready&&(typeof p.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||typeof p.expires_in!=="number"||!Number.isInteger(p.expires_in)||p.expires_in<1||p.expires_in>120)))throw new Error("Invalid preview");
      setPlan(p);
    }catch{if(mounted.current)setMessage("Automatic attack preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const r=await api(prefix+"/tasks/grind-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task===TASK?"Automatic attacks started. Monitor Activity.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Automatic barbarian attacks")}</legend>
      <p>{t("Use the upstream preset for village levels 1–39. Attacks continue until stopped or prerequisites fail.")}</p>
      <label className="field"><span>{t("Origin city")}</span><select value={city||""} onChange={e=>{clear();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name} {c.coords}</option>)}</select></label>
      <label className="field"><span>{t("City on target island")}</span><select value={target||""} onChange={e=>{clear();setTarget(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name} {c.coords}</option>)}</select></label>
      <label className="check-label"><input type="checkbox" checked={notify} onChange={e=>{clear();setNotify(e.target.checked);}}/>{t("Send notifications")}</label>
      <button className="secondary-button" type="button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview automatic attacks")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name} → {plan.target_name}</h4>
      <p>{t("Village level")}: {plan.level} · {t("Ships")}: {plan.available_ships}/{plan.required_ships}</p>
      <table><thead><tr><th>{t("Unit")}</th><th>{t("Available")}</th><th>{t("Required")}</th></tr></thead><tbody>{plan.requirements.map((r,i)=><tr key={i}><td>{r.name}</td><td>{r.available}</td><td>{r.required}</td></tr>)}</tbody></table>
      {plan.ready?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button className="primary-button" type="button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="autoBarbarians" previewId={plan.preview_id} ttl={plan.expires_in} summary={plan.city_name+" → "+plan.target_name+" · village level "+plan.level+" · "+plan.requirements.map(r=>r.name+" × "+r.required).join(", ")+" · notifications "+(plan.send_notifications?"on":"off")} disabled={disabled||!approved||!valid||!plan.ready} onQueued={()=>{setLocked(true);setApproved(false);}}/></>:<p>{t("Village destroyed or prerequisites missing.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
