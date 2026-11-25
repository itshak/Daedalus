"use client";
import {ProxyProfilesPanel} from "./proxy-profiles-panel";
import {ChallengePolicyPanel} from "./challenge-policy-panel";
import {ExtensionPanel} from "./extension-panel";
import {useState,useRef} from "react";
import {useLanguage} from "./language-provider";
import {validNotificationSettings,sealNotificationSettings,parseNotificationReceipt,type Provider,type NotificationSettings} from "../lib/notification-settings";
import {parseAdminStatus,type AdministrativeSettings} from "../lib/admin-status";
export function AdminStatusPanel({accounts,role="viewer"}:{accounts:{id:string;name:string}[];role?:string}){
  const {t}=useLanguage();
  const [selected,setSelected]=useState("");
  const [result,setResult]=useState<{account:string;settings:AdministrativeSettings}|null>(null);
  const [error,setError]=useState(""),[busy,setBusy]=useState(false);
  const revision=useRef(0),flight=useRef(false);
  const [provider,setProvider]=useState<Provider>("telegram"),[secret,setSecret]=useState(""),[chat,setChat]=useState("");
  const [consent,setConsent]=useState(false),[notice,setNotice]=useState("");
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
  function resetSecrets(){setSecret("");setChat("");setConsent(false);}
  async function configure(clear:boolean){
    if(!account||role!=="owner"||!consent||busy||flight.current)return;
    const settings:NotificationSettings=clear?{mode:"clear"}:provider==="telegram"?{mode:"replace",bot_token:secret.trim(),chat_id:chat.trim()}:{mode:"replace",webhook_url:secret.trim()};
    if(!validNotificationSettings(provider,settings)){setNotice("Invalid provider settings");return;}
    if(clear&&!window.confirm("Clear the worker-global notification default for all accounts using it?"))return;
    const id=++revision.current;flight.current=true;setBusy(true);resetSecrets();setNotice("");setResult(null);
    const path="/api/controller/accounts/"+encodeURIComponent(account)+"/notifications/"+provider;
    const post=async(action:string,body:unknown)=>{const response=await fetch(path+"/"+action,{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!response.ok)throw new Error("Provider configuration unavailable");return response.json();};
    try{
      const challenge=await post("begin",{confirmed_global:true});
      const envelope=await sealNotificationSettings(challenge,account,provider,settings);
      const receipt=parseNotificationReceipt(await post("complete",envelope),account,provider);
      if(id===revision.current)setNotice(receipt.result==="configured"?"Worker-global notification default saved after successful provider test.":"Worker-global notification default cleared.");
    }catch{if(id===revision.current)setNotice("Configuration unavailable or outcome uncertain. Refresh status before retrying.");}
    finally{flight.current=false;if(id===revision.current)setBusy(false);}
  }
  const s=result?.account===account?result.settings:null;
  return <section className="panel settings-panel"><div className="panel-heading"><div><h3>{t("Protected administration")}</h3><p>{t("Read observed settings without displaying credentials.")}</p></div></div>
    <label className="field"><span>{t("Account")}</span><select value={account} disabled={busy} onChange={e=>{revision.current++;setSelected(e.target.value);setResult(null);setError("");setBusy(false);resetSecrets();setNotice("");}}><option value="">{t("Choose an account")}</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
    <button type="button" className="secondary-button" disabled={!account||busy} onClick={()=>void refresh()}>{t(busy?"Loading…":"Read protected settings status")}</button>
    {error&&<p role="alert">{t(error)}</p>}
    {s&&<><p className="subtle-message">{t("Observed saved configuration; connectivity has not been tested.")}</p>
      {[[t("Telegram"),t(s.telegram.replaceAll("_"," "))],[t("Discord"),t(s.discord.replaceAll("_"," "))],[t("Proxy"),s.proxy_enabled?t("Enabled"):t("Disabled")],[t("Proxy protocol"),s.proxy_protocol??t("Unknown")],[t("Proxy port"),s.proxy_port??t("Unknown")],[t("Proxy authentication"),s.proxy_auth===null?t("Unknown"):t(s.proxy_auth?"configured":"not configured")],[t("Challenge provider"),s.challenge_provider],[t("Registered custom extensions"),s.registered_extensions??t("Unknown")]].map(([label,value])=><div className="settings-row" key={String(label)}><strong>{label}</strong><span className="settings-value">{value}</span></div>)}</>}
    {role==="owner"&&<fieldset disabled={busy||!account}><legend>{t("Notification configuration")}</legend>
      <p className="subtle-message">{t("Worker-global defaults affect all accounts using this worker host. Legacy per-user overrides require local reconciliation. Replacement sends one fixed test message before saving.")}</p>
      <label className="field"><span>{t("Provider")}</span><select value={provider} onChange={e=>{setProvider(e.target.value as Provider);resetSecrets();setNotice("");}}><option value="telegram">Telegram</option><option value="discord">Discord</option></select></label>
      <label className="field"><span>{t(provider==="telegram"?"New Telegram bot token":"New Discord webhook URL")}</span><input type="password" autoComplete="new-password" maxLength={300} value={secret} onChange={e=>{setSecret(e.target.value);setConsent(false);}}/></label>
      {provider==="telegram"&&<label className="field"><span>{t("Telegram chat ID")}</span><input type="password" autoComplete="off" maxLength={21} value={chat} onChange={e=>{setChat(e.target.value);setConsent(false);}}/></label>}
      <label className="check-label"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>{t("I approve changing the worker-global notification default")}</label>
      <div className="report-tools"><button type="button" className="primary-button" disabled={!consent||!validNotificationSettings(provider,provider==="telegram"?{mode:"replace",bot_token:secret.trim(),chat_id:chat.trim()}:{mode:"replace",webhook_url:secret.trim()})} onClick={()=>void configure(false)}>{t("Test and save")}</button><button type="button" className="secondary-button" disabled={!consent} onClick={()=>void configure(true)}>{t("Clear configured default")}</button></div>
    </fieldset>}
    {notice&&<p role="status">{t(notice)}</p>}
    <ProxyProfilesPanel key={"proxy:"+account+":"+role} account={account} role={role}/>
    <ChallengePolicyPanel key={"challenge:"+account+":"+role} account={account} role={role}/>
    <ExtensionPanel key={account+":"+role} account={account} role={role}/>
    <p className="subtle-message">{t("Unapproved proxy endpoints and legacy automated challenge providers are not exposed. The browser does not expose raw game services, developer cookies or unverified update commands.")}</p>
  </section>;
}
