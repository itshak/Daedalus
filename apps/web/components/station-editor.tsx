"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
type Plan={account_id:string;city_id:number;destination_city_id:number;city_name:string;destination_name:string;ground:boolean;total:number;weight:number|null;capacity:number|null;ready:boolean;preview_id:string|null;expires_in:number|null};
const TASK="stationArmy";
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function StationEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[city,setCity]=useState(0),[destination,setDestination]=useState(0),[ground,setGround]=useState(true);
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
  const valid=city!==destination&&cities.some(c=>c.id===city)&&cities.some(c=>c.id===destination);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/station-plan",{destination_city_id:destination,ground}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||p.destination_city_id!==destination||p.ground!==ground||
         !Number.isSafeInteger(p.total)||p.total<0||typeof p.city_name!=="string"||typeof p.destination_name!=="string"||
         (ground&&(!Number.isSafeInteger(p.weight)||!Number.isSafeInteger(p.capacity)||p.weight===null||p.capacity===null||p.weight<0||p.capacity<0))||
         (!ground&&(p.weight!==null||p.capacity!==null))||p.ready!==(p.total>0&&(!ground||p.weight!<=p.capacity!))||
         (p.ready&&(typeof p.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||typeof p.expires_in!=="number"||!Number.isInteger(p.expires_in)||p.expires_in<1||p.expires_in>120)))throw new Error("Invalid deployment preview");
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
      <label className="field"><span>{t("Units to deploy")}</span><select value={ground?"ground":"fleet"} onChange={e=>{clear();setGround(e.target.value==="ground");}}><option value="ground">{t("All available ground troops")}</option><option value="fleet">{t("All available fleet units")}</option></select></label>
      <button className="secondary-button" type="button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview deployment")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name} → {plan.destination_name}</h4>
      <p>{plan.total.toLocaleString()} · {t(plan.ground?"All available ground troops":"All available fleet units")}</p>
      {plan.ground&&<p>{t("Cargo weight")}: {plan.weight?.toLocaleString()} / {t("Transport capacity")}: {plan.capacity?.toLocaleString()}</p>}
      {plan.ready?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button className="primary-button" type="button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button></>:<p>{t("No available units or insufficient transport capacity.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
