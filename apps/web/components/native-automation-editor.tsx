"use client";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { useLanguage } from "./language-provider";
import { MATERIALS, MAX_AMOUNT, type City, type NativeTask, scopedCities, readyPreflight, validNativeConfig } from "@/lib/native-task-contract";

type Config = Record<string,unknown>;
type Route = {key:number; from:number; to:number; resources:number[]};
type Props = {account:string; accountName:string; task:NativeTask; enabled:boolean; role:string};
const zeros = () => [0,0,0,0,0];
const route = (key:number):Route => ({key,from:0,to:0,resources:zeros()});
async function api(path:string, body?:unknown):Promise<unknown> {
  const response=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)
  })});
  if (!response.ok) throw new Error("Request unavailable");
  return response.json();
}

export function NativeAutomationEditor({account,accountName,task,enabled,role}:Props) {
  // Parent keys this component by account, task and refresh revision. A stale response
  // cannot populate another account's form or retain its review.
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [ready,setReady]=useState(false);
  const [loading,setLoading]=useState(Boolean(account&&enabled));
  const [loadError,setLoadError]=useState(false);
  const [routes,setRoutes]=useState<Route[]>([route(1)]);
  const nextRoute=useRef(2);
  const [minutes,setMinutes]=useState(20);
  const [hours,setHours]=useState(4);
  const [autoTransfer,setAutoTransfer]=useState(false);
  const [transferAmount,setTransferAmount]=useState(0);
  const [freighters,setFreighters]=useState(false);
  const [material,setMaterial]=useState("wood");
  const [policy,setPolicy]=useState("even");
  const [single,setSingle]=useState(0);
  const [multiple,setMultiple]=useState<number[]>([]);
  const [limits,setLimits]=useState<number[]>([-1,-1,-1,-1,-1]);
  const [resourceAmounts,setResourceAmounts]=useState<(number|null)[]>(zeros());
  const [ignored,setIgnored]=useState<boolean[]>([true,true,true,true,true]);
  const [interval,setInterval]=useState(1);
  const [fleet,setFleet]=useState(1);
  const [mode,setMode]=useState("consolidate");
  const [sendMode,setSendMode]=useState("keep");
  const [notify,setNotify]=useState("none");
  const [review,setReview]=useState<{config:Config;summary:string;fingerprint:string}|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const inFlight=useRef(false);
  const mounted=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  const cityTask=task!=="alertAttacks" && task!=="alertLowWine";
  useEffect(()=>{
    let alive=true;
    mounted.current=true;
    if (!account || !enabled) return ()=>{mounted.current=false;};
    Promise.all([
      api(prefix+"/tasks/preflight?task="+encodeURIComponent(task)),
      cityTask ? api(prefix+"/cities") : Promise.resolve(null)
    ]).then(([p,c])=>{
      if (!alive)return;
      setReady(readyPreflight(p,account,task));
      if (cityTask) setCities(scopedCities(c,account));
    }).catch(()=>{if(alive)setLoadError(true);}).finally(()=>{if(alive)setLoading(false);});
    return ()=>{alive=false;mounted.current=false;};
  },[account,enabled,prefix,task,cityTask]);
  const byId=new Map(cities.map(c=>[c.id,c.name+(c.coords?" · "+c.coords:"")]));
  const actual=(id:number)=>byId.has(id);
  const cityName=(id:number)=>byId.get(id)??t("Choose a city");
  const materialName=(m:string)=>t(m==="crystal"?"Glass":m[0].toUpperCase()+m.slice(1));
  const resourceSummary=(a:(number|null)[],keep=false)=>a.map((v,i)=>
    materialName(MATERIALS[i])+": "+(v===null||v===-1?t("Ignore"):String(v))+(keep&&v!==null&&v>=0?" "+t("to keep"):"")).join("; ");
  const fleetName=freighters?t("Freighters"):t("Trade ships");
  const names=multiple.map(cityName).join(", ");
  let config:Config={};let summary="";let scoped=true;
  if(task==="alertAttacks"){config={minutes};summary=t("Check for attacks every")+" "+minutes+" "+t("minutes");}
  else if(task==="alertLowWine"){config={hours,auto_transfer:autoTransfer,transfer_amount:autoTransfer?transferAmount:0};
    summary=t("Warn when wine has less than")+" "+hours+" "+t("hours")+"; "+(autoTransfer?t("Automatic wine transfer")+": "+transferAmount:t("Notifications only"));}
  else if(task==="sendResources"){
    config={routes:routes.map(r=>({from:r.from,to:r.to,resources:r.resources})),useFreighters:freighters};
    scoped=routes.every(r=>actual(r.from)&&actual(r.to));
    summary=routes.map(r=>cityName(r.from)+" → "+cityName(r.to)+": "+resourceSummary(r.resources)).join("\n")+"\n"+fleetName;
  } else if(task==="distributeResources"){
    config={resource:material,mode:policy,cities_ids:multiple,useFreighters:freighters};
    scoped=multiple.every(actual);
    summary=materialName(material)+" · "+t(policy==="even"?"Balance evenly":"From producers")+" · "+names+" · "+fleetName;
  } else if(task==="consolidateResources"){
    config={limits,sourceCityIds:multiple,destinationCityId:single,intervalInHours:interval,shipType:fleet};
    scoped=actual(single)&&multiple.every(actual);
    summary=names+" → "+cityName(single)+"\n"+resourceSummary(limits,true)+"\n"+t("Repeat every")+" "+interval+" "+t("hours")+" · "+t(["Trade ships","Freighters","Both fleets"][fleet-1]);
  } else {
    const values=resourceAmounts.map((v,i)=>mode==="consolidate"&&ignored[i]?null:v);
    const common={mode,resource_config:values,interval_hours:interval,useFreighters:freighters,notify};
    config=mode==="consolidate"?{...common,origin_cities:multiple,destination_city:single,send_mode:sendMode}
      :{...common,origin_city:single,destination_cities:multiple};
    scoped=actual(single)&&multiple.every(actual);
    summary=(mode==="consolidate"?names+" → "+cityName(single):cityName(single)+" → "+names)+"\n"
      +resourceSummary(values,mode==="consolidate"&&sendMode==="keep")+"\n"+t("Repeat every")+" "+interval+" "+t("hours")+" · "+fleetName+" · "+t("Notifications")+": "+t(notify==="none"?"None":notify==="start"?"At start":"Every shipment");
  }
  const valid=scoped&&validNativeConfig(task,config);
  const fingerprint=JSON.stringify(config);
  const reviewed=review!==null&&review.fingerprint===fingerprint;
  const canReview=enabled&&role!=="viewer"&&ready&&!loading&&!loadError&&valid&&!locked&&!busy;
  const canLaunch=canReview&&reviewed&&approved;
  const edit=()=>{setReview(null);setApproved(false);};
  const numeric=(label:string,value:number,onChange:(v:number)=>void,min:number,max:number)=>
    <label className="field"><span>{label}</span><input type="number" min={min} max={max} step={1} value={Number.isNaN(value)?"":value}
      onChange={e=>{edit();onChange(e.target.value===""?NaN:Number(e.target.value));}}/></label>;
  const citySelect=(label:string,value:number,onChange:(v:number)=>void,exclude:number=0)=>
    <label className="field"><span>{label}</span><select value={value||""} onChange={e=>{edit();onChange(Number(e.target.value));}}>
      <option value="">{t("Choose a city")}</option>{cities.filter(c=>c.id!==exclude).map(c=><option key={c.id} value={c.id}>{cityName(c.id)}</option>)}</select></label>;
  const cityChecks=(label:string,exclude=0)=><fieldset><legend>{label}</legend>
    <button type="button" className="secondary-button" onClick={()=>{edit();setMultiple(cities.filter(c=>c.id!==exclude).map(c=>c.id));}}>{t("Select all cities")}</button>
    {cities.filter(c=>c.id!==exclude).map(c=><label key={c.id} className="check-label"><input type="checkbox" checked={multiple.includes(c.id)} onChange={e=>{edit();setMultiple(old=>e.target.checked?[...old,c.id]:old.filter(id=>id!==c.id));}}/>{cityName(c.id)}</label>)}
  </fieldset>;
  const fleetSelect=<label className="field"><span>{t("Fleet")}</span><select value={freighters?"freighters":"trade"} onChange={e=>{edit();setFreighters(e.target.value==="freighters");}}><option value="trade">{t("Trade ships")}</option><option value="freighters">{t("Freighters")}</option></select></label>;
  const amountsFields=(values:number[],change:(i:number,v:number)=>void)=>MATERIALS.map((m,i)=>
    <div key={m} className="native-resource-row"><Image src={`/ikariam-resources/${m==="crystal"?"glass":m}.webp`} alt="" width={25} height={20} unoptimized/>{numeric(materialName(m),values[i],v=>change(i,v),0,MAX_AMOUNT)}</div>);
  const changeRoute=(key:number,update:Partial<Route>)=>setRoutes(old=>old.map(r=>r.key===key?{...r,...update}:r));
  const launch=async()=>{
    if (!canLaunch || !review || inFlight.current)return;
    inFlight.current=true;setBusy(true);setLocked(true);setApproved(false);setMessage("");
    try {
      const current=await api(prefix+"/tasks/preflight?task="+encodeURIComponent(task));
      if(!mounted.current)return;
      if(!readyPreflight(current,account,task)){setMessage("Readiness changed; refresh and review again.");return;}
      const result=await api(prefix+"/tasks",{task,config:review.config,confirmed:true,request_id:crypto.randomUUID()});
      const receipt=result as {status?:unknown};
      if(mounted.current)setMessage(receipt.status==="started"?"Task started. See Activity for status.":"Request recorded. Check Activity before another attempt.");
    } catch {if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally {if(mounted.current)setBusy(false);inFlight.current=false;}
  };
  return <section className="native-automation-editor">
    {loading?<p role="status">{t("Retrieving authenticated controller data…")}</p>:loadError||!ready?<p role="alert">{t("Task prerequisites are not ready. Check the account and notifications.")}</p>:<p>{t("Ready to review")}</p>}
    {cityTask&&!loading&&cities.length<2&&<p role="alert">{t("At least two authenticated cities are required.")}</p>}
    <fieldset disabled={busy||locked||loading||!enabled||role==="viewer"}>
      <legend>{t("Settings")}</legend>
      {task==="alertAttacks"&&numeric(t("Check for attacks every (minutes)"),minutes,setMinutes,3,1440)}
      {task==="alertLowWine"&&<>{numeric(t("Warn when wine has less than (hours)"),hours,setHours,1,720)}<label className="check-label"><input type="checkbox" checked={autoTransfer} onChange={e=>{edit();setAutoTransfer(e.target.checked);}}/>{t("Automatic wine transfer")}</label>{autoTransfer&&numeric(t("Wine to transfer"),transferAmount,setTransferAmount,1,MAX_AMOUNT)}</>}
      {task==="sendResources"&&<>
        {routes.map((r,i)=><fieldset key={r.key}><legend>{t("Route")} {i+1}</legend>
          {citySelect(t("From city"),r.from,v=>changeRoute(r.key,{from:v,to:r.to===v?0:r.to}),r.to)}
          {citySelect(t("To city"),r.to,v=>changeRoute(r.key,{to:v}),r.from)}
          {amountsFields(r.resources,(j,v)=>changeRoute(r.key,{resources:r.resources.map((x,k)=>j===k?v:x)}))}
          <button type="button" className="secondary-button" disabled={routes.length===1} onClick={()=>{edit();setRoutes(old=>old.filter(x=>x.key!==r.key));}}>{t("Remove route")}</button>
        </fieldset>)}
        <button type="button" className="secondary-button" disabled={routes.length>=20} onClick={()=>{edit();const key=nextRoute.current++;setRoutes(old=>[...old,route(key)]);}}>{t("Add route")}</button>{fleetSelect}
      </>}
      {task==="distributeResources"&&<>
        <label className="field"><span>{t("Resource")}</span><select value={material} onChange={e=>{edit();setMaterial(e.target.value);if(e.target.value==="wood")setPolicy("even");}}>{MATERIALS.map(m=><option key={m} value={m}>{materialName(m)}</option>)}</select></label>
        <label className="field"><span>{t("Distribution policy")}</span><select value={policy} onChange={e=>{edit();setPolicy(e.target.value);}}><option value="even">{t("Balance evenly")}</option><option value="producers" disabled={material==="wood"}>{t("From producers")}</option></select></label>
        {cityChecks(t("Participating cities"))}{fleetSelect}
      </>}
      {task==="consolidateResources"&&<>
        {citySelect(t("To city"),single,v=>{setSingle(v);setMultiple(old=>old.filter(id=>id!==v));})}
        {cityChecks(t("Source cities"),single)}
        {MATERIALS.map((m,i)=><div key={m}><label className="check-label"><input type="checkbox" checked={limits[i]===-1} onChange={e=>{edit();setLimits(old=>old.map((v,j)=>i===j?(e.target.checked?-1:0):v));}}/>{t("Ignore")} {materialName(m)}</label>{limits[i]!==-1&&numeric(materialName(m)+" "+t("to keep"),limits[i],v=>setLimits(old=>old.map((x,j)=>i===j?v:x)),0,MAX_AMOUNT)}</div>)}
        {numeric(t("Repeat every (hours)"),interval,setInterval,1,336)}
        <label className="field"><span>{t("Fleet")}</span><select value={fleet} onChange={e=>{edit();setFleet(Number(e.target.value));}}>{["Trade ships","Freighters","Both fleets"].map((f,i)=><option key={f} value={i+1}>{t(f)}</option>)}</select></label>
      </>}
      {task==="resourceTransportManager"&&<>
        <label className="field"><span>{t("Transport strategy")}</span><select value={mode} onChange={e=>{edit();setMode(e.target.value);setSingle(0);setMultiple([]);}}><option value="consolidate">{t("Many cities to one")}</option><option value="distribute">{t("One city to many")}</option></select></label>
        {citySelect(t(mode==="consolidate"?"To city":"From city"),single,v=>{setSingle(v);setMultiple(old=>old.filter(id=>id!==v));})}
        {cityChecks(t(mode==="consolidate"?"Source cities":"Destination cities"),single)}
        {mode==="consolidate"&&<label className="field"><span>{t("Resource policy")}</span><select value={sendMode} onChange={e=>{edit();setSendMode(e.target.value);}}><option value="keep">{t("Keep reserve")}</option><option value="send">{t("Send fixed amounts")}</option></select></label>}
        {MATERIALS.map((m,i)=><div key={m}>{mode==="consolidate"&&<label className="check-label"><input type="checkbox" checked={ignored[i]} onChange={e=>{edit();setIgnored(old=>old.map((v,j)=>i===j?e.target.checked:v));}}/>{t("Ignore")} {materialName(m)}</label>}{(mode==="distribute"||!ignored[i])&&numeric(materialName(m),resourceAmounts[i]??0,v=>setResourceAmounts(old=>old.map((x,j)=>i===j?v:x)),0,MAX_AMOUNT)}</div>)}
        {numeric(t("Repeat every (hours; 0 once)"),interval,setInterval,0,720)}{fleetSelect}
        <label className="field"><span>{t("Notifications")}</span><select value={notify} onChange={e=>{edit();setNotify(e.target.value);}}>{[["none","None"],["start","At start"],["all","Every shipment"]].map(([v,l])=><option key={v} value={v}>{t(l)}</option>)}</select></label>
      </>}
    </fieldset>
    {!valid&&!loading&&<p>{t("Complete the required settings before review.")}</p>}
    <p className="subtle-message">{t("The engine checks current game data again at launch. Capacity and travel estimates are not yet available here.")}</p>
    <button type="button" className="secondary-button" disabled={!canReview} onClick={()=>{setReview({config,summary,fingerprint});setApproved(false);}}>{t("Review settings")}</button>
    {reviewed&&review&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName}</h4><p style={{whiteSpace:"pre-line"}}>{review.summary}</p>
      <label className="check-label"><input type="checkbox" checked={approved} disabled={locked||busy} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label>
      <button type="button" className="primary-button" disabled={!canLaunch} onClick={()=>void launch()}>{t("Start automation")}</button></section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
