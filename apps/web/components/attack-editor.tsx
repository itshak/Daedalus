"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {scopedCities,readyPreflight,type City} from "@/lib/native-task-contract";
type Unit={unit_id:string;name:string;available:number};
type Wave={round:number;loot:boolean;ships:number;units:Record<string,number>};
type WaveSummary={round:number;loot:boolean;ships:number;transport_ships:number;units:{name:string;amount:number}[]};
type Plan={account_id:string;city_id:number;target_city_id:number;city_name:string;target_name:string;level:number;waves:WaveSummary[];required_ships:number;available_ships:number;ready:boolean;preview_id:string|null;expires_in:number|null};
const TASK="attackBarbarians";
const integer=(n:unknown,min:number,max:number)=>typeof n==="number"&&Number.isSafeInteger(n)&&n>=min&&n<=max;
const blank=(round:number):Wave=>({round,loot:false,ships:0,units:{}});
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function AttackEditor({account,accountName,enabled,role}:{account:string;accountName:string;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]),[city,setCity]=useState(0),[target,setTarget]=useState(0);
  const [units,setUnits]=useState<Unit[]>([]),[ships,setShips]=useState(0),[waves,setWaves]=useState<Wave[]>([]);
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
  const setWave=(i:number,update:Partial<Wave>)=>{clear();setWaves(old=>old.map((w,j)=>j===i?{...w,...update}:w));};
  const setAmount=(i:number,id:string,n:number)=>{
    const amounts={...waves[i].units};
    if(n===0)delete amounts[id];else amounts[id]=n;
    setWave(i,{units:amounts});
  };
  const validCity=cities.some(c=>c.id===city);
  const valid=validCity&&cities.some(c=>c.id===target)&&waves.length>0&&waves.length<=8&&
    waves.every((w,i)=>integer(w.round,1,100)&&(i===0?w.round===1:w.round>waves[i-1].round)&&
      (!w.loot||(i>0&&i===waves.length-1&&w.ships===0))&&integer(w.ships,0,ships)&&
      Object.keys(w.units).length>0&&Object.entries(w.units).every(([id,n])=>units.some(u=>u.unit_id===id&&integer(n,1,u.available))))&&
    units.every(u=>waves.reduce((sum,w)=>sum+(w.units[u.unit_id]??0),0)<=u.available);
  const disabled=busy||locked||!enabled||role==="viewer"||!ready;
  const load=async()=>{
    if(disabled||!validCity||flight.current)return;
    clear();setUnits([]);setWaves([]);flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/attack-options") as {account_id:string;city_id:number;units:Unit[];available_ships:number};
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||!integer(p.available_ships,0,1e9)||!Array.isArray(p.units)||p.units.length>100||
         p.units.some(u=>typeof u.name!=="string"||!/^[0-9]{1,6}$/.test(u.unit_id)||!integer(u.available,1,1e9))||new Set(p.units.map(u=>u.unit_id)).size!==p.units.length)throw new Error("Invalid troops");
      setUnits(p.units);setShips(p.available_ships);setWaves(p.units.length?[blank(1)]:[]);
      if(!p.units.length)setMessage("No available troops.");
    }catch{if(mounted.current)setMessage("Troop inventory unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const prepare=async()=>{
    if(disabled||!valid||flight.current)return;
    clear();flight.current=true;setBusy(true);
    try{
      const p=await api(prefix+"/cities/"+city+"/attack-plan",{target_city_id:target,waves}) as Plan;
      if(!mounted.current)return;
      if(p.account_id!==account||p.city_id!==city||p.target_city_id!==target||!integer(p.level,1,1000)||
         typeof p.city_name!=="string"||typeof p.target_name!=="string"||!integer(p.available_ships,0,1e12)||!integer(p.required_ships,0,1e12)||
         typeof p.ready!=="boolean"||(p.ready&&p.available_ships<p.required_ships)||!Array.isArray(p.waves)||p.waves.length!==waves.length||
         p.waves.some((w,i)=>w.round!==waves[i].round||w.loot!==waves[i].loot||w.ships!==waves[i].ships||
           !integer(w.transport_ships,0,1e12)||!Array.isArray(w.units)||w.units.length!==Object.keys(waves[i].units).length||
           w.units.some(u=>typeof u.name!=="string"||!integer(u.amount,1,1e9)))||
         (p.ready&&(typeof p.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(p.preview_id)||!integer(p.expires_in,1,120))))throw new Error("Invalid attack preview");
      setPlan(p);
    }catch{if(mounted.current)setMessage("Attack preview unavailable.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  const start=async()=>{
    if(disabled||!valid||!approved||!plan?.ready||!plan.preview_id||flight.current)return;
    flight.current=true;setLocked(true);setBusy(true);setApproved(false);
    try{
      const r=await api(prefix+"/tasks/attack-start",{preview_id:plan.preview_id,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string;account_id?:string;task?:string};
      if(mounted.current)setMessage(r.status==="started"&&r.account_id===account&&r.task===TASK?"Attack task started. Monitor Activity.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    <fieldset disabled={disabled}><legend>{t("Manual barbarian attack")}</legend>
      <label className="field"><span>{t("Origin city")}</span><select value={city||""} onChange={e=>{clear();setUnits([]);setWaves([]);setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name} {c.coords}</option>)}</select></label>
      <label className="field"><span>{t("City on target island")}</span><select value={target||""} onChange={e=>{clear();setTarget(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name} {c.coords}</option>)}</select></label>
      <button className="secondary-button" type="button" disabled={disabled||!validCity} onClick={()=>void load()}>{t("Load troops")}</button>
      {waves.length>0&&<p>{t("Available transport ships")}: {ships.toLocaleString()}</p>}
      {waves.map((w,i)=><fieldset key={i}><legend>{t("Wave")} {i+1}</legend>
        <label className="field"><span>{t("Battle round")}</span><input type="number" min={1} max={100} disabled={i===0||disabled} value={Number.isNaN(w.round)?"":w.round} onChange={e=>setWave(i,{round:e.target.value===""?NaN:Number(e.target.value)})}/></label>
        <label className="field"><span>{t("Loot ships")}</span><input type="number" min={0} max={ships} disabled={w.loot||disabled} value={Number.isNaN(w.ships)?"":w.ships} onChange={e=>setWave(i,{ships:e.target.value===""?NaN:Number(e.target.value)})}/></label>
        {i>0&&<label className="check-label"><input type="checkbox" checked={w.loot} onChange={e=>setWave(i,{loot:e.target.checked,...(e.target.checked?{ships:0}:{})})}/>{t("Final looting wave")}</label>}
        {units.map(u=><label className="field" key={u.unit_id}><span>{u.name} ({t("Available")}: {u.available})</span><input type="number" min={0} max={u.available} value={w.units[u.unit_id]??0} onChange={e=>setAmount(i,u.unit_id,Number(e.target.value))}/></label>)}
      </fieldset>)}
      {waves.length>0&&<div><button type="button" className="secondary-button" disabled={disabled||waves.length>=8||waves.at(-1)?.loot} onClick={()=>{clear();setWaves(old=>[...old,blank(Math.min(100,old[old.length-1].round+1))]);}}>{t("Add wave")}</button> <button type="button" className="secondary-button" disabled={disabled||waves.length<=1} onClick={()=>{clear();setWaves(old=>old.slice(0,-1));}}>{t("Remove last wave")}</button></div>}
      <button className="secondary-button" type="button" disabled={disabled||!valid} onClick={()=>void prepare()}>{t("Preview attack")}</button>
    </fieldset>
    {plan&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName} · {plan.city_name} → {plan.target_name}</h4>
      <p>{t("Village level")}: {plan.level} · {t("Ships")}: {plan.available_ships}/{plan.required_ships}</p>
      {plan.waves.map((w,i)=><p key={i}>{t("Battle round")} {w.round}: {w.units.map(u=>u.name+" × "+u.amount).join(", ")} · {t(w.loot?"Final looting wave":"Loot ships")}{w.loot?"":": "+w.ships}</p>)}
      {plan.ready?<><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button className="primary-button" type="button" disabled={disabled||!approved} onClick={()=>void start()}>{t("Start automation")}</button><QueueReviewButton key={plan.preview_id} account={account} accountName={accountName} task="attackBarbarians" previewId={plan.preview_id} ttl={plan.expires_in} summary={plan.city_name+" → "+plan.target_name+" · "+plan.waves.map(w=>w.round+": "+w.units.map(u=>u.name+" × "+u.amount).join(", ")+", ships "+w.ships).join("; ")} disabled={disabled||!approved||!valid||!plan.ready} onQueued={()=>{setLocked(true);setApproved(false);}}/></>:<p>{t("Village destroyed or prerequisites missing.")}</p>}
    </section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
