export type ProxyDraft={action:"test"|"save";profile:string|null;revision:string;confirmed:true};
export type ProxyStatus={account_id:string;revision:string;enabled:boolean;current:string|null;allow_direct:boolean;busy:boolean;profiles:{id:string;label:string;protocol:string}[];result:"observed"|"tested"|"saved"};
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==="object"&&!Array.isArray(v);
const profileId=(v:unknown):v is string=>typeof v==="string"&&/^[a-z][a-z0-9_-]{0,47}$/.test(v)&&v!=="legacy";
const revision=(v:unknown)=>typeof v==="string"&&/^[a-f0-9]{64}$/.test(v);
export function proxyProfileRoute(parts:string[]){return parts.length===3&&parts[0]==="accounts"&&parts[2]==="proxy-settings";}
export function validProxyDraft(v:unknown):v is ProxyDraft{
  return obj(v)&&Object.keys(v).length===4&&(v.action==="test"||v.action==="save")&&
    (v.profile===null||profileId(v.profile))&&revision(v.revision)&&v.confirmed===true;
}
export function parseProxyStatus(v:unknown,account:string,draft?:ProxyDraft):ProxyStatus{
  if(!obj(v)||Object.keys(v).length!==8||v.account_id!==account||!revision(v.revision)||
     typeof v.enabled!=="boolean"||typeof v.allow_direct!=="boolean"||typeof v.busy!=="boolean"||
     !Array.isArray(v.profiles)||v.profiles.length>16||!v.profiles.every(r=>obj(r)&&Object.keys(r).length===3&&profileId(r.id)&&
       typeof r.label==="string"&&/^[A-Za-z0-9 _.-]{1,80}$/.test(r.label)&&
       ["http","https","socks4","socks5","socks5h"].includes(r.protocol as string))||
     new Set(v.profiles.map(r=>r.id)).size!==v.profiles.length||
     (v.enabled?!(v.current==="legacy"||v.profiles.some(r=>r.id===v.current)):v.current!==null)||
     v.result!==(draft?(draft.action==="test"?"tested":"saved"):"observed")||
     (draft&&(draft.action==="test"?v.revision!==draft.revision:v.current!==draft.profile||v.enabled!==(draft.profile!==null))))
    throw new Error("Invalid network profile result");
  return v as ProxyStatus;
}
