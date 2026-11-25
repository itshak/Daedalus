"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
import {scopedStationPlan,type StationPlan,type StationDraft} from "@/lib/station-contract";
const TASK="stationArmy";
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function StationEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[city,setCity]=useState(0),[destination,setDestination]=useState(0),[ground,setGround]=useState(true);
  const [allOrigins,setAllOrigins]=useState(false),[both,setBoth]=useState(false);
  const [ready,setReady]=useState(false),[approved,setApproved]=useState(false);
  const [plan,setPlan]=useState<StationPlan|null>(null),[busy,setBusy]=useState(false),[locked,setLocked]=useState(false);
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
  const valid=city!==destination&&cities.some(c=>c.id===city)&&cities.some(c=>c.id===destination);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const draft:StationDraft={destination_city_id:destination,ground:both||ground,...(allOrigins?{all_origins:true}:{}),...(both?{both:true}:{})};
      const value=await api(prefix+"/cities/"+city+"/station-plan",draft);
      if(!mounted.current)return;
      const p=scopedStationPlan(value,account,city,draft,cities.map(c=>c.id));
      setPlan(p);
    }catch{if(mounted.current)setMessage("Deployment preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const r=await api(prefix+"/tasks/station-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task===TASK?"Deployment task started. Verify military movements.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Station troops or fleet")}</legend>
      <label className="field"><span>{t("Origin city")}</span><select value={city||""} onChange={e=>{clear();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="field"><span>{t("Destination city")}</span><select value={destination||""} onChange={e=>{clear();setDestination(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.filter(c=>c.id!==city).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="check-label"><input type="checkbox" checked={allOrigins} onChange={e=>{clear();setAllOrigins(e.target.checked);}}/>{t("Include all other owned cities")}</label>
      <label className="field"><span>{t("Units to deploy")}</span><select value={both?"both":ground?"ground":"fleet"} onChange={e=>{clear();setBoth(e.target.value==="both");setGround(e.target.value!=="fleet");}}><option value="ground">{t("All available ground troops")}</option><option value="fleet">{t("All available fleet units")}</option><option value="both">{t("All available ground troops and fleet")}</option></select></label>
      <button className="secondary-button" type="button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview deployment")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name} → {plan.destination_name}</h4>
      {plan.deployments?<><table><thead><tr><th>{t("Origin city")}</th><th>{t("Units to deploy")}</th><th>{t("Total")}</th></tr></thead><tbody>{plan.deployments.map(r=><tr key={r.city_id+":"+r.ground}><td>{r.city_name}</td><td>{t(r.ground?"Ground troops":"Fleet units")}</td><td>{r.total.toLocaleString()}</td></tr>)}</tbody></table><p>{t("Total")}: {plan.total.toLocaleString()}</p><p>{t("Shared transport capacity; dispatch stops if a route changes.")}</p></>:<p>{plan.total.toLocaleString()} · {t(plan.ground?"All available ground troops":"All available fleet units")}</p>}
      {plan.ground&&<p>{t("Cargo weight")}: {plan.weight?.toLocaleString()} / {t("Transport capacity")}: {plan.capacity?.toLocaleString()}</p>}
      {plan.ready?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button className="primary-button" type="button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="stationArmy" previewId={plan.preview_id} ttl={plan.expires_in} summary={plan.deployments?plan.deployments.map(r=>r.city_name+" → "+plan.destination_name+" · "+r.total+" "+t(r.ground?"Ground troops":"Fleet units")).join("\n"):plan.city_name+" → "+plan.destination_name+" · "+plan.total+" "+t(plan.ground?"Ground troops":"Fleet units")} disabled={disabled||!approved||!valid||!plan.ready} onQueued={()=>{setLocked(true);setApproved(false);}}/></>:<p>{t("No available units or insufficient transport capacity.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
