"use client";
import {useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {parseChallengePolicy,type ChallengeMode,type ChallengePolicy} from "../lib/challenge-policy";
export function ChallengePolicyPanel({account,role}:{account:string;role:string}){
  const {t}=useLanguage();
  const [policy,setPolicy]=useState<ChallengePolicy|null>(null),[mode,setMode]=useState<ChallengeMode>("stop");
  const [busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const flight=useRef(false);
  async function request(save=false){
    if(!account||flight.current||save&&(!policy||role!=="owner"||mode===policy.mode||mode==="notify_and_stop"&&!policy.notification_ready))return;
    if(save&&!window.confirm(t("Save the selected account's human-attention stop policy?")))return;
    flight.current=true;setBusy(true);setMessage("");
    const draft=save&&policy?{mode,expected_mode:policy.mode,confirmed:true}:null;
    setPolicy(null);
    try{
      const response=await fetch("/api/controller/accounts/"+encodeURIComponent(account)+"/challenge-policy",draft?{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify(draft)}:{cache:"no-store"});
      if(!response.ok)throw new Error("Unavailable");
      const p=parseChallengePolicy(await response.json(),account);
      if(draft&&p.mode!==draft.mode)throw new Error("Unconfirmed");
      setPolicy(p);setMode(p.mode);
    }catch{setMessage("Challenge policy unavailable or changed. Refresh before retrying.");}
    finally{flight.current=false;setBusy(false);}
  }
  return <section><h4>{t("Human challenge handling")}</h4><p className="subtle-message">{t("Managed piracy stops at a game challenge. Complete the challenge manually before a new reviewed launch.")}</p>
    <button type="button" className="secondary-button" disabled={busy||!account} onClick={()=>void request()}>{t("Read challenge policy")}</button>
    {policy&&<><label className="field"><span>{t("Challenge policy")}</span><select disabled={busy||role!=="owner"} value={mode} onChange={e=>setMode(e.target.value as ChallengeMode)}><option value="stop">{t("Stop for human attention")}</option><option value="notify_and_stop" disabled={!policy.notification_ready}>{t("Notify and stop")}</option></select></label>
      <p>{t(policy.notification_ready?"Notification destination configured.":"Configure a supported notification destination before choosing notify and stop.")}</p>
      {role==="owner"&&<button type="button" className="secondary-button" disabled={busy||mode===policy.mode||mode==="notify_and_stop"&&!policy.notification_ready} onClick={()=>void request(true)}>{t("Save human challenge policy")}</button>}</>}
    {message&&<p role="alert">{t(message)}</p>}
  </section>;
}
