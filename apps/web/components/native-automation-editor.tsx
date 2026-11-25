"use client";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { useLanguage } from "./language-provider";
import { MATERIALS, MAX_AMOUNT, type City, type NativeTask, type BatchTarget, type BatchReceipt, launchAlertBatch, scopedCities, readyPreflight, validNativeConfig, scopedExternalCities, type ExternalCity, scopedShipmentPlan, type ShipmentPlan } from "@/lib/native-task-contract";

type Config = Record<string,unknown>;
type Route = {key:number; from:number; to:number; resources:number[]};
type Props = {account:string; accountName:string; task:NativeTask; enabled:boolean; role:string; batchTargets?:BatchTarget[]};
const zeros = () => [0,0,0,0,0];
const route = (key:number):Route => ({key,from:0,to:0,resources:zeros()});
async function api(path:string, body?:unknown):Promise<unknown> {
  const response=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)
  })});
  if (!response.ok) throw new Error("Request unavailable");
  return response.json();
}

export function NativeAutomationEditor({account,accountName,task,enabled,role,batchTargets}:Props) {
  // Parent keys this component by account, task and refresh revision. A stale response
  // cannot populate another account's form or retain its review.
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [ready,setReady]=useState(false);
  const [loading,setLoading]=useState(Boolean(account&&enabled));
  const [loadError,setLoadError]=useState(false);
  const [routes,setRoutes]=useState<Route[]>([route(1)]);
  const nextRoute=useRef(2);
  const [islandX,setIslandX]=useState(1),[islandY,setIslandY]=useState(1);
  const [external,setExternal]=useState<ExternalCity[]>([]);
  const [lookupMessage,setLookupMessage]=useState("");
  const [lookingUp,setLookingUp]=useState(false);
  const lookupRevision=useRef(0);
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
  const [shipment,setShipment]=useState<ShipmentPlan|null>(null);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const [batchReceipts,setBatchReceipts]=useState<BatchReceipt[]>([]);
  const inFlight=useRef(false);
  const mounted=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  const notificationTest=task==="testTelegramBot"||task==="testDiscordBot";
  const cityTask=task!=="alertAttacks" && task!=="alertLowWine" && !notificationTest;
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
  const externalById=new Map(external.filter(r=>!byId.has(r.id)).map(r=>[r.id,r]));
  const actual=(id:number)=>byId.has(id);
  const destinationName=(id:number)=>{const r=externalById.get(id);return r?r.name+" — "+r.owner+" ("+islandX+":"+islandY+")":cityName(id);};
  const cityName=(id:number)=>byId.get(id)??t("Choose a city");
  const materialName=(m:string)=>t(m==="crystal"?"Glass":m[0].toUpperCase()+m.slice(1));
  const resourceSummary=(a:(number|null)[],keep=false)=>a.map((v,i)=>
    materialName(MATERIALS[i])+": "+(v===null||v===-1?t("Ignore"):String(v))+(keep&&v!==null&&v>=0?" "+t("to keep"):"")).join("; ");
  const fleetName=freighters?t("Freighters"):t("Trade ships");
  const names=multiple.map(cityName).join(", ");
  let config:Config={};let summary="";let scoped=true;
  if(notificationTest){config={};summary=t("Send one fixed test message to the configured notification provider.");}
  else if(task==="alertAttacks"){config={minutes};summary=t("Check for attacks every")+" "+minutes+" "+t("minutes");}
  else if(task==="alertLowWine"){config={hours,auto_transfer:autoTransfer,transfer_amount:autoTransfer?transferAmount:0};
    summary=t("Warn when wine has less than")+" "+hours+" "+t("hours")+"; "+(autoTransfer?t("Automatic wine transfer")+": "+transferAmount:t("Notifications only"));}
  else if(task==="sendResources"){
    config={routes:routes.map(r=>{const ext=externalById.get(r.to);return {from:r.from,to:r.to,resources:r.resources,...(ext?{island:ext.island,recipient:ext.recipient}:{})};}),useFreighters:freighters};
    scoped=routes.every(r=>actual(r.from)&&(actual(r.to)||externalById.has(r.to)));
    summary=routes.map(r=>cityName(r.from)+" → "+destinationName(r.to)+": "+resourceSummary(r.resources)).join("\n")+"\n"+fleetName
      +(routes.some(r=>externalById.has(r.to))?"\n"+t("External shipments require manual recovery."):"");
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
    const ext=mode==="consolidate"?externalById.get(single):undefined;
    config=mode==="consolidate"?{...common,origin_cities:multiple,destination_city:single,send_mode:sendMode,...(ext?{island:ext.island,recipient:ext.recipient}:{})}
      :{...common,origin_city:single,destination_cities:multiple};
    scoped=(actual(single)||Boolean(ext))&&multiple.every(actual);
    summary=(mode==="consolidate"?names+" → "+destinationName(single):cityName(single)+" → "+names)+"\n"
      +resourceSummary(values,mode==="consolidate"&&sendMode==="keep")+"\n"+t("Repeat every")+" "+interval+" "+t("hours")+" · "+fleetName+" · "+t("Notifications")+": "+t(notify==="none"?"None":notify==="start"?"At start":"Every shipment")+(ext?"\n"+t("External shipments require manual recovery."):"");
  }
  const valid=scoped&&validNativeConfig(task,config);
  const fingerprint=JSON.stringify(config);
  const reviewed=review!==null&&review.fingerprint===fingerprint;
  const batchValid=!!batchTargets&&batchTargets.length>=1&&batchTargets.length<=32&&batchTargets.every(a=>a.enabled);
  const canReview=!lookingUp&&(batchTargets?batchValid:enabled&&ready&&!loading&&!loadError)&&role!=="viewer"&&valid&&!locked&&!busy;
  const canLaunch=canReview&&reviewed&&approved&&(task!=="sendResources"||Boolean(shipment?.ready&&shipment.preview_id));
  const edit=()=>{setReview(null);setApproved(false);setShipment(null);};
  useEffect(()=>{
    if(!shipment?.expires_in)return;
    const timer=window.setTimeout(()=>{setReview(null);setApproved(false);setShipment(null);setMessage("Review expired; prepare a new preview.");},shipment.expires_in*1000);
    return ()=>window.clearTimeout(timer);
  },[shipment]);
  const prepare=async()=>{
    if(!canReview||inFlight.current)return;
    edit();setMessage("");
    if(task!=="sendResources"){setReview({config,summary,fingerprint});return;}
    inFlight.current=true;setBusy(true);
    try{
      const data=scopedShipmentPlan(await api(prefix+"/shipment-plan",config),account,config);
      if(mounted.current){setShipment(data);setReview({config,summary,fingerprint});}
    }catch{if(mounted.current)setMessage("Shipment preview unavailable. Check stock, recipients and fleet.");}
    finally{if(mounted.current)setBusy(false);inFlight.current=false;}
  };
  const resetExternal=()=>{
    lookupRevision.current++;setExternal([]);setLookingUp(false);setLookupMessage("");
    setRoutes(old=>old.map(r=>actual(r.to)?r:{...r,to:0}));
    if(task==="resourceTransportManager"&&!actual(single))setSingle(0);
    edit();
  };
  const lookup=async()=>{
    if(lookingUp||!enabled||role==="viewer"||!Number.isInteger(islandX)||islandX<1||islandX>100||!Number.isInteger(islandY)||islandY<1||islandY>100)return;
    resetExternal();const revision=lookupRevision.current;setLookingUp(true);
    try{
      const value=await api(prefix+"/island-destinations?x="+islandX+"&y="+islandY);
      if(mounted.current&&revision===lookupRevision.current){
        const rows=scopedExternalCities(value,account,islandX,islandY).filter(r=>!actual(r.id));
        setExternal(rows);setLookupMessage(rows.length?"Select a destination from the verified island.":"No eligible external cities on this island.");
      }
    }catch{if(mounted.current&&revision===lookupRevision.current)setLookupMessage("Island lookup unavailable.");}
    finally{if(mounted.current&&revision===lookupRevision.current)setLookingUp(false);}
  };
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
      if(batchTargets&&(task==="alertAttacks"||task==="alertLowWine")){
        const rows=await launchAlertBatch(task,review.config,batchTargets,
          id=>api("accounts/"+encodeURIComponent(id)+"/tasks/preflight?task="+encodeURIComponent(task)),
          (id,rid)=>api("accounts/"+encodeURIComponent(id)+"/tasks",{task,config:review.config,confirmed:true,request_id:rid}),
          ()=>crypto.randomUUID(),()=>mounted.current);
        if(mounted.current)setBatchReceipts(rows);
        return;
      }
      const current=await api(prefix+"/tasks/preflight?task="+encodeURIComponent(task));
      if(!mounted.current)return;
      if(!readyPreflight(current,account,task)){setMessage("Readiness changed; refresh and review again.");return;}
      const result=task==="sendResources"&&shipment?.preview_id?await api(prefix+"/tasks/shipment-start",{preview_id:shipment.preview_id,confirmed:true,request_id:crypto.randomUUID()}):await api(prefix+"/tasks",{task,config:review.config,confirmed:true,request_id:crypto.randomUUID()});
      const receipt=result as {status?:unknown};
      if(mounted.current)setMessage(receipt.status==="started"?"Task started. See Activity for status.":"Request recorded. Check Activity before another attempt.");
    } catch {if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally {if(mounted.current)setBusy(false);inFlight.current=false;}
  };
  return <section className="native-automation-editor">
    {batchTargets?<p>{batchValid?t("Each selected account is checked before any launch."):t("Select 1–32 enabled accounts.")}</p>:loading?<p role="status">{t("Retrieving authenticated controller data…")}</p>:loadError||!ready?<p role="alert">{t("Task prerequisites are not ready. Check the account and notifications.")}</p>:<p>{t("Ready to review")}</p>}
    {cityTask&&task!=="sendResources"&&!(task==="resourceTransportManager"&&mode==="consolidate")&&!loading&&cities.length<2&&<p role="alert">{t("At least two authenticated cities are required.")}</p>}
    <fieldset disabled={busy||locked||(batchTargets?!batchValid:loading||!enabled)||role==="viewer"}>
      <legend>{t("Settings")}</legend>
      {notificationTest&&<p>{t("Send one fixed test message to the configured notification provider.")} {t("Credentials are shared by the login and are never displayed. Check Activity for acceptance.")}</p>}
      {task==="alertAttacks"&&numeric(t("Check for attacks every (minutes)"),minutes,setMinutes,3,1440)}
      {task==="alertLowWine"&&<>{numeric(t("Warn when wine has less than (hours)"),hours,setHours,1,720)}<label className="check-label"><input type="checkbox" checked={autoTransfer} onChange={e=>{edit();setAutoTransfer(e.target.checked);}}/>{t("Automatic wine transfer")}</label>{autoTransfer&&numeric(t("Wine to transfer"),transferAmount,setTransferAmount,1,MAX_AMOUNT)}</>}
      {(task==="sendResources"||(task==="resourceTransportManager"&&mode==="consolidate"))&&<fieldset><legend>{t("Find external cities")}</legend>
          <label className="field"><span>{t("Island X")}</span><input type="number" min={1} max={100} step={1} value={Number.isNaN(islandX)?"":islandX} onChange={e=>{resetExternal();setIslandX(e.target.value===""?NaN:Number(e.target.value));}}/></label>
          <label className="field"><span>{t("Island Y")}</span><input type="number" min={1} max={100} step={1} value={Number.isNaN(islandY)?"":islandY} onChange={e=>{resetExternal();setIslandY(e.target.value===""?NaN:Number(e.target.value));}}/></label>
          <button type="button" className="secondary-button" disabled={lookingUp||!cities.length||!Number.isInteger(islandX)||islandX<1||islandX>100||!Number.isInteger(islandY)||islandY<1||islandY>100} onClick={()=>void lookup()}>{t(lookingUp?"Looking up cities…":"Find external cities")}</button>
          {lookupMessage&&<p role="status">{t(lookupMessage)}</p>}
        </fieldset>}
      {task==="sendResources"&&<>
        {routes.map((r,i)=><fieldset key={r.key}><legend>{t("Route")} {i+1}</legend>
          {citySelect(t("From city"),r.from,v=>changeRoute(r.key,{from:v,to:r.to===v?0:r.to}),r.to)}
          <label className="field"><span>{t("To city")}</span><select value={r.to||""} onChange={e=>{edit();changeRoute(r.key,{to:Number(e.target.value)});}}>
            <option value="">{t("Choose a city")}</option>
            {cities.filter(c=>c.id!==r.from).map(c=><option key={c.id} value={c.id}>{cityName(c.id)}</option>)}
            {[...externalById.values()].map(c=><option key={c.id} value={c.id}>{destinationName(c.id)}</option>)}
          </select></label>
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
        {mode==="consolidate"?<label className="field"><span>{t("To city")}</span><select value={single||""} onChange={e=>{edit();const v=Number(e.target.value);setSingle(v);setMultiple(old=>old.filter(id=>id!==v));}}>
          <option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{cityName(c.id)}</option>)}{[...externalById.values()].map(c=><option key={c.id} value={c.id}>{destinationName(c.id)}</option>)}</select></label>:citySelect(t("From city"),single,v=>{setSingle(v);setMultiple(old=>old.filter(id=>id!==v));})}
        {cityChecks(t(mode==="consolidate"?"Source cities":"Destination cities"),single)}
        {mode==="consolidate"&&<label className="field"><span>{t("Resource policy")}</span><select value={sendMode} onChange={e=>{edit();setSendMode(e.target.value);}}><option value="keep">{t("Keep reserve")}</option><option value="send">{t("Send fixed amounts")}</option></select></label>}
        {MATERIALS.map((m,i)=><div key={m}>{mode==="consolidate"&&<label className="check-label"><input type="checkbox" checked={ignored[i]} onChange={e=>{edit();setIgnored(old=>old.map((v,j)=>i===j?e.target.checked:v));}}/>{t("Ignore")} {materialName(m)}</label>}{(mode==="distribute"||!ignored[i])&&numeric(materialName(m),resourceAmounts[i]??0,v=>setResourceAmounts(old=>old.map((x,j)=>i===j?v:x)),0,MAX_AMOUNT)}</div>)}
        {numeric(t("Repeat every (hours; 0 once)"),interval,setInterval,0,720)}{fleetSelect}
        <label className="field"><span>{t("Notifications")}</span><select value={notify} onChange={e=>{edit();setNotify(e.target.value);}}>{[["none","None"],["start","At start"],["all","Every shipment"]].map(([v,l])=><option key={v} value={v}>{t(l)}</option>)}</select></label>
      </>}
    </fieldset>
    {!valid&&!loading&&<p>{t("Complete the required settings before review.")}</p>}
    {!notificationTest&&<p className="subtle-message">{t(task==="sendResources"?"The engine checks current game data again at launch. Travel time is not yet verified.":"The engine checks current game data again at launch. Capacity and travel estimates are not yet available here.")}</p>}
    <button type="button" className="secondary-button" disabled={!canReview} onClick={()=>void prepare()}>{t(task==="sendResources"?"Preview shipment capacity":"Review settings")}</button>
    {reviewed&&review&&<section className="preview-panel"><h4>{t("Review automation")} · {batchTargets?t("Selected account scope"):accountName}</h4>{batchTargets&&<ul>{batchTargets.map(a=><li key={a.id}>{a.name}</li>)}</ul>}<p style={{whiteSpace:"pre-line"}}>{review.summary}</p>
      {shipment&&<><p>{t("Available ships")}: {shipment.available_ships.toLocaleString()}/{shipment.total_ships.toLocaleString()} · {t("Cargo per vessel")}: {shipment.capacity.toLocaleString()}</p>
        <table><thead><tr><th>{t("Route")}</th><th>{t("Origin stock")}</th><th>{t("First load limit")}</th><th>{t("Minimum loads")}</th></tr></thead><tbody>{shipment.routes.map((r,i)=><tr key={i}><td>{r.origin_name} → {r.destination_name}{r.destination_space===null&&<p>{t("Recipient storage unknown")}</p>}</td><td>{r.stock.map((n,j)=>r.resources[j]?materialName(MATERIALS[j])+": "+n.toLocaleString():null).filter(Boolean).join("; ")}</td><td>{r.first_load_limit.toLocaleString()}</td><td>{r.minimum_loads??t("Unavailable")}</td></tr>)}</tbody></table>
        <p>{t("Individual route limits share the same fleet. Waiting and ETA are not predicted.")}</p>{!shipment.ready&&<p role="alert">{t("No usable fleet")}</p>}</>}
      <label className="check-label"><input type="checkbox" checked={approved} disabled={locked||busy||(task==="sendResources"&&!shipment?.ready)} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label>
      <button type="button" className="primary-button" disabled={!canLaunch} onClick={()=>void launch()}>{t("Start automation")}</button></section>}
    {batchReceipts.length>0&&<section className="preview-panel"><h4>{t("Batch receipts")}</h4><ul>{batchReceipts.map(r=><li key={r.account}>{batchTargets?.find(a=>a.id===r.account)?.name??r.account} · {t(r.status)}</li>)}</ul><p>{t("Check Activity before starting any further task.")}</p></section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
