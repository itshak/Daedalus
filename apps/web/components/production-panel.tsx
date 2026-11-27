"use client";

import {useEffect,useState} from "react";
import {useLanguage} from "./language-provider";
import {formatNumber} from "../lib/i18n";

type Account={id:string;name:string;enabled:boolean};
type Site={available:true;maximum:number|null;extra:number|null;current:number|null}|{available:false;reason:string};
type Inventory={account_id:string;city_id:number;city_name:string;island_id:number;luxury:string;free_citizens:number|null;sites:Record<string,Site>};
type Entry={account:string;cityId:number;cityName:string;inventory?:Inventory;unavailable?:boolean};
const kinds=["resource","tradegood","academy","temple"] as const;
const resources=["wood","wine","marble","crystal","sulfur"] as const;
const capital=(s:string)=>s[0].toUpperCase()+s.slice(1);

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
export function ProductionPanel({accounts}:{accounts:Account[]}){
  const {t,locale}=useLanguage();
  const [rows,setRows]=useState<Entry[]>([]);
  const [errors,setErrors]=useState<string[]>([]);
  const [loading,setLoading]=useState(true);
  const [filter,setFilter]=useState("all");
  const [section,setSection]=useState<"resources"|"academy"|"temple">("resources");
  useEffect(()=>{
    const abort=new AbortController();
    const load=async()=>{
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
  return <div className="content-stack">
    <div className="notice"><span>{t("Read-only workforce observations. Assignment controls are not enabled yet.")}</span></div>
    <div className="under-tabs" role="group" aria-label={t("Workforce section")}>
      {(["resources","academy","temple"] as const).map(key=><button key={key} aria-pressed={section===key} className={section===key?"tab-selected":""} onClick={()=>setSection(key)}>{t(key==="resources"?"Production resources":key==="academy"?"Academy scientists":"Temple priests")}</button>)}
    </div>
    {section==="resources"&&<label className="field"><span>{t("Resource")}</span><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">{t("All resources")}</option>{resources.map(key=><option key={key} value={key}>{t(capital(key))}</option>)}</select></label>}
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
  </div>;
}
