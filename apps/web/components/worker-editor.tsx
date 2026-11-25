"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,validWorkerDraft,type WorkerTask,type City} from "@/lib/native-task-contract";

type Plan={task:WorkerTask;account_id:string;city_id:number;city_name:string;percentage:number;project:string|null;overcharge:boolean;current:number|null;maximum:number;extra:number;target:number;ready:boolean;preview_id:string;expires_in:number};
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function WorkerEditor({account,accountName,task,enabled,role}:{account:string;accountName:string;task:WorkerTask;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [city,setCity]=useState(0);
  const [percentage,setPercentage]=useState(100);
  const [project,setProject]=useState("resource");
  const [overcharge,setOvercharge]=useState(false);
  const [ready,setReady]=useState(false);
  const [plan,setPlan]=useState<Plan|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const mounted=useRef(false);
  const flight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  const production=task==="modifyProduction";
  const draft=production?{percentage,project,overcharge}:{percentage};
  useEffect(()=>{
    let live=true;mounted.current=true;
    if(account&&enabled)Promise.all([api(prefix+"/cities"),api(prefix+"/tasks/preflight?task="+task)]).then(([c,p])=>{
      if(live){setCities(scopedCities(c,account));setReady(readyPreflight(p,account,task));}
    }).catch(()=>{if(live)setMessage("Current inventory unavailable");});
    return ()=>{live=false;mounted.current=false;};
  },[account,enabled,prefix,task]);
  useEffect(()=>{
    if(!plan?.expires_in)return;
    const timer=window.setTimeout(()=>{setPlan(null);setApproved(false);setMessage("Review expired; prepare a new preview.");},plan.expires_in*1000);
    return ()=>window.clearTimeout(timer);
  },[plan]);
  const clear=()=>{setPlan(null);setApproved(false);setMessage("");};
  const valid=cities.some(c=>c.id===city)&&validWorkerDraft(task,draft);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/worker-plan",{task,draft}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.task!==task||p.city_id!==city||p.percentage!==percentage||
         p.project!==(production?project:null)||p.overcharge!==(production&&overcharge)||
         ![p.maximum,p.extra,p.target].every(n=>Number.isSafeInteger(n)&&n>=0&&n<=2_000_000)||
         (p.current!==null&&(!Number.isSafeInteger(p.current)||p.current<0))||
         p.target!==Math.floor(p.maximum*percentage/100)+(p.overcharge?p.extra:0)||
         p.ready!==true||typeof p.city_name!=="string"||typeof p.preview_id!=="string"||
         !/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||!Number.isInteger(p.expires_in)||p.expires_in<1||p.expires_in>120)throw new Error("Invalid preview");
      setPlan(p);
    }catch{if(mounted.current)setMessage("Worker preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const result=await api(prefix+"/tasks/worker-start",{task,preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(result.status==="started"&&result.account_id===account&&result.task===task?"Worker assignment started. Verify the city.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    {!ready&&<p>{t("Task prerequisites are not ready. Check the account and notifications.")}</p>}
    <fieldset disabled={disabled}><legend>{t("Worker assignment")}</legend>
      <label className="field"><span>{t("City")}</span><select value={city||""} onChange={e=>{clear();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}{c.coords?" · "+c.coords:""}</option>)}</select></label>
      {production&&<label className="field"><span>{t("Resource production")}</span><select value={project} onChange={e=>{clear();setProject(e.target.value);}}><option value="resource">{t("Forest")}</option><option value="tradegood">{t("Luxury resource")}</option></select></label>}
      <label className="field"><span>{t("Capacity percentage")} (%)</span><input type="number" min={0} max={100} value={Number.isNaN(percentage)?"":percentage} onChange={e=>{clear();const n=e.target.value===""?NaN:Number(e.target.value);setPercentage(n);if(n!==100)setOvercharge(false);}}/></label>
      {production&&<label className="check-label"><input type="checkbox" checked={overcharge} disabled={percentage!==100} onChange={e=>{clear();setOvercharge(e.target.checked);}}/>{t("Use overcharge (only at 100%)")}</label>}
      <button type="button" className="secondary-button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview worker assignment")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name}</h4>
      <p>{t("Current workers")}: {plan.current??t("Unknown")} · {t("Normal capacity")}: {plan.maximum} · {t("Extra capacity")}: {plan.extra}</p><p><strong>{t("Target workers")}: {plan.target}</strong></p>
      <p>{t("The game may reject the assignment if population is insufficient.")}</p>
      <label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button type="button" className="primary-button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button>
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
