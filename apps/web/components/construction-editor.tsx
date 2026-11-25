"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {useEffect, useRef, useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedConstructionPlan,validSupply,type ConstructionPlan,type SupplyOptions,type Target} from "@/lib/construction-contract";
import {scopedCities, type City} from "@/lib/native-task-contract";

type Building = {position:number; name:string; level:number; busy:boolean; can_upgrade:boolean};
async function request(path:string, body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function ConstructionEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [city,setCity]=useState(0);
  const [buildings,setBuildings]=useState<Building[]>([]);
  const [targets,setTargets]=useState<Target[]>([]);
  const [plan,setPlan]=useState<ConstructionPlan|null>(null);
  const [supplyMode,setSupplyMode]=useState("self");
  const [sources,setSources]=useState<number[]>([]);
  const [freighters,setFreighters]=useState(false),[roundUp,setRoundUp]=useState(false);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const [loadError,setLoadError]=useState(false);
  const revision=useRef(0);
  const inFlight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  useEffect(()=>{
    let active=true;
    if(account&&enabled)request(prefix+"/cities").then(v=>{if(active)setCities(scopedCities(v,account));}).catch(()=>{if(active)setLoadError(true);});
    return ()=>{active=false;revision.current++;};
  },[account,enabled,prefix]);
  useEffect(()=>{
    let active=true;
    if(city)request(prefix+"/cities/"+city+"/buildings").then(v=>{
      if(!active)return;
      const result=v as {account_id?:unknown;city_id?:unknown;buildings?:Building[];synthetic_demo?:boolean};
      if(result.account_id!==account||result.city_id!==city||result.synthetic_demo||!Array.isArray(result.buildings)){setLoadError(true);return;}
      setBuildings(result.buildings.filter(b=>Number.isInteger(b.position)&&Number.isInteger(b.level)&&typeof b.name==="string"&&!b.busy&&b.can_upgrade));
    }).catch(()=>{if(active)setLoadError(true);});
    return ()=>{active=false;};
  },[account,city,prefix]);
  useEffect(()=>{
    if(!plan?.preview_id||!plan.expires_in)return;
    const id=window.setTimeout(()=>{setPlan(null);setApproved(false);setMessage("Review expired; prepare a new preview.");},plan.expires_in*1000);
    return ()=>window.clearTimeout(id);
  },[plan]);
  const invalidate=()=>{revision.current++;setPlan(null);setApproved(false);setMessage("");};
  const changeCity=(id:number)=>{invalidate();setCity(id);setBuildings([]);setTargets([]);setSources([]);setSupplyMode("self");setFreighters(false);setRoundUp(false);setLoadError(false);};
  const changeTarget=(position:number,level:number|null)=>{
    invalidate();
    setTargets(old=>level===null?old.filter(x=>x.position!==position):old.some(x=>x.position===position)?old.map(x=>x.position===position?{position,target_level:level}:x):[...old,{position,target_level:level}]);
  };
  const supply:SupplyOptions|undefined=supplyMode==="self"?undefined:{source_ids:sources,useFreighters:freighters,round_up:roundUp,supply_only:supplyMode==="only"};
  const valid=(!supply||validSupply(supply,city)&&sources.every(id=>cities.some(c=>c.id===id)))&&cities.some(c=>c.id===city)&&targets.length>0&&targets.length<=12&&targets.every(x=>{
    const b=buildings.find(y=>y.position===x.position);
    return !!b&&Number.isInteger(x.target_level)&&x.target_level>b.level&&x.target_level<=Math.min(150,b.level+10);
  });
  const disabled=busy||locked||!enabled||role==="viewer";
  const prepare=async()=>{
    if(disabled||!valid||inFlight.current)return;
    invalidate();const key=revision.current;inFlight.current=true;setBusy(true);
    try{
      const result=await request(prefix+"/cities/"+city+"/construction-plan",{upgrades:targets,...(supply?{supply}:{})});
      if(revision.current!==key)return;
      setPlan(scopedConstructionPlan(result,account,city,targets,supply,cities.map(c=>c.id)));
    }catch{if(revision.current===key)setMessage("Construction preview unavailable.");}
    finally{inFlight.current=false;setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||inFlight.current)return;
    inFlight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const receipt=await request(prefix+"/tasks/construction-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string};
      setMessage(receipt.status==="started"?"Task started. See Activity for status.":"Request recorded. Check Activity before another attempt.");
    }catch{setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{inFlight.current=false;setBusy(false);}
  };
  const resources=["Wood","Wine","Marble","Glass","Sulfur"];
  return <section className="native-automation-editor">
    {loadError&&<p role="alert">{t("Current inventory unavailable")}</p>}
    <fieldset disabled={disabled}><legend>{t("Construction queue")}</legend>
      <label className="field"><span>{t("City")}</span><select value={city||""} onChange={e=>changeCity(Number(e.target.value))}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}{c.coords?" · "+c.coords:""}</option>)}</select></label>
      {buildings.map(b=>{
        const target=targets.find(x=>x.position===b.position);
        return <div key={b.position} className="building-item"><label className="check-label"><input type="checkbox" checked={!!target} disabled={!target&&targets.length>=12} onChange={e=>changeTarget(b.position,e.target.checked?b.level+1:null)}/>{b.name} · {t("Level")} {b.level}</label>{target&&<label className="field"><span>{t("Target level")}</span><input type="number" min={b.level+1} max={Math.min(150,b.level+10)} value={Number.isNaN(target.target_level)?"":target.target_level} onChange={e=>changeTarget(b.position,e.target.value===""?NaN:Number(e.target.value))}/></label>}</div>;
      })}
      {targets.length>0&&<ol>{targets.map(x=><li key={x.position}>{buildings.find(b=>b.position===x.position)?.name} → {x.target_level}<button type="button" className="secondary-button" disabled={targets[0].position===x.position} onClick={()=>{invalidate();setTargets(old=>{const copy=[...old];const i=copy.findIndex(y=>y.position===x.position);[copy[i-1],copy[i]]=[copy[i],copy[i-1]];return copy;});}}>{t("Move up")}</button></li>)}</ol>}
      <label className="field"><span>{t("Construction supply (optional)")}</span><select value={supplyMode} onChange={e=>{invalidate();setSupplyMode(e.target.value);}}><option value="self">{t("Self-funded construction")}</option><option value="build">{t("Send supplies and build")}</option><option value="only">{t("Send supplies only")}</option></select></label>
      {supplyMode!=="self"&&<fieldset><legend>{t("Owned construction supplier cities")}</legend>
      <button type="button" className="secondary-button" disabled={!city||cities.length>21} onClick={()=>{invalidate();setSources(cities.filter(c=>c.id!==city).map(c=>c.id));}}>{t("Select all cities")}</button>
      {cities.filter(c=>c.id!==city).map(c=><label className="check-label" key={c.id}><input type="checkbox" checked={sources.includes(c.id)} disabled={!city||(!sources.includes(c.id)&&sources.length>=20)} onChange={e=>{invalidate();setSources(old=>e.target.checked?[...old,c.id]:old.filter(id=>id!==c.id));}}/>{c.name}{c.coords?" · "+c.coords:""}</label>)}
      <label className="check-label"><input type="checkbox" checked={freighters} onChange={e=>{invalidate();setFreighters(e.target.checked);}}/>{t("Use freighters")}</label>
      <label className="check-label"><input type="checkbox" checked={roundUp} onChange={e=>{invalidate();setRoundUp(e.target.checked);}}/>{t("Round up shipment amounts")}</label>
      </fieldset>}
      <button type="button" className="secondary-button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview construction queue")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name}</h4>
      <ol>{plan.buildings.map(b=><li key={b.position}>{b.name}: {b.current_level} → {b.target_level}</li>)}</ol>
      <div className="table-scroll"><table><thead><tr><th>{t("Resource")}</th><th>{t("Required")}</th><th>{t("Missing")}</th></tr></thead><tbody>{resources.map((name,i)=><tr key={name}><td>{t(name)}</td><td>{plan.costs[i]}</td><td>{plan.missing[i]}</td></tr>)}</tbody></table></div>
      <p>{t("Estimated duration (seconds)")}: {plan.estimated_seconds} {plan.supply&&t("(construction only)")}</p>
      {plan.supply&&<><p>{t(plan.supply.options.supply_only?"Send supplies only":"Send supplies and build")}</p>
        {plan.supply.shipment&&<><p>{t(plan.supply.options.useFreighters?"Freighters":"Trade ships")} · {plan.supply.shipment.available_ships}/{plan.supply.shipment.total_ships} · {t("Capacity")}: {plan.supply.shipment.capacity}</p><div className="table-scroll"><table><thead><tr><th>{t("Route")}</th><th>{t("Cargo")}</th><th>{t("Minimum loads")}</th><th>{t("First-load estimate (seconds)")}</th></tr></thead><tbody>{plan.supply.shipment.routes.map(r=><tr key={r.from}><td>{r.origin_name} → {r.destination_name}</td><td>{r.resources.map((n,i)=>n?t(resources[i])+" "+n.toLocaleString():null).filter(Boolean).join("; ")}</td><td>{r.minimum_loads??t("Unavailable")}</td><td>{r.first_load_timing? <>{r.first_load_timing.total_seconds.toLocaleString()}<p>{t("Queue")}: {r.first_load_timing.queue_seconds} · {t("Loading")}: {r.first_load_timing.loading_seconds} · {t("Travel")}: {r.first_load_timing.travel_seconds}</p></>:t("Unavailable")}</td></tr>)}</tbody></table></div></>}
        <p>{t("Uncovered shortage")}: {plan.supply.remaining.map((n,i)=>n?t(resources[i])+" "+n.toLocaleString():null).filter(Boolean).join("; ")||t("None")}</p><p>{t("Full multi-load ETA unavailable. Manual recovery only.")}</p></>}
      {plan.ready&&plan.preview_id?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button type="button" className="primary-button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="constructionList" previewId={plan.preview_id} ttl={plan.expires_in} summary={plan.city_name+" · "+plan.buildings.map(b=>b.name+": "+b.current_level+" → "+b.target_level).join("; ")+(plan.supply?"\n"+t(plan.supply.options.supply_only?"Send supplies only":"Send supplies and build")+"\n"+(plan.supply.shipment?.routes??[]).map(r=>r.origin_name+" → "+r.destination_name+" · "+r.resources.map((n,i)=>n?t(resources[i])+" "+n.toLocaleString():null).filter(Boolean).join("; ")).join("\n"):"")} disabled={disabled||!approved||!valid||!plan.ready} onQueued={()=>{setLocked(true);setApproved(false);}}/></>:<p role="alert">{t("Construction cannot start with this preview.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
