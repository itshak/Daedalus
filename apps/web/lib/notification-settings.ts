/** Browser-to-worker encrypted provider configuration. Never return credentials. */
export type Provider="telegram"|"discord";
type Challenge={account_id:string;provider:Provider;ticket_id:string;public_key:string;expires_in:number;scope:"worker_global";version:1};
export type NotificationSettings={mode:"clear"}|{mode:"replace";bot_token:string;chat_id:string}|{mode:"replace";webhook_url:string};
type Receipt={account_id:string;provider:Provider;scope:"worker_global";result:"configured"|"cleared"};
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const exact=(v:Record<string,unknown>,keys:string[])=>Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const b64=(v:unknown,min:number,max:number):v is string=>typeof v==="string"&&v.length>=min&&v.length<=max&&/^[A-Za-z0-9_-]+$/.test(v);
const encode=(raw:Uint8Array)=>btoa(String.fromCharCode(...raw)).replaceAll("+","-").replaceAll("/","_").replace(/=+$/,"");
const decode=(s:string)=>Uint8Array.from(atob(s.replaceAll("-","+").replaceAll("_","/")+"=".repeat((4-s.length%4)%4)),c=>c.charCodeAt(0));
export function validProvider(v:unknown):v is Provider{return v==="telegram"||v==="discord";}
export function notificationRoute(parts:string[]):boolean{return parts.length===5&&parts[0]==="accounts"&&parts[2]==="notifications"&&validProvider(parts[3])&&["begin","complete"].includes(parts[4]);}
export function notificationOwnerAllowed(role:string,parts:string[]):boolean{return !notificationRoute(parts)||role==="owner";}
export function validNotificationEnvelope(v:unknown):boolean{
  return obj(v)&&exact(v,["ticket_id","version","confirmed_global","client_key","nonce","ciphertext"])&&
    v.version===1&&v.confirmed_global===true&&b64(v.ticket_id,43,43)&&b64(v.client_key,87,87)&&b64(v.nonce,16,16)&&b64(v.ciphertext,23,2731);
}
export function parseNotificationChallenge(v:unknown,account:string,provider:Provider):Challenge{
  if(!obj(v)||!exact(v,["account_id","provider","ticket_id","public_key","expires_in","scope","version"])||
    v.account_id!==account||v.provider!==provider||v.version!==1||v.scope!=="worker_global"||
    !b64(v.ticket_id,43,43)||!b64(v.public_key,87,87)||typeof v.expires_in!=="number"||
    !Number.isInteger(v.expires_in)||v.expires_in<1||v.expires_in>120)throw new Error("Invalid provider challenge");
  return v as unknown as Challenge;
}
export function parseNotificationReceipt(v:unknown,account:string,provider:Provider):Receipt{
  if(!obj(v)||!exact(v,["account_id","provider","scope","result"])||v.account_id!==account||v.provider!==provider||
    v.scope!=="worker_global"||!["configured","cleared"].includes(String(v.result)))throw new Error("Invalid provider receipt");
  return v as unknown as Receipt;
}
export function validNotificationSettings(provider:Provider,v:unknown):v is NotificationSettings{
  if(!obj(v))return false;
  if(v.mode==="clear")return exact(v,["mode"]);
  if(v.mode!=="replace")return false;
  return provider==="telegram"?exact(v,["mode","bot_token","chat_id"])&&typeof v.bot_token==="string"&&/^[0-9]{5,20}:[A-Za-z0-9_-]{20,128}$/.test(v.bot_token)&&typeof v.chat_id==="string"&&/^-?[1-9][0-9]{0,19}$/.test(v.chat_id):
    exact(v,["mode","webhook_url"])&&typeof v.webhook_url==="string"&&/^https:\/\/(?:discord\.com|discordapp\.com)\/api\/webhooks\/[0-9]{1,25}\/[A-Za-z0-9_-]{10,200}$/.test(v.webhook_url);
}
export async function sealNotificationSettings(challenge:unknown,account:string,provider:Provider,settings:NotificationSettings){
  const c=parseNotificationChallenge(challenge,account,provider);
  if(!validNotificationSettings(provider,settings))throw new Error("Invalid provider settings");
  const publicKey=await crypto.subtle.importKey("raw",decode(c.public_key),{name:"ECDH",namedCurve:"P-256"},false,[]);
  const pair=await crypto.subtle.generateKey({name:"ECDH",namedCurve:"P-256"},true,["deriveBits"]);
  const shared=await crypto.subtle.deriveBits({name:"ECDH",public:publicKey},pair.privateKey,256);
  const secret=await crypto.subtle.importKey("raw",shared,"HKDF",false,["deriveKey"]);
  const aad=new TextEncoder().encode("daedalus-notification-v1:"+c.ticket_id+":"+account+":"+provider);
  const key=await crypto.subtle.deriveKey({name:"HKDF",hash:"SHA-256",salt:new Uint8Array(32),info:aad},secret,{name:"AES-GCM",length:256},false,["encrypt"]);
  const nonce=crypto.getRandomValues(new Uint8Array(12));
  const payload=new TextEncoder().encode(JSON.stringify(settings));
  const ciphertext=await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce,additionalData:aad},key,payload);
  return {ticket_id:c.ticket_id,version:1,confirmed_global:true,client_key:encode(new Uint8Array(await crypto.subtle.exportKey("raw",pair.publicKey))),nonce:encode(nonce),ciphertext:encode(new Uint8Array(ciphertext))};
}
