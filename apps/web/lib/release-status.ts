const base="https://github.com/itshak/Daedalus/releases";
const dmg="Daedalus-macos-preview.dmg";
type Preview={tag:string;revision_prefix:string;published_at:string;release_url:string;dmg_url:string;checksum_url:string;notarization:"unnotarized_preview"};
export type ReleaseStatus={controller_version:string;controller_revision:string|null;catalog_status:"available"|"no_preview"|"unavailable"|"offline";preview:Preview|null};
const obj=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==="object"&&!Array.isArray(x);
export function parseReleaseStatus(value:unknown):ReleaseStatus{
  if(!obj(value)||Object.keys(value).length!==4||typeof value.controller_version!=="string"||!/^\d[0-9a-z.]{0,30}$/.test(value.controller_version)||
    (value.controller_revision!==null&&(typeof value.controller_revision!=="string"||! /^[a-f0-9]{40}$/.test(value.controller_revision)))||
    typeof value.catalog_status!=="string"||!["available","no_preview","unavailable","offline"].includes(value.catalog_status))
    throw new Error("Invalid release metadata");
  const p=value.preview;
  if(value.catalog_status!=="available"){
    if(p!==null)throw new Error("Invalid release metadata");
  }else{
    if(!obj(p)||Object.keys(p).length!==7||typeof p.tag!=="string"||!/^desktop-preview-[a-f0-9]{12}$/.test(p.tag)||
       p.revision_prefix!==p.tag.slice(-12)||typeof p.published_at!=="string"||
       !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(p.published_at)||!Number.isFinite(Date.parse(p.published_at))||
       p.notarization!=="unnotarized_preview"||p.release_url!==base+"/tag/"+p.tag||
       p.dmg_url!==base+"/download/"+p.tag+"/"+dmg||p.checksum_url!==base+"/download/"+p.tag+"/"+dmg+".sha256")
      throw new Error("Invalid release metadata");
  }
  return value as unknown as ReleaseStatus;
}
