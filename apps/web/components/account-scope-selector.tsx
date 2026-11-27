"use client";
import {useState} from "react";
import {Globe2,ChevronDown} from "lucide-react";
import {useLanguage} from "./language-provider";
import type {AccountScope} from "../lib/account-scope";
type Account={id:string;world?:string};
export function AccountScopeSelector({accounts,ids,names,scope,onChange,loading}:{accounts:Account[];ids:string[];names:Record<string,string>;scope:AccountScope;onChange:(scope:AccountScope)=>void;loading:boolean}){
  const {t}=useLanguage();
  const [draft,setDraft]=useState<string[]>([]);
  const [query,setQuery]=useState("");
  const [open,setOpen]=useState(false);
  const summary=scope.mode==="all"?t("All accounts ({count})",{count:ids.length}):ids.length===1?names[ids[0]]:t("{count} accounts selected",{count:ids.length});
  function toggle(){if(!open){setDraft(ids);setQuery("");}setOpen(!open);}
  function apply(next:AccountScope){setOpen(false);onChange(next);}
  return <div className="global-account-scope" onKeyDown={e=>{if(e.key==="Escape"){setOpen(false);e.currentTarget.querySelector("button")?.focus();}}}>
    <button type="button" className="secondary-button scope-trigger" aria-label={t("Account scope")+": "+summary} aria-expanded={open} disabled={loading} onClick={toggle}><Globe2 size={16}/><span>{summary}</span><ChevronDown size={15}/></button>
    {open&&<div className="scope-popover" role="group" aria-label={t("Account scope")}>
      <button type="button" className="secondary-button" onClick={()=>apply({mode:"all"})}>{t("All accounts")}</button>
      {accounts.length>6&&<label className="field"><span>{t("Filter accounts")}</span><input value={query} onChange={e=>setQuery(e.target.value)}/></label>}
      <div className="scope-popover-list">{accounts.filter(a=>(names[a.id]+" "+(a.world||"")).toLowerCase().includes(query.toLowerCase())).map(a=><label key={a.id}><input type="checkbox" checked={draft.includes(a.id)} onChange={e=>setDraft(prev=>e.target.checked?[...prev,a.id]:prev.filter(id=>id!==a.id))}/><span>{names[a.id]}{names[a.id]?.includes(" · ")?"":" · "+(a.world||"—")}</span></label>)}</div>
      <div className="report-tools"><button type="button" className="text-button" onClick={()=>setDraft(accounts.map(a=>a.id))}>{t("Select all")}</button><button type="button" className="text-button" onClick={()=>setDraft([])}>{t("Clear")}</button></div>
      <button type="button" className="primary-button" onClick={()=>apply({mode:"explicit",ids:draft.filter(id=>accounts.some(a=>a.id===id))})}>{t("Apply account selection")}</button>
    </div>}
  </div>;
}
