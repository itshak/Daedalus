"use client";
import {useState,useRef} from "react";
import {useLanguage} from "./language-provider";
import {parseReleaseStatus,type ReleaseStatus} from "../lib/release-status";
export function ReleasePanel({webVersion,webRevision}:{webVersion:string;webRevision:string|null}){
  const {t}=useLanguage();
  const [status,setStatus]=useState<ReleaseStatus|null>(null),[busy,setBusy]=useState(false),[failed,setFailed]=useState(false);
  const flight=useRef(false);
  async function check(){
    if(flight.current)return;
    flight.current=true;setBusy(true);setFailed(false);setStatus(null);
    try{
      const response=await fetch("/api/controller/release-status",{cache:"no-store"});
      if(!response.ok)throw new Error("Unavailable");
      setStatus(parseReleaseStatus(await response.json()));
    }catch{setFailed(true);}
    finally{flight.current=false;setBusy(false);}
  }
  return <section className="panel settings-panel"><div className="panel-heading"><div><h3>{t("Releases and diagnostics")}</h3><p>{t("Check published Mac previews without changing the backend.")}</p></div></div>
    <div className="settings-row"><strong>{t("Web version")}</strong><span>{webVersion}</span></div>
    <div className="settings-row"><strong>{t("Web build revision")}</strong><code>{webRevision??t("Unknown")}</code></div>
    <button type="button" className="secondary-button" disabled={busy} onClick={()=>void check()}>{t(busy?"Loading…":"Check published Mac preview")}</button>
    {failed&&<p role="alert">{t("Release metadata unavailable")}</p>}
    {status&&<><div className="settings-row"><strong>{t("Controller version")}</strong><span>{status.controller_version}</span></div>
      <div className="settings-row"><strong>{t("Controller build revision")}</strong><code>{status.controller_revision??t("Unknown")}</code></div>
      {status.preview?<><div className="settings-row"><strong>{t("Published preview")}</strong><span>{status.preview.tag}</span></div><p>{status.preview.published_at}</p>
        <p><a href={status.preview.release_url} target="_blank" rel="noopener noreferrer">{t("Release notes")}</a> · <a href={status.preview.dmg_url} target="_blank" rel="noopener noreferrer">{t("Download Mac DMG")}</a> · <a href={status.preview.checksum_url} target="_blank" rel="noopener noreferrer">{t("SHA-256 checksum")}</a></p>
      </>:<p>{t("Public preview unavailable or no verified catalog entry")}</p>}</>}
    <p className="subtle-message">{t("Published previews are not notarized. Verify the checksum before installation. Controller updates and rollback use the reviewed host release workflow, not a remote shell.")}</p>
  </section>;
}
