/** Validated, account-scoped projection of the engine's deployment review. */
export type StationDraft={destination_city_id:number;ground:boolean;all_origins?:true;both?:true};
export type StationRoute={city_id:number;city_name:string;ground:boolean;total:number;weight:number|null;capacity:number|null};
export type StationPlan=StationRoute&StationDraft&{account_id:string;destination_name:string;ready:boolean;preview_id:string|null;expires_in:number|null;deployments?:StationRoute[]};
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const integer=(v:unknown,min:number,max:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=min&&v<=max;
const name=(v:unknown)=>typeof v==="string"&&v.length>0&&v.length<=100;
function route(v:unknown):v is StationRoute & Record<string,unknown> {
  if(!obj(v)||!integer(v.city_id,1,999_999_999_999)||!name(v.city_name)||typeof v.ground!=="boolean"||!integer(v.total,0,1e12))return false;
  return v.ground?integer(v.weight,0,1e15)&&integer(v.capacity,0,Number.MAX_SAFE_INTEGER):v.weight===null&&v.capacity===null;
}
export function scopedStationPlan(v:unknown,account:string,origin:number,draft:StationDraft,owned:number[]):StationPlan{
  if(!obj(v)||v.account_id!==account||!route(v)||v.city_id!==origin||v.destination_city_id!==draft.destination_city_id
    ||!owned.includes(origin)||!owned.includes(draft.destination_city_id)||origin===draft.destination_city_id
    ||v.ground!==draft.ground||!name(v.destination_name)
    ||v.all_origins!==draft.all_origins||v.both!==draft.both
    ||v.ready!==(v.total>0&&(!v.ground||v.weight!<=v.capacity!)))
    throw new Error("Invalid deployment preview");
  if(draft.all_origins||draft.both){
    if(!Array.isArray(v.deployments)||!v.deployments.length||v.deployments.length>64||!v.deployments.every(route))throw new Error("Invalid deployment routes");
    const rows=v.deployments as StationRoute[];
    const expected=(draft.all_origins?owned.filter(id=>id!==draft.destination_city_id):[origin]).flatMap(id=>(draft.both?[true,false]:[draft.ground]).map(g=>id+":"+g)).sort();
    const keys=rows.map(r=>r.city_id+":"+r.ground).sort();
    const names=new Map<number,string>();
    for(const r of rows){
      if(names.has(r.city_id)&&names.get(r.city_id)!==r.city_name)throw new Error("City identity changed");
      names.set(r.city_id,r.city_name);
    }
    const ground=rows.filter(r=>r.ground);
    if(expected.length!==keys.length||expected.some((key,i)=>key!==keys[i])||names.get(origin)!==v.city_name||
       rows.reduce((n,r)=>n+r.total,0)!==v.total||
       (ground.length>0&&(ground.reduce((n,r)=>n+r.weight!,0)!==v.weight||Math.min(...ground.map(r=>r.capacity!))!==v.capacity)))
      throw new Error("Invalid deployment coverage");
  }else if(v.deployments!==undefined)throw new Error("Unexpected deployment routes");
  if(v.ready&&(typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)||!integer(v.expires_in,1,120)))throw new Error("Invalid deployment review");
  return v as unknown as StationPlan;
}
