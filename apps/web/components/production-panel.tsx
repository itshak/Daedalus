"use client";

import {useEffect,useRef,useState} from "react";
import {verifyPriorityReview,type PriorityRow,type PriorityReview,type ProductionDraft} from "../lib/production-contract";
import {launchReviewedBatch,type BatchResult} from "../lib/reviewed-batch";
import {ProductionRuns} from "./production-runs";
import {useLanguage} from "./language-provider";
import {formatNumber} from "../lib/i18n";

type Account={id:string;name:string;enabled:boolean};
type Site={available:true;maximum:number|null;extra:number|null;current:number|null}|{available:false;reason:string};
type Inventory={account_id:string;city_id:number;city_name:string;island_id:number;luxury:string;free_citizens:number|null;sites:Record<string,Site>};
type Entry={account:string;cityId:number;cityName:string;inventory?:Inventory;unavailable?:boolean};
const kinds=["resource","tradegood","academy","temple"] as const;
const resources=["wood","wine","marble","crystal","sulfur"] as const;
const capital=(s:string)=>s[0].toUpperCase()+s.slice(1);
const deadline=(seconds:number)=>Date.now()+seconds*1000;

async function read(path:string,signal:AbortSignal):Promise<unknown>{
  const response=await fetch("/api/controller/"+path,{cache:"no-store",signal});
  if(!response.ok)throw Error("Unavailable");
  return response.json();
}
function object(value:unknown):value is Record<string,unknown>{return !!value&&typeof value==="object"&&!Array.isArray(value);}
function count(value:unknown,max:number):value is number|null{return value===null||typeof value==="number"&&Number.isInteger(value)&&value>=0&&value<=max;}
function verified(value:unknown,account:string,city:number):Inventory {
  if(!object(value)||value.account_id!==account||value.city_id!==city||typeof value.city_name!=="string"
    ||typeof value.island_id!=="number"||!Number.isSafeInteger(value.island_id)||value.island_id<=0
    ||!resources.slice(1).some(r=>r===value.luxury)||!count(value.free_citizens,2000000)
    ||!object(value.sites)||Object.keys(value.sites).length!==4)throw Error("Invalid inventory");
  for(const k of kinds){
    const site=value.sites[k];
    if(!object(site)||typeof site.available!=="boolean")throw Error("Invalid site");
    if(site.available){
      if(!count(site.maximum,1000000)||!count(site.extra,1000000)||!count(site.current,2000000)
        ||((k==="academy"||k==="temple")&&site.extra!==0))throw Error("Invalid site counts");
    }else if(site.reason!=="slider_unavailable"&&site.reason!=="building_absent")throw Error("Invalid site reason");
  }
  return value as unknown as Inventory;
}

/** Key this view by the shell account identity and refresh generation. */
export function ProductionPanel({accounts,role}:{accounts:Account[];role:string}){
  const {t,locale}=useLanguage();
  const [rows,setRows]=useState<Entry[]>([]);
  const [errors,setErrors]=useState<string[]>([]);
  const [loading,setLoading]=useState(true);
  const [filter,setFilter]=useState("all");
  const [section,setSection]=useState<"resources"|"academy"|"temple">("resources");
  const [mode,setMode]=useState<ProductionDraft["mode"]>("maximum");
  const [amount,setAmount]=useState("100");
  const [overcharge,setOvercharge]=useState(false),[availableOnly,setAvailableOnly]=useState(false),[fallback,setFallback]=useState(false);
  const [excluded,setExcluded]=useState<string[]>([]);
  const [overrides,setOverrides]=useState<Record<string,string>>({});
  const [reviews,setReviews]=useState<{review:PriorityReview;deadline:number}[]>([]);
  const [message,setMessage]=useState(""),[pending,setPending]=useState(false),[results,setResults]=useState<BatchResult[]>([]);
  const mounted=useRef(true),flight=useRef(false);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const reset=()=>{setReviews([]);setResults([]);setMessage("");};

  useEffect(()=>{
    const abort=new AbortController();
    const load=async()=>{
      await Promise.resolve();
      if(abort.signal.aborted)return;
      setRows([]);setErrors([]);setLoading(true);setReviews([]);
      // Keep per-account reads sequential; one account's session must not
      // receive simultaneous selected-city slider requests.
      for(const account of accounts){
        if(abort.signal.aborted)return;
        try{
          if(!account.enabled)throw Error("Disabled");
          const data=await read("accounts/"+encodeURIComponent(account.id)+"/cities",abort.signal);
          if(!object(data)||data.account_id!==account.id||!Array.isArray(data.cities)||data.cities.length>500)throw Error("Invalid city list");
          const seen=new Set<number>();
          for(const city of data.cities){
            if(!object(city)||typeof city.id!=="number"||!Number.isSafeInteger(city.id)||city.id<=0||city.id>=1e12
              ||typeof city.name!=="string"||seen.has(city.id))throw Error("Invalid city");
            seen.add(city.id);
          }
          for(const city of data.cities as {id:number;name:string}[]){
            if(abort.signal.aborted)return;
            let entry:Entry={account:account.id,cityId:city.id,cityName:city.name};
            try{
              const raw=await read("accounts/"+encodeURIComponent(account.id)+"/cities/"+city.id+"/production",abort.signal);
              entry={...entry,inventory:verified(raw,account.id,city.id)};
            }catch{entry={...entry,unavailable:true};}
            if(!abort.signal.aborted)setRows(previous=>[...previous,entry]);
          }
        }catch{if(!abort.signal.aborted)setErrors(previous=>[...previous,account.id]);}
      }
      if(!abort.signal.aborted)setLoading(false);
    };
    void load();
    return ()=>abort.abort();
  },[accounts]);
  const names=Object.fromEntries(accounts.map(a=>[a.id,a.name]));
  const show=(n:number|null)=>n===null?t("Unknown"):formatNumber(n,locale);
  const visible=rows.filter(row=>section!=="resources"||filter==="all"||filter==="wood"||!row.inventory||row.inventory.luxury===filter);
  const eligible=visible.filter(row=>row.inventory&&filter!=="all"&&section==="resources"&&!excluded.includes(row.account+":"+row.cityId));
  const keyOf=(row:Entry)=>row.account+":"+row.cityId;
  const amountValid=mode==="maximum"||/^\d+$/.test(amount)&&Number(amount)<=(mode==="percentage"?100:2000000)&&(!overcharge||mode!=="percentage"||Number(amount)===100);
  const canEdit=role!=="viewer"&&!loading&&!pending&&!reviews.length&&section==="resources"&&filter!=="all";
  async function post(path:string,body:unknown){
    const response=await fetch("/api/controller/"+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!response.ok)throw Error("Unavailable");
    return response.json();
  }
  async function preview(){
    if(!canEdit||!amountValid||!eligible.length||flight.current)return;
    const grouped=new Map<string,PriorityRow[]>();
    for(const row of eligible){
      const override=overrides[keyOf(row)];
      const draft:ProductionDraft={resource:filter,mode:override!==undefined&&override!==""?"exact":mode,amount:override!==undefined&&override!==""?Number(override):mode==="maximum"?null:Number(amount),overcharge,available_only:availableOnly,allow_fallback:!availableOnly&&fallback};
      grouped.set(row.account,[...(grouped.get(row.account)??[]),{city_id:row.cityId,draft}]);
    }
    if(grouped.size>32||[...grouped.values()].some(r=>r.length>16)){setMessage("Review at most 16 cities per account and 32 accounts.");return;}
    flight.current=true;setPending(true);reset();
    try{
      const ready:typeof reviews=[];
      for(const [account,priority] of grouped){
        if(!mounted.current)return;
        const raw=await post("accounts/"+encodeURIComponent(account)+"/cities/"+priority[0].city_id+"/worker-plan",{task:"modifyProduction",draft:{priority}});
        const review=verifyPriorityReview(raw,account,priority);
        ready.push({review,deadline:deadline(review.expires_in)});
      }
      if(mounted.current)setReviews(ready);
    }catch{if(mounted.current)setMessage("Production preview unavailable. No assignments were started.");}
    finally{flight.current=false;if(mounted.current)setPending(false);}
  }
  async function start(){
    if(flight.current||role==="viewer"||!reviews.length)return;
    if(reviews.some(r=>r.deadline<=Date.now())){reset();setMessage("A review has expired. Prepare a new preview.");return;}
    if(!window.confirm(t("Apply these reviewed production allocations? Other production may be reduced as shown.")))return;
    flight.current=true;setPending(true);setMessage("");
    try{
      const launched=await launchReviewedBatch(reviews.map(({review:r})=>({account_id:r.account_id,task:r.task,preview_id:r.preview_id})),post,()=>crypto.randomUUID(),()=>mounted.current);
      if(mounted.current){setResults(launched);setMessage("Inspect Activity before retrying any operation.");}
    }catch{if(mounted.current)setMessage("Batch check unavailable. Inspect Activity before preparing new reviews.");}
    finally{flight.current=false;if(mounted.current){setPending(false);setReviews([]);}}
  }
  return <div className="content-stack">
    <div className="notice"><span>{t("Production uses free citizens first. Unless available-only is selected, the other resource may release workers within the reviewed city.")}</span></div>
    <div className="under-tabs" role="group" aria-label={t("Workforce section")}>
      {(["resources","academy","temple"] as const).map(key=><button key={key} aria-pressed={section===key} className={section===key?"tab-selected":""} disabled={pending} onClick={()=>{setSection(key);reset();}}>{t(key==="resources"?"Production resources":key==="academy"?"Academy scientists":"Temple priests")}</button>)}
    </div>
    {section==="resources"&&<label className="field"><span>{t("Resource")}</span><select value={filter} disabled={pending} onChange={e=>{setFilter(e.target.value);setExcluded([]);setOverrides({});reset();}}><option value="all">{t("All resources")}</option>{resources.map(key=><option key={key} value={key}>{t(capital(key))}</option>)}</select></label>}
    {section==="resources"&&role!=="viewer"&&<section className="panel">
      <div className="panel-heading"><div><h3>{t("Reviewed production allocation")}</h3><p>{t("Choose one resource priority. All resources is an inventory view.")}</p></div></div>
      <div className="form-grid">
        <label className="field"><span>{t("Target")}</span><select value={mode} disabled={!canEdit} onChange={e=>setMode(e.target.value as ProductionDraft["mode"])}><option value="maximum">{t("Maximum")}</option><option value="percentage">{t("Percentage")}</option><option value="exact">{t("Exact workers")}</option></select></label>
        {mode!=="maximum"&&<label className="field"><span>{t("Amount")}</span><input type="number" min={0} max={mode==="percentage"?100:2000000} value={amount} disabled={!canEdit} onChange={e=>setAmount(e.target.value)}/></label>}
        <label><input type="checkbox" checked={overcharge} disabled={!canEdit} onChange={e=>setOvercharge(e.target.checked)}/> {t("Include extra workers")}</label>
        <label><input type="checkbox" checked={availableOnly} disabled={!canEdit} onChange={e=>{setAvailableOnly(e.target.checked);if(e.target.checked)setFallback(false);}}/> {t("Use only available population")}</label>
        <label><input type="checkbox" checked={fallback} disabled={!canEdit||availableOnly} onChange={e=>setFallback(e.target.checked)}/> {t("Allow reviewed temporary full donor release if population is unknown")}</label>
      </div>
      {filter!=="all"&&<div className="table-scroll"><table><thead><tr><th>{t("Include")}</th><th>{t("Account")}</th><th>{t("City")}</th><th>{t("Exact override (optional)")}</th></tr></thead><tbody>
        {visible.filter(r=>r.inventory).map(row=><tr key={keyOf(row)}><td><input type="checkbox" aria-label={row.cityName} checked={!excluded.includes(keyOf(row))} disabled={!canEdit} onChange={e=>setExcluded(old=>e.target.checked?old.filter(k=>k!==keyOf(row)):[...old,keyOf(row)])}/></td><td>{names[row.account]}</td><td>{row.cityName}</td><td><input type="number" min={0} max={2000000} aria-label={t("Exact override (optional)")+" "+row.cityName} value={overrides[keyOf(row)]??""} disabled={!canEdit||excluded.includes(keyOf(row))} onChange={e=>setOverrides(old=>({...old,[keyOf(row)]:e.target.value}))}/></td></tr>)}
      </tbody></table></div>}
      <div className="report-tools"><button className="primary-button" disabled={!canEdit||!amountValid||!eligible.length||eligible.some(r=>overrides[keyOf(r)]!==undefined&&overrides[keyOf(r)]!==""&&(!/^\d+$/.test(overrides[keyOf(r)])||Number(overrides[keyOf(r)])>2000000))} onClick={()=>void preview()}>{t("Preview")} · {eligible.length}</button>{reviews.length>0&&<button className="secondary-button" disabled={pending} onClick={reset}>{t("Cancel")}</button>}</div>
      {reviews.length>0&&<><div className="table-scroll"><table><thead><tr><th>{t("Account")}</th><th>{t("City")}</th><th>{t("Target before → after")}</th><th>{t("Donor before → after")}</th><th>{t("Maximum release")}</th><th>{t("Shortfall")}</th></tr></thead><tbody>{reviews.flatMap(({review:r})=>r.plans.map(p=><tr key={r.account_id+":"+p.city_id}><td>{names[r.account_id]}</td><td>{rows.find(x=>x.account===r.account_id&&x.cityId===p.city_id)?.cityName??p.city_id}</td><td>{p.resource}: {show(p.target_before)} → {show(p.target_after)}{p.fallback?" ("+t("Fallback")+")":""}</td><td>{show(p.donor_before)} → {show(p.donor_after)}</td><td>{show(p.donor_release)}</td><td>{show(p.shortfall)}</td></tr>))}</tbody></table></div>
        <button className="primary-button" disabled={pending} onClick={()=>void start()}>{t("Confirm and start")} · {reviews.length} {t("Accounts")}</button></>}
      {pending&&<p role="status">{t("Preparing…")}</p>}{message&&<p role="status">{t(message)}</p>}
      {results.length>0&&<ul>{results.map(r=><li key={r.account_id}>{names[r.account_id]} · {t(r.status)}</li>)}</ul>}
    </section>}
    <section className="panel">
      <div className="panel-heading"><div><h3>{t("City workforce")}</h3><p aria-live="polite">{loading?t("Retrieving current observations…"):t("{count} city observations",{count:rows.length})}</p></div></div>
      {!!errors.length&&<div role="alert" className="notice">{t("Some accounts could not be retrieved:")} {errors.map(id=>names[id]).join(", ")}</div>}
      {!accounts.length?<p className="subtle-message">{t("Choose an eligible account in scope")}</p>:<div className="table-scroll"><table><thead><tr><th>{t("Account")}</th><th>{t("City")}</th><th>{t("Resource")}</th><th>{t("Current workers")}</th><th>{t("Normal capacity")}</th><th>{t("Extra capacity")}</th><th>{t("Free citizens")}</th></tr></thead><tbody>{visible.flatMap(row=>{
        const key=row.account+":"+row.cityId;
        if(!row.inventory)return [<tr key={key}><td>{names[row.account]}</td><td>{row.cityName}</td><td colSpan={5}>{t("Unavailable")}</td></tr>];
        const inventory=row.inventory;
        const selected=section==="resources"?(filter==="all"?["resource","tradegood"]:filter==="wood"?["resource"]:["tradegood"]):[section];
        return selected.map(kind=>{
          const site=inventory.sites[kind];
          return <tr key={key+":"+kind}><td>{names[row.account]}</td><td>{row.cityName}</td><td>{t(kind==="resource"?"Wood":kind==="tradegood"?capital(inventory.luxury):capital(kind))}</td>{site.available?<><td>{show(site.current)}</td><td>{show(site.maximum)}</td><td>{show(site.extra)}</td></>:<td colSpan={3}>{t(site.reason==="building_absent"?"Building absent":"Unavailable")}</td>}<td>{show(inventory.free_citizens)}</td></tr>;
        });
      })}</tbody></table></div>}
      {!loading&&!!accounts.length&&!visible.length&&<p className="subtle-message">{t("No current snapshot")}</p>}
    </section>
    <ProductionRuns accounts={accounts} role={role}/>
  </div>;
}
