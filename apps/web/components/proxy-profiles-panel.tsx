"use client";
import {useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {parseProxyStatus,type ProxyDraft,type ProxyStatus} from "../lib/proxy-profiles";
export function ProxyProfilesPanel({account,role}:{account:string;role:string}){
  const {t}=useLanguage();
  const [status,setStatus]=useState<ProxyStatus|null>(null),[choice,setChoice]=useState(""),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const flight=useRef(false);
  const allowed=!!status&&!status.busy&&(choice==="@direct"?status.allow_direct:status.profiles.some(r=>r.id===choice));
  const selected=choice==="@direct"?null:choice;
  async function request(action?:"test"|"save"){
    if(!account||flight.current||action&&(!allowed||!status||role!=="owner"))return;
    if(action&&!window.confirm(t(action==="test"?"Test this approved profile using a fixed public HTTPS endpoint?":"Test and save this approved profile for the selected idle account?")))return;
    const draft:ProxyDraft|undefined=action&&status?{action,profile:selected,revision:status.revision,confirmed:true}:undefined;
    flight.current=true;setBusy(true);setStatus(null);setChoice("");setMessage("");
    try{
      const response=await fetch("/api/controller/accounts/"+encodeURIComponent(account)+"/proxy-settings",draft?{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify(draft)}:{cache:"no-store"});
      if(!response.ok)throw new Error("Unavailable");
      const result=parseProxyStatus(await response.json(),account,draft);
      setStatus(result);setChoice(result.current==="legacy"?"":result.current??(result.allow_direct?"@direct":""));
      if(draft)setMessage(result.result==="tested"?"HTTPS test passed; settings unchanged.":"Profile saved after HTTPS test.");
    }catch{setMessage("Network profile unavailable or outcome uncertain. Refresh before retrying.");}
    finally{flight.current=false;setBusy(false);}
  }
  return <section><h4>{t("Approved proxy profiles")}</h4><p className="subtle-message">{t("Choose a host-approved profile. The connectivity check uses a fixed HTTPS endpoint without game credentials. Provision endpoints and authentication locally.")}</p>
    <button type="button" className="secondary-button" disabled={!account||busy} onClick={()=>void request()}>{t("Read approved profiles")}</button>
    {status&&<><p>{t("Current")}: {status.profiles.find(r=>r.id===status.current)?.label??t(status.enabled?"Legacy proxy (manage locally)":"Direct connection")}</p>
      <label className="field"><span>{t("Network profile")}</span><select disabled={busy||role!=="owner"||status.busy} value={choice} onChange={e=>setChoice(e.target.value)}><option value="">{t("Choose approved profile")}</option>{status.allow_direct&&<option value="@direct">{t("Direct connection (host approved)")}</option>}{status.profiles.map(r=><option key={r.id} value={r.id}>{r.label} · {r.protocol}</option>)}</select></label>
      {status.busy&&<p>{t("Stop active tasks before changing profiles.")}</p>}{!status.profiles.length&&!status.allow_direct&&<p>{t("No profiles approved for this account. Provision profiles locally.")}</p>}
      {role==="owner"&&<div className="report-tools"><button type="button" className="secondary-button" disabled={busy||!allowed} onClick={()=>void request("test")}>{t("Test selected profile")}</button><button type="button" className="primary-button" disabled={busy||!allowed||selected===status.current} onClick={()=>void request("save")}>{t("Test and save profile")}</button></div>}
      <p className="subtle-message">{t("Game-side connectivity is not tested. No automatic reconnect or profile switching.")}</p></>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
