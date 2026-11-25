"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
import {validTrainingDraft,scopedTrainingPlan,TRAINING_RESOURCES,type TrainingDraft,type TrainingPlan} from "@/lib/training-contract";
type CatalogUnit={unit_type_id:number;local_name:string;costs:Record<string,number>};
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");return r.json();
}
export function TrainingEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[origin,setOrigin]=useState(0),[additional,setAdditional]=useState<number[]>([]);
  const [troops,setTroops]=useState(true),[units,setUnits]=useState<CatalogUnit[]>([]),[rounds,setRounds]=useState<Record<string,number>[]>([{}]),[index,setIndex]=useState(0),[cycles,setCycles]=useState(1);
  const [ready,setReady]=useState(false),[plan,setPlan]=useState<TrainingPlan|null>(null),[approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false),[locked,setLocked]=useState(false),[message,setMessage]=useState("");
  const mounted=useRef(false),flight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  useEffect(()=>{let live=true;mounted.current=true;if(account&&enabled)Promise.all([api(prefix+"/cities"),api(prefix+"/tasks/preflight?task=trainArmy")]).then(([c,p])=>{if(live){setCities(scopedCities(c,account));setReady(readyPreflight(p,account,"trainArmy"));}}).catch(()=>{if(live)setMessage("Current inventory unavailable");});return()=>{live=false;mounted.current=false;};},[account,enabled,prefix]);
  useEffect(()=>{let live=true;if(origin&&enabled)api(prefix+"/cities/"+origin+"/trainable-units?train_troops="+troops).then(value=>{
    const v=value as {account_id?:string;city_id?:number;train_troops?:boolean;units?:CatalogUnit[]};
    if(!live)return;
    if(v.account_id!==account||v.city_id!==origin||v.train_troops!==troops||!Array.isArray(v.units)||!v.units.length||
      v.units.some(u=>!Number.isInteger(u.unit_type_id)||typeof u.local_name!=="string"||!u.costs||typeof u.costs!=="object"))throw new Error("Invalid catalog");
    setUnits(v.units);
  }).catch(()=>{if(live)setMessage("Current inventory unavailable");});return()=>{live=false;};},[account,origin,troops,prefix,enabled]);
  useEffect(()=>{if(!plan?.expires_in)return;const timer=window.setTimeout(()=>{setPlan(null);setApproved(false);setMessage("Review expired; prepare a new preview.");},plan.expires_in*1000);return()=>window.clearTimeout(timer);},[plan]);
  const edit=()=>{setPlan(null);setApproved(false);setMessage("");};
  const reset=()=>{edit();setUnits([]);setRounds([{}]);setIndex(0);};
  const draft:TrainingDraft={city_ids:[origin,...additional],train_troops:troops,cycles,rounds:rounds.map(g=>units.filter(u=>g[u.unit_type_id]>0).map(u=>({unit_type_id:u.unit_type_id,cantidad:g[u.unit_type_id]})))};
  const valid=validTrainingDraft(draft)&&draft.city_ids.every(id=>cities.some(c=>c.id===id))&&rounds.every(g=>Object.values(g).every(n=>Number.isSafeInteger(n)&&n>=0&&n<=100000));
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const preview=async()=>{if(disabled||!valid||flight.current)return;edit();flight.current=true;setBusy(true);try{const p=scopedTrainingPlan(await api(prefix+"/cities/"+origin+"/training-plan",draft),account,draft,cities.map(c=>c.id));if(mounted.current)setPlan(p);}catch{if(mounted.current)setMessage("Recruitment preview unavailable.");}finally{flight.current=false;if(mounted.current)setBusy(false);}};
  const start=async()=>{if(disabled||!valid||!approved||!plan?.preview_id||flight.current)return;flight.current=true;setLocked(true);setApproved(false);setBusy(true);const rid=crypto.randomUUID();try{const r=await api(prefix+"/tasks/training-start",{preview_id:plan.preview_id,confirmed:true,request_id:rid}) as {status?:string;account_id?:string;task?:string;request_id?:string};if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task==="trainArmy"&&r.request_id===rid?"Recruitment task started. Verify training queues.":"Request recorded. Check Activity before another attempt.");}catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}finally{flight.current=false;if(mounted.current)setBusy(false);}};
  const summary=plan?plan.cities.map(c=>c.city_name+"\n"+c.rounds.map((g,i)=>t("Round")+" "+(i+1)+": "+g.map(u=>u.local_name+" × "+u.cantidad).join(", ")).join("\n")+"\n"+t("Total commitment")+": "+c.total_costs.map((n,i)=>TRAINING_RESOURCES[i]+" "+n.toLocaleString()).join("; ")).join("\n\n")+"\n"+t("Total cycles")+": "+plan.cycles:"";
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Recruitment plan")}</legend>
      <label className="field"><span>{t("City")}</span><select value={origin||""} onChange={e=>{reset();const id=Number(e.target.value);setOrigin(id);setAdditional(old=>old.filter(x=>x!==id));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}{c.coords?" · "+c.coords:""}</option>)}</select></label>
      <label className="field"><span>{t("Recruit")}</span><select value={troops?"troops":"fleet"} onChange={e=>{reset();setTroops(e.target.value==="troops");}}><option value="troops">{t("Land units")}</option><option value="fleet">{t("Warships")}</option></select></label>
      <fieldset><legend>{t("Additional owned cities")}</legend><button type="button" className="secondary-button" disabled={!origin||cities.length>32} onClick={()=>{edit();setAdditional(cities.filter(c=>c.id!==origin).map(c=>c.id));}}>{t("Select all cities")}</button>{cities.filter(c=>c.id!==origin).map(c=><label key={c.id} className="check-label"><input type="checkbox" checked={additional.includes(c.id)} disabled={!origin||(!additional.includes(c.id)&&additional.length>=31)} onChange={e=>{edit();setAdditional(old=>e.target.checked?[...old,c.id]:old.filter(id=>id!==c.id));}}/>{c.name}{c.coords?" · "+c.coords:""}</label>)}</fieldset>
      <label className="field"><span>{t("Total cycles")}</span><input type="number" min={1} max={10} value={Number.isNaN(cycles)?"":cycles} onChange={e=>{edit();setCycles(e.target.value===""?NaN:Number(e.target.value));}}/></label>
      <div className="report-tools"><label className="field"><span>{t("Round")}</span><select value={index} onChange={e=>setIndex(Number(e.target.value))}>{rounds.map((_,i)=><option key={i} value={i}>{t("Round")} {i+1}</option>)}</select></label><button type="button" className="secondary-button" disabled={!units.length||rounds.length>=10} onClick={()=>{edit();setRounds(old=>[...old,{}]);setIndex(rounds.length);}}>{t("Add round")}</button><button type="button" className="secondary-button" disabled={rounds.length<=1} onClick={()=>{edit();setRounds(old=>old.filter((_,i)=>i!==index));setIndex(Math.max(0,index-1));}}>{t("Remove round")}</button></div>
      {units.map(u=><label className="field" key={u.unit_type_id}><span>{u.local_name}</span><small>{Object.entries(u.costs).filter(([,n])=>n>0).map(([k,n])=>k+" "+n).join(" · ")}</small><input type="number" min={0} max={100000} value={rounds[index][u.unit_type_id]??0} onChange={e=>{edit();const value=e.target.value===""?0:Number(e.target.value);setRounds(old=>old.map((g,i)=>i===index?{...g,[u.unit_type_id]:value}:g));}}/></label>)}
      <button type="button" className="secondary-button" disabled={!valid||disabled} onClick={()=>void preview()}>{t("Preview recruitment rounds")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName}</h4><p style={{whiteSpace:"pre-line"}}>{summary}</p>{plan.cities.map(c=><p key={c.city_id}>{c.city_name}: {t(c.ready?"First round affordable":"Insufficient initial stock")}</p>)}<p>{t("Later rounds stop if stock, costs or training queue changes. Manual recovery only.")}</p>{plan.ready&&<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button type="button" className="primary-button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="trainArmy" previewId={plan.preview_id} ttl={plan.expires_in} summary={summary} disabled={disabled||!approved||!valid} onQueued={()=>{setLocked(true);setApproved(false);}}/></>}</section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
