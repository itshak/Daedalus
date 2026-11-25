export type Extension={id:string;name:string;sha256:string;verified:boolean;registered:boolean};
export type ExtensionStatus={account_id:string;scope:"worker_global";legacy_override:boolean;unreviewed_count:number;extensions:Extension[]};
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==="object"&&!Array.isArray(v);
const id=(v:unknown):v is string=>typeof v==="string"&&/^[a-z][a-z0-9_-]{0,47}$/.test(v);
const hash=(v:unknown):v is string=>typeof v==="string"&&/^[a-f0-9]{64}$/.test(v);
export function extensionRoute(parts:string[]):boolean{return parts.length===3&&parts[0]==="accounts"&&parts[2]==="extensions";}
export function validExtensionDraft(v:unknown):boolean{return obj(v)&&Object.keys(v).length===5&&id(v.id)&&hash(v.sha256)&&typeof v.registered==="boolean"&&typeof v.expected_registered==="boolean"&&v.confirmed_global===true;}
export function parseExtensionStatus(v:unknown,account:string):ExtensionStatus{
  if(!obj(v)||Object.keys(v).length!==5||v.account_id!==account||v.scope!=="worker_global"||typeof v.legacy_override!=="boolean"||
    typeof v.unreviewed_count!=="number"||!Number.isInteger(v.unreviewed_count)||v.unreviewed_count<0||v.unreviewed_count>1000||
    !Array.isArray(v.extensions)||v.extensions.length>32)throw new Error("Invalid extension status");
  const seen=new Set<string>();
  for(const row of v.extensions){
    if(!obj(row)||Object.keys(row).length!==5||!id(row.id)||seen.has(row.id)||typeof row.name!=="string"||! /^[A-Za-z0-9 _.-]{1,80}$/.test(row.name)||
      !hash(row.sha256)||typeof row.verified!=="boolean"||typeof row.registered!=="boolean")throw new Error("Invalid extension status");
    seen.add(row.id);
  }
  return v as unknown as ExtensionStatus;
}
