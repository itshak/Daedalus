import {scopedShipmentObservation,type ShipmentPlan} from "./native-task-contract.ts";
export type SupplyOptions={source_ids:number[];useFreighters:boolean;round_up:boolean;supply_only:boolean};
export type Target={position:number;target_level:number};
export type ConstructionPlan={account_id:string;city_id:number;city_name:string;ready:boolean;costs:number[];available:number[];missing:number[];estimated_seconds:number;buildings:{name:string;position:number;current_level:number;target_level:number}[];preview_id:string|null;expires_in:number|null;supply?:{options:SupplyOptions;target:number[];remaining:number[];destination_space:number[];shipment:Omit<ShipmentPlan,"account_id"|"preview_id"|"expires_in">|null}};
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const int=(v:unknown,min:number,max:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=min&&v<=max;
const exact=(v:Record<string,unknown>,keys:string[])=>Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const qty=(v:unknown):v is number[]=>Array.isArray(v)&&v.length===5&&v.every(n=>int(n,0,1e15));
const same=(a:unknown,b:number[])=>qty(a)&&a.every((n,i)=>n===b[i]);
export function validSupply(v:unknown,city:number):v is SupplyOptions{
  return obj(v)&&exact(v,["source_ids","useFreighters","round_up","supply_only"])&&
    typeof v.useFreighters==="boolean"&&typeof v.round_up==="boolean"&&typeof v.supply_only==="boolean"&&
    Array.isArray(v.source_ids)&&v.source_ids.length>=1&&v.source_ids.length<=20&&
    v.source_ids.every(id=>int(id,1,999_999_999_999)&&id!==city)&&new Set(v.source_ids).size===v.source_ids.length;
}
export function scopedConstructionPlan(v:unknown,account:string,city:number,targets:Target[],options:SupplyOptions|undefined,owned:number[]):ConstructionPlan{
  if(!obj(v)||v.account_id!==account||v.city_id!==city||!owned.includes(city)||typeof v.city_name!=="string"||!v.city_name||v.city_name.length>100||
    !qty(v.costs)||!qty(v.available)||!same(v.missing,v.costs.map((n,i)=>Math.max(0,n-(v.available as number[])[i])))||
    !int(v.estimated_seconds,0,1e15)||!Array.isArray(v.buildings)||v.buildings.length!==targets.length||
    !v.buildings.every((b,i)=>obj(b)&&b.position===targets[i].position&&b.target_level===targets[i].target_level&&
      int(b.current_level,0,149)&&int(b.target_level,b.current_level+1,Math.min(150,b.current_level+10))&&typeof b.name==="string"&&b.name.length>0&&b.name.length<=100))
    throw new Error("Invalid construction review");
  const missing=v.missing as number[];
  let ready=!missing.some(n=>n>0);
  if(options){
    const s=v.supply;
    if(!validSupply(options,city)||!options.source_ids.every(id=>owned.includes(id))||!obj(s)||!exact(s,["options","target","remaining","shipment","destination_space"])||
       !validSupply(s.options,city)||s.options.useFreighters!==options.useFreighters||s.options.supply_only!==options.supply_only||s.options.round_up!==options.round_up||
       s.options.source_ids.length!==options.source_ids.length||s.options.source_ids.some((n,i)=>n!==options.source_ids[i])||!qty(s.destination_space))
      throw new Error("Invalid construction supply scope");
    const round=(n:number)=>{const unit=n<1000?100:n<10000?500:1000;return Math.ceil(n/unit)*unit;};
    const target=missing.map((n,i)=>Math.min((s.destination_space as number[])[i],options.round_up?round(n):n));
    if(!same(s.target,target))throw new Error("Invalid construction supply target");
    let left=target.slice(),fleetReady=false;
    if(s.shipment!==null){
      const f=s.shipment;
      if(!obj(f)||!Array.isArray(f.routes)||!f.routes.length||f.routes.length>20)throw new Error("Invalid fleet");
      const routes=f.routes.map(r=>{if(!obj(r))throw new Error("Invalid route");return {from:r.from,to:r.to,resources:r.resources};});
      const ids=routes.map(r=>r.from);
      if(ids.some((id,i)=>id!==options.source_ids.filter(x=>ids.includes(x))[i])||new Set(ids).size!==ids.length||routes.some(r=>r.to!==city))throw new Error("Invalid suppliers");
      // The nested shipment observation has no launch authority of its own.
      const verified=scopedShipmentObservation({...f,account_id:account},account,{routes,useFreighters:options.useFreighters});
      for(const r of verified.routes){
        if(!same(r.destination_space,s.destination_space)||!same(r.resources,left.map((n,i)=>Math.min(n,r.stock[i],1e9))))throw new Error("Invalid supplier allocation");
        left=left.map((n,i)=>n-r.resources[i]);
      }
      fleetReady=verified.ready;
    }
    const remaining=missing.map((n,i)=>Math.max(0,n-(target[i]-left[i])));
    if(!same(s.remaining,remaining))throw new Error("Invalid uncovered shortage");
    ready=fleetReady&&!remaining.some(n=>n>0);
  }else if(v.supply!==undefined)throw new Error("Unexpected supply plan");
  if(v.ready!==ready||(ready&&(typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)||!int(v.expires_in,1,120)))||
    (!ready&&(v.preview_id!==null||v.expires_in!==null)))throw new Error("Invalid construction ticket");
  return v as unknown as ConstructionPlan;
}
