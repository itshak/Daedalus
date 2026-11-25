export type AdministrativeSettings={
  telegram:"configured"|"unsupported"|"not_configured";discord:"configured"|"unsupported"|"not_configured";
  proxy_enabled:boolean;proxy_protocol:"http"|"https"|"socks4"|"socks5"|"socks5h"|null;
  proxy_port:number|null;proxy_auth:boolean|null;challenge_provider:"default"|"custom"|"9kw.eu"|"telegram"|"unknown";
  registered_extensions:number|null;
};
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const count=(v:unknown,min:number,max:number)=>typeof v==="number"&&Number.isInteger(v)&&v>=min&&v<=max;
export function parseAdminStatus(value:unknown,account:string):AdministrativeSettings{
  if(!obj(value)||value.account_id!==account||!obj(value.settings))throw new Error("Invalid account status");
  const s=value.settings;
  const fields=["telegram","discord","proxy_enabled","proxy_protocol","proxy_port","proxy_auth","challenge_provider","registered_extensions"];
  if(Object.keys(s).length!==fields.length||fields.some(k=>!Object.hasOwn(s,k))||
    ![s.telegram,s.discord].every(v=>typeof v==="string"&&["configured","unsupported","not_configured"].includes(v))||
    typeof s.proxy_enabled!=="boolean"||
    ![null,"http","https","socks4","socks5","socks5h"].includes(s.proxy_protocol as string|null)||
    (s.proxy_port!==null&&!count(s.proxy_port,1,65535))||
    (s.proxy_auth!==null&&typeof s.proxy_auth!=="boolean")||
    !["default","custom","9kw.eu","telegram","unknown"].includes(s.challenge_provider as string)||
    (s.registered_extensions!==null&&!count(s.registered_extensions,0,1000))||
    (!s.proxy_enabled&&(s.proxy_protocol!==null||s.proxy_port!==null||s.proxy_auth!==null)))throw new Error("Invalid administrative status");
  return s as AdministrativeSettings;
}
