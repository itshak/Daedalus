"use client";
import {useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {parseExtensionStatus,type Extension,type ExtensionStatus} from "../lib/extension-settings";
export function ExtensionPanel({account,role}:{account:string;role:string}){
  const {t}=useLanguage();
  const [status,setStatus]=useState<ExtensionStatus|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const flight=useRef(false);
  async function request(row?:Extension){
    if(!account||flight.current||row&&role!=="owner")return;
    if(row&&!window.confirm(t("Change the worker-global extension registration without executing code?")+"\n"+row.name+"\nSHA-256: "+row.sha256))return;
    flight.current=true;setBusy(true);setStatus(null);setMessage("");
    const path="/api/controller/accounts/"+encodeURIComponent(account)+"/extensions";
    try{
      const response=await fetch(path,row?{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:row.id,sha256:row.sha256,registered:!row.registered,expected_registered:row.registered,confirmed_global:true})}:{cache:"no-store"});
      if(!response.ok)throw new Error("Unavailable");
      const value=parseExtensionStatus(await response.json(),account);
      if(row&&!value.extensions.some(x=>x.id===row.id&&x.sha256===row.sha256&&x.registered!==row.registered))throw new Error("Unconfirmed");
      setStatus(value);
    }catch{setMessage("Extension settings unavailable or changed. Refresh before retrying.");}
    finally{flight.current=false;setBusy(false);}
  }
  return <section><h4>{t("Host-approved extensions")}</h4><p className="subtle-message">{t("Only locally installed and hash-approved extensions can be registered. Registration does not execute or delete code.")}</p>
    <button type="button" className="secondary-button" disabled={!account||busy} onClick={()=>void request()}>{t("Read approved extensions")}</button>
    {status&&<><p>{t("Legacy registrations")}: {status.unreviewed_count}</p>{status.legacy_override&&<p role="alert">{t("Local per-user override blocks changes.")}</p>}
      {status.extensions.length===0?<p>{t("No locally approved extensions")}</p>:<div className="table-scroll"><table><thead><tr><th>{t("Extension")}</th><th>{t("Verification")}</th><th>{t("Registration")}</th><th>{t("Action")}</th></tr></thead><tbody>{status.extensions.map(row=><tr key={row.id}><td>{row.name}</td><td>{t(row.verified?"Verified":"Hash mismatch")}</td><td>{t(row.registered?"Registered":"Not registered")}</td><td><button type="button" className="secondary-button" disabled={busy||role!=="owner"||status.legacy_override||(!row.verified&&!row.registered)} onClick={()=>void request(row)}>{t(row.registered?"Unregister":"Register")}</button></td></tr>)}</tbody></table></div>}
    </>}{message&&<p role="alert">{t(message)}</p>}
  </section>;
}
