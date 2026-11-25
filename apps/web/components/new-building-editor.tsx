"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
type Option={position:number;building_id:number;name:string;surface:string;costs:number[];ready:boolean};
type Plan=Option&{account_id:string;city_id:number;city_name:string;available:number[];missing:number[];busy:boolean;preview_id:string|null;expires_in:number|null};
const TASK="constructBuilding";
const resources=["Wood","Wine","Marble","Glass","Sulfur"];
const quantities=(v:unknown):v is number[]=>Array.isArray(v)&&v.length===5&&v.every(n=>Number.isSafeInteger(n)&&n>=0&&n<=1e15);
const validOption=(v:Option)=>v&&Number.isInteger(v.position)&&v.position>=0&&v.position<=80&&Number.isInteger(v.building_id)&&v.building_id>0&&v.building_id<1e6&&typeof v.name==="string"&&["sea","land","shore","wall","dockyard"].includes(v.surface)&&quantities(v.costs)&&v.costs.some(n=>n>0)&&typeof v.ready==="boolean";
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function NewBuildingEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[city,setCity]=useState(0);
  const [options,setOptions]=useState<Option[]>([]),[choice,setChoice]=useState("");
  const [ready,setReady]=useState(false),[approved,setApproved]=useState(false);
  const [plan,setPlan]=useState<Plan|null>(null),[busy,setBusy]=useState(false),[locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const mounted=useRef(false),flight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  const selected=options.find(o=>choice===o.position+":"+o.building_id);
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
  const load=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();setOptions([]);setChoice("");flight.current=true;setBusy(true);
    try{
      const data=await api(prefix+"/cities/"+city+"/build-options") as {account_id:string;city_id:number;options:Option[]};
      if(!mounted.current)return;
      if(data.account_id!==account||data.city_id!==city||!Array.isArray(data.options)||data.options.length>500||!data.options.every(validOption))throw new Error("Invalid building inventory");
      setOptions(data.options);
      if(!data.options.length)setMessage("No available building choices.");
    }catch{if(mounted.current)setMessage("Building options unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const prepare=async()=>{
    if(disabled||!valid||!selected||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/build-plan",{position:selected.position,building_id:selected.building_id}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||p.position!==selected.position||p.building_id!==selected.building_id||!validOption(p)||!quantities(p.available)||!quantities(p.missing)||typeof p.busy!=="boolean"||p.ready!==(!p.busy&&p.missing.every(n=>n===0))||(p.ready&&(typeof p.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||typeof p.expires_in!=="number"||!Number.isInteger(p.expires_in)||p.expires_in<1||p.expires_in>120)))throw new Error("Invalid preview");
      setPlan(p);
    }catch{if(mounted.current)setMessage("Building preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!selected||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const r=await api(prefix+"/tasks/build-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task===TASK?"Building task started. Verify the city.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Build new building")}</legend>
      <label className="field"><span>{t("City")}</span><select value={city||""} onChange={e=>{clear();setOptions([]);setChoice("");setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <button type="button" className="secondary-button" disabled={disabled||!valid} onClick={()=>void load()}>{t("Load building options")}</button>
      <label className="field"><span>{t("Available building")}</span><select value={choice} onChange={e=>{clear();setChoice(e.target.value);}}><option value="">{t("Choose building and slot")}</option>{options.map(o=><option key={o.position+":"+o.building_id} value={o.position+":"+o.building_id}>{o.name} · {t("Slot")} {o.position} ({o.surface}){o.ready?"":" — "+t("Not ready")}</option>)}</select></label>
      <button className="secondary-button" type="button" disabled={disabled||!valid||!selected} onClick={()=>void prepare()}>{t("Preview building cost")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name}</h4><p>{plan.name} · {t("Slot")} {plan.position}</p>
      <table><thead><tr><th>{t("Resource")}</th><th>{t("Cost")}</th><th>{t("Available")}</th><th>{t("Missing")}</th></tr></thead><tbody>{resources.map((r,i)=><tr key={r}><td>{t(r)}</td><td>{plan.costs[i].toLocaleString()}</td><td>{plan.available[i].toLocaleString()}</td><td>{plan.missing[i].toLocaleString()}</td></tr>)}</tbody></table>
      {plan.ready?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button className="primary-button" type="button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button></>:<p>{t("City is busy or materials are missing.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
