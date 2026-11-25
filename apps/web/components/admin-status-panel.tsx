"use client";
import {useState,useRef} from "react";
import {useLanguage} from "./language-provider";
import {parseAdminStatus,type AdministrativeSettings} from "../lib/admin-status";
export function AdminStatusPanel({accounts}:{accounts:{id:string;name:string}[]}){
  const {t}=useLanguage();
  const [selected,setSelected]=useState("");
  const [result,setResult]=useState<{account:string;settings:AdministrativeSettings}|null>(null);
  const [error,setError]=useState(""),[busy,setBusy]=useState(false);
  const revision=useRef(0);
  const account=accounts.some(a=>a.id===selected)?selected:"";
  async function refresh(){
    if(!account||busy)return;
    const id=++revision.current;
    setBusy(true);setResult(null);setError("");
    try{
      const response=await fetch("/api/controller/accounts/"+encodeURIComponent(account)+"/administrative-status",{cache:"no-store"});
      if(!response.ok)throw new Error("Unavailable");
      const settings=parseAdminStatus(await response.json(),account);
      if(id===revision.current)setResult({account,settings});
    }catch{if(id===revision.current)setError("Protected settings unavailable for this account.");}
    finally{if(id===revision.current)setBusy(false);}
  }
  const s=result?.account===account?result.settings:null;
  return <section className="panel settings-panel"><div className="panel-heading"><div><h3>{t("Protected administration")}</h3><p>{t("Read observed settings without displaying credentials.")}</p></div></div>
    <label className="field"><span>{t("Account")}</span><select value={account} onChange={e=>{revision.current++;setSelected(e.target.value);setResult(null);setError("");setBusy(false);}}><option value="">{t("Choose an account")}</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
    <button type="button" className="secondary-button" disabled={!account||busy} onClick={()=>void refresh()}>{t(busy?"Loading…":"Read protected settings status")}</button>
    {error&&<p role="alert">{t(error)}</p>}
    {s&&<><p className="subtle-message">{t("Observed saved configuration; connectivity has not been tested.")}</p>
      {[[t("Telegram"),t(s.telegram.replaceAll("_"," "))],[t("Discord"),t(s.discord.replaceAll("_"," "))],[t("Proxy"),s.proxy_enabled?t("Enabled"):t("Disabled")],[t("Proxy protocol"),s.proxy_protocol??t("Unknown")],[t("Proxy port"),s.proxy_port??t("Unknown")],[t("Proxy authentication"),s.proxy_auth===null?t("Unknown"):t(s.proxy_auth?"configured":"not configured")],[t("Challenge provider"),s.challenge_provider],[t("Registered custom extensions"),s.registered_extensions??t("Unknown")]].map(([label,value])=><div className="settings-row" key={String(label)}><strong>{label}</strong><span className="settings-value">{value}</span></div>)}</>}
    <p className="subtle-message">{t("Notification credentials, proxy settings, challenge handling and custom extensions must be managed on the authenticated worker host. The browser does not expose raw game services, developer cookies or unverified update commands.")}</p>
  </section>;
}
