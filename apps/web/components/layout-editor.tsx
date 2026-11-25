"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";

type Move={from:number;to:number;building:string;displaced:string};
type Plan={account_id:string;city_id:number;template_city_id:number;city_name:string;template_name:string;moves:Move[];ready:boolean;preview_id:string|null;expires_in:number|null};
const TASK="reorganizeCityBuildings";
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function LayoutEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [city,setCity]=useState(0),[template,setTemplate]=useState(0);
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
  const valid=city!==template&&cities.some(c=>c.id===city)&&cities.some(c=>c.id===template);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/layout-plan",{template_city_id:template}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||p.template_city_id!==template||
         typeof p.city_name!=="string"||typeof p.template_name!=="string"||!Array.isArray(p.moves)||p.moves.length>80||
         p.moves.some(m=>![m.from,m.to].every(n=>Number.isInteger(n)&&n>=0&&n<=80)||m.from===m.to||typeof m.building!=="string"||typeof m.displaced!=="string")||
         p.ready!==Boolean(p.moves.length)||(p.ready&&(typeof p.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||typeof p.expires_in!=="number"||!Number.isInteger(p.expires_in)||p.expires_in<1||p.expires_in>120)))throw new Error("Invalid preview");
      setPlan(p);
    }catch{if(mounted.current)setMessage("Layout preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const r=await api(prefix+"/tasks/layout-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task===TASK?"Layout task started. Verify the city.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Copy city layout")}</legend>
      <label className="field"><span>{t("Template city")}</span><select value={template||""} onChange={e=>{clear();setTemplate(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="field"><span>{t("Target city")}</span><select value={city||""} onChange={e=>{clear();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.filter(c=>c.id!==template).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <button className="secondary-button" type="button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview layout changes")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.template_name} → {plan.city_name}</h4>
      {plan.moves.length?<><ol>{plan.moves.map((m,i)=><li key={i}>{m.building} · {m.from} → {m.to} ({m.displaced})</li>)}</ol>
      <label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label>
      <button className="primary-button" type="button" disabled={disabled||!approved||!plan.ready} onClick={()=>void start()}>{t("Start automation")}</button></>:<p>{t("No applicable layout swaps.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
