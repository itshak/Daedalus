"use client";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {MAX_AMOUNT,MATERIALS,type City,type CityTask,scopedCities,readyPreflight,validNativeConfig} from "@/lib/native-task-contract";
type Row=Record<string,unknown>;
const record=(v:unknown):v is Row=>!!v&&typeof v==="object"&&!Array.isArray(v);
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");return r.json();
}
export function NativeCityEditor({account,accountName,task,enabled,role}:{account:string;accountName:string;task:CityTask;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [city,setCity]=useState(0);
  const [resource,setResource]=useState(0);
  const [side,setSide]=useState(task==="buyResources"?"buy":"sell_to_offers");
  const [snapshot,setSnapshot]=useState<Row|null>(null);
  const [quantities,setQuantities]=useState<Record<string,number>>({});
  const [selected,setSelected]=useState<number[]>([]);
  const [amount,setAmount]=useState(1);
  const [price,setPrice]=useState(1);
  const [ready,setReady]=useState(false);
  const [error,setError]=useState(false);
  const [loading,setLoading]=useState(Boolean(account&&enabled));
  const [review,setReview]=useState<{config:Row;summary:string}|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const inFlight=useRef(false);
  const mounted=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  useEffect(()=>{
    let live=true;mounted.current=true;
    if(!account||!enabled)return ()=>{mounted.current=false;};
    Promise.all([api(prefix+"/cities"),api(prefix+"/tasks/preflight?task="+encodeURIComponent(task))]).then(([c,p])=>{
      if(live){setCities(scopedCities(c,account));setReady(readyPreflight(p,account,task));}
    }).catch(()=>{if(live)setError(true);}).finally(()=>{if(live)setLoading(false);});
    return ()=>{live=false;mounted.current=false;};
  },[account,enabled,prefix,task]);
  useEffect(()=>{
    let live=true;
    if(city&&enabled){
      const path=task==="UpgradeUnits"?"workshop-upgrades":"market-quotes?side="+side+"&resource_type="+resource;
      api(prefix+"/cities/"+city+"/"+path).then(v=>{
        if(!live)return;
        if(!record(v)||v.account_id!==account||v.city_id!==city||v.synthetic_demo===true||
          ((task==="buyResources"||task==="sellResources")&&(v.side!==side||v.resource_type!==resource))){setError(true);return;}
        setSnapshot(v);
        if(side==="create_offer"&&typeof v.price_min==="number")setPrice(v.price_min);
      }).catch(()=>{if(live)setError(true);});
    }
    return ()=>{live=false;};
  },[account,city,enabled,prefix,task,resource,side]);
  const invalidate=()=>{setReview(null);setApproved(false);};
  const changeScope=()=>{invalidate();setSnapshot(null);setSelected([]);setQuantities({});setError(false);};
  const upgrades=Array.isArray(snapshot?.upgrades)?snapshot.upgrades.filter(record):[];
  const offers=Array.isArray(snapshot?.offers)?snapshot.offers:[];
  const material=(i:number)=>t(i===3?"Glass":MATERIALS[i][0].toUpperCase()+MATERIALS[i].slice(1));
  const cityRow=record(snapshot?.city)?snapshot.city:null;
  const name=cities.find(c=>c.id===city)?.name??"";
  const upgradeKey=(r:Row)=>String(r.unit_id)+":"+String(r.upgrade_type);
  let config:Row={},summary="",scoped=!!snapshot&&cities.some(c=>c.id===city);
  if(task==="UpgradeUnits"){
    const chosen=upgrades.filter(r=>Object.hasOwn(quantities,upgradeKey(r)));
    scoped=scoped&&chosen.every(r=>quantities[upgradeKey(r)]>Number(r.current_level)&&quantities[upgradeKey(r)]<=Number(r.max_level));
    config={jobs:[{city_id:city,upgrades:chosen.map(r=>({unitId:r.unit_id,upgradeType:r.upgrade_type,target:quantities[upgradeKey(r)]}))}]};
    summary=name+"\n"+chosen.map(r=>String(r.name)+" · "+String(r.description)+": "+r.current_level+" → "+quantities[upgradeKey(r)]).join("\n");
  }else{
    const chosen=selected.map(i=>offers[i]).filter(x=>x!==undefined);
    const stock=cityRow&&Array.isArray(cityRow.availableResources)?Number(cityRow.availableResources[resource]):0;
    if(side==="buy"){
      config={city:cityRow,offers:chosen,amount_to_buy:amount};
      scoped=scoped&&selected.length===chosen.length&&amount<=chosen.reduce((n,o)=>n+Number(record(o)?o.amountAvailable:0),0);
    }else if(side==="create_offer"){
      config={mode:side,city:cityRow,amount_to_sell:amount,price,resource_type:resource,sell_market_capacity:snapshot?.sell_market_capacity};
      scoped=scoped&&amount<=stock&&price>=Number(snapshot?.price_min)&&price<=Number(snapshot?.price_max)&&amount<=Number(snapshot?.sell_market_capacity)-Number(snapshot?.currently_on_sale);
    }else{
      config={mode:side,city_to_buy_from:cityRow,offers:chosen,amount_to_sell:amount,resource_type:resource};
      scoped=scoped&&selected.length===chosen.length&&amount<=stock&&amount<=chosen.reduce((n,o)=>n+Number(Array.isArray(o)?o[2]:0),0);
    }
    summary=name+" · "+material(resource)+" · "+t(side==="buy"?"Buy":side==="create_offer"?"Create a market offer":"Sell")+" "+amount+"\n"+(side==="create_offer"?t("Gold per unit")+": "+price:chosen.map(o=>Array.isArray(o)?o.slice(0,4).join(" · "):record(o)?[o.ciudadDestino,o.jugadorAComprar,o.amountAvailable,o.precio].join(" · "):"").join("\n"));
  }
  const valid=scoped&&validNativeConfig(task,config);
  const disabled=busy||locked||loading||!enabled||role==="viewer";
  const canReview=!disabled&&ready&&!error&&valid;
  const numeric=(label:string,value:number,onChange:(v:number)=>void,min:number,max:number)=><label className="field"><span>{label}</span><input type="number" min={min} max={max} step={1} value={Number.isNaN(value)?"":value} onChange={e=>{invalidate();onChange(e.target.value===""?NaN:Number(e.target.value));}}/></label>;
  const launch=async()=>{
    if(!canReview||!approved||!review||inFlight.current)return;inFlight.current=true;setBusy(true);setLocked(true);setApproved(false);
    try{
      const p=await api(prefix+"/tasks/preflight?task="+encodeURIComponent(task));
      if(!mounted.current)return;
      if(!readyPreflight(p,account,task)){setMessage("Readiness changed; refresh and review again.");return;}
      const receipt=await api(prefix+"/tasks",{task,config:review.config,confirmed:true,request_id:crypto.randomUUID()}) as {status?:string};
      if(mounted.current)setMessage(receipt.status==="started"?"Task started. See Activity for status.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{inFlight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    {error&&<p role="alert">{t("Current inventory unavailable")}</p>}
    <fieldset disabled={disabled}><legend>{t("Settings")}</legend>
      <label className="field"><span>{t("City")}</span><select value={city||""} onChange={e=>{changeScope();setCity(Number(e.target.value));}}><option value="">{t("Choose a city")}</option>{cities.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      {task==="UpgradeUnits"&&upgrades.map(r=>{const key=upgradeKey(r),current=Number(r.current_level),max=Number(r.max_level);return <fieldset key={key}><legend>{String(r.name)} · {String(r.description)}</legend><label className="check-label"><input type="checkbox" checked={Object.hasOwn(quantities,key)} disabled={current>=max} onChange={e=>{invalidate();setQuantities(old=>{const next={...old};if(e.target.checked)next[key]=current+1;else delete next[key];return next;});}}/>{t("Level")} {current}</label>{Object.hasOwn(quantities,key)&&numeric(t("Target level"),quantities[key],v=>setQuantities(old=>({...old,[key]:v})),current+1,max)}</fieldset>;})}
      {(task==="buyResources"||task==="sellResources")&&<><label className="field"><span>{t("Resource")}</span><select value={resource} onChange={e=>{changeScope();setResource(Number(e.target.value));}}>{MATERIALS.map((m,i)=><option key={m} value={i}>{material(i)}</option>)}</select></label>{task==="sellResources"&&<label className="field"><span>{t("Market action")}</span><select value={side} onChange={e=>{changeScope();setSide(e.target.value);}}><option value="sell_to_offers">{t("Sell to available offers")}</option><option value="create_offer">{t("Create a market offer")}</option></select></label>}
      {side==="create_offer"?snapshot&&<p>{t("Market capacity")}: {String(snapshot.sell_market_capacity)} · {t("Currently on sale")}: {String(snapshot.currently_on_sale)}</p>:offers.map((o,i)=><label key={i} className="check-label"><input type="checkbox" checked={selected.includes(i)} onChange={e=>{invalidate();setSelected(old=>e.target.checked?[...old,i]:old.filter(x=>x!==i));}}/>{Array.isArray(o)?o.slice(0,4).join(" · "):record(o)?[o.ciudadDestino,o.jugadorAComprar,o.amountAvailable,o.precio].join(" · "):"—"}</label>)}
      {numeric(t("Quantity"),amount,setAmount,1,MAX_AMOUNT)}{side==="create_offer"&&snapshot&&numeric(t("Gold per unit"),price,setPrice,Number(snapshot.price_min),Number(snapshot.price_max))}</>}
    </fieldset>
    {!valid&&!loading&&<p>{t("Complete the required settings before review.")}</p>}
    <button type="button" className="secondary-button" disabled={!canReview} onClick={()=>{setReview({config,summary});setApproved(false);}}>{t("Review settings")}</button>
    {review&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName}</h4><p style={{whiteSpace:"pre-line"}}>{review.summary}</p><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button type="button" className="primary-button" disabled={!canReview||!approved} onClick={()=>void launch()}>{t("Start automation")}</button></section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
