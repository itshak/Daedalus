// Native web task contracts: only reviewed operations may use the web launch route.
import {NATIVE_TASKS} from "./generated-operation-contract.ts";
export {NATIVE_TASKS};
export type NativeTask = typeof NATIVE_TASKS[number];
export const DOMAIN_TASKS = ["loginDaily","research","tavernManager","activateMiracle","activateShrine","donationBot","autoPirate","searchForIslandSpaces","dumpWorld"] as const;
export const CITY_TASKS = ["UpgradeUnits","buyResources","sellResources"] as const;
export type CityTask = typeof CITY_TASKS[number];
export function isCityTask(task:unknown):task is CityTask {
  return (CITY_TASKS as readonly unknown[]).includes(task);
}
export type DomainTask = typeof DOMAIN_TASKS[number];
export function isDomainTask(task: unknown): task is DomainTask {
  return (DOMAIN_TASKS as readonly unknown[]).includes(task);
}
export const MATERIALS = ["wood", "wine", "marble", "crystal", "sulfur"] as const;
export const MAX_AMOUNT = 1_000_000_000;
type Obj = Record<string, unknown>;
const obj = (v: unknown): v is Obj => !!v && typeof v === "object" && !Array.isArray(v);
const integer = (v: unknown, min: number, max: number): v is number =>
  typeof v === "number" && Number.isSafeInteger(v) && v >= min && v <= max;
const city = (v: unknown): v is number => integer(v, 1, 999_999_999_999);
const ids = (v: unknown, min: number): v is number[] =>
  Array.isArray(v) && v.length >= min && v.length <= 200 && v.every(city)
    && new Set(v).size === v.length;
const exact = (v: Obj, keys: string[]) =>
  Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v,k));
const amounts = (v: unknown, min = 0, nullable = false): v is (number | null)[] =>
  Array.isArray(v) && v.length === 5 && v.every(n => (nullable && n === null) || integer(n,min,MAX_AMOUNT));
const boundedText=(v:unknown):v is string=>typeof v==="string"&&v.length>0&&v.length<=100;
const numericId=(v:unknown):v is string=>typeof v==="string"&&/^[1-9][0-9]{0,11}$/.test(v);
const marketCity=(v:unknown):v is Obj=>obj(v)&&exact(v,["id","pos","rango","name","cityName","availableResources"])
  && numericId(v.id)&&integer(v.pos,0,80)&&integer(v.rango,1,100)&&boundedText(v.name)&&boundedText(v.cityName)
  && Array.isArray(v.availableResources)&&v.availableResources.length===5&&v.availableResources.every(n=>integer(n,0,1e15));
const buyQuote=(v:unknown):v is Obj=>obj(v)&&exact(v,["ciudadDestino","jugadorAComprar","amountAvailable","tipo","precio","destinationCityId","cityId","position","type","resource"])
  && boundedText(v.ciudadDestino)&&boundedText(v.jugadorAComprar)&&boundedText(v.tipo)
  && numericId(v.destinationCityId)&&numericId(v.cityId)&&typeof v.position==="string"&&/^\d{1,3}$/.test(v.position)
  && typeof v.type==="string"&&/^\d{1,7}$/.test(v.type)&&typeof v.resource==="string"&&["resource","1","2","3","4"].includes(v.resource)
  && integer(v.amountAvailable,1,1e12)&&integer(v.precio,1,1e9);
const sellQuote=(v:unknown):v is unknown[]=>Array.isArray(v)&&v.length===6&&boundedText(v[0])&&boundedText(v[1])
  &&integer(v[2],1,1e12)&&integer(v[3],1,1e12)&&integer(v[4],0,1e12)&&integer(v[5],1,1e12);
const positive = (v: (number | null)[]) => v.some(n => typeof n === "number" && n > 0);
export type StudyChoice = {index:number;name:string;research_type:string};
export function validStudyChoice(value:unknown):value is StudyChoice{
  return obj(value)&&exact(value,["index","name","research_type"])&&integer(value.index,0,99)
    &&typeof value.name==="string"&&value.name.length>0&&value.name.length<=160
    &&Array.from(value.name).every(c=>c.charCodeAt(0)>=32&&c!=="<"&&c!==">")
    &&typeof value.research_type==="string"&&/^[A-Za-z0-9_-]{1,40}$/.test(value.research_type);
}
export function scopedStudyChoices(value:unknown):StudyChoice[]|null{
  if(value===undefined||value===null)return null;
  if(!Array.isArray(value)||value.length>16||!value.every(validStudyChoice)
    ||new Set(value.map(r=>r.index)).size!==value.length||new Set(value.map(r=>r.research_type)).size!==value.length)
    throw new Error("Invalid research advisor inventory");
  return value;
}
export type FixedTavernRow={city_id:number;city_name:string;current_level:number;max_level:number;target_level:number;current_wine:number;target_wine:number};
export type FixedTavernReview={percentage:number;rows:FixedTavernRow[]};
export function validFixedTavern(v:unknown):v is FixedTavernReview{
  if(!obj(v)||!exact(v,["percentage","rows"])||!integer(v.percentage,0,100)||!Array.isArray(v.rows)||v.rows.length<1||v.rows.length>100)return false;
  const percentage=v.percentage;
  const ids=new Set<number>();
  return v.rows.every(r=>{
    if(!obj(r)||!exact(r,["city_id","city_name","current_level","max_level","target_level","current_wine","target_wine"])
      ||!city(r.city_id)||ids.has(r.city_id)||!boundedText(r.city_name)||Array.from(r.city_name).some(c=>c.charCodeAt(0)<32||c==="<"||c===">")
      ||!integer(r.max_level,0,150)||!integer(r.current_level,0,r.max_level)||!integer(r.target_level,0,r.max_level)
      ||r.target_level!==Math.floor(r.max_level*percentage/100)||!integer(r.current_wine,0,1e9)||!integer(r.target_wine,0,1e9))return false;
    ids.add(r.city_id);return true;
  });
}
export function fixedTavernReview(rows:unknown[],percentage:number):FixedTavernReview|null{
  if(!integer(percentage,0,100))return null;
  const result:unknown[]=[];
  for(const r of rows){
    if(!obj(r)||r.has_tavern!==true||!Array.isArray(r.serving_options)||r.serving_options.length<1||r.serving_options.length>151)return null;
    const levels=new Map<number,number>();
    for(const pair of r.serving_options){
      if(!Array.isArray(pair)||pair.length!==2||!integer(pair[0],0,150)||!integer(pair[1],0,1e9)||levels.has(pair[0]))return null;
      levels.set(pair[0],pair[1]);
    }
    if(!integer(r.serving_level,0,150)||!integer(r.wine_per_hour,0,1e9)||levels.get(r.serving_level)!==r.wine_per_hour)return null;
    const max=Math.max(...levels.keys()),target=Math.floor(max*percentage/100);
    if(!levels.has(target))return null;
    result.push({city_id:r.city_id,city_name:r.city_name,current_level:r.serving_level,max_level:max,target_level:target,current_wine:r.wine_per_hour,target_wine:levels.get(target)});
  }
  const draft={percentage,rows:result};
  return validFixedTavern(draft)?draft:null;
}
export function isNativeTask(task: unknown): task is NativeTask {
  return typeof task === "string" && (NATIVE_TASKS as readonly string[]).includes(task);
}
export function validNativeConfig(task: unknown, c: unknown): boolean {
  if (!isNativeTask(task) || !obj(c)) return false;
  switch (task) {
    case "testTelegramBot":
    case "testDiscordBot":
      return exact(c,[]);
    case "UpgradeUnits":
      return exact(c,["jobs"])&&Array.isArray(c.jobs)&&c.jobs.length===1&&obj(c.jobs[0])&&exact(c.jobs[0],["city_id","upgrades"])
        &&city(c.jobs[0].city_id)&&Array.isArray(c.jobs[0].upgrades)&&c.jobs[0].upgrades.length>0&&c.jobs[0].upgrades.length<=50
        &&c.jobs[0].upgrades.every(x=>obj(x)&&exact(x,["unitId","upgradeType","target"])
          &&typeof x.unitId==="string"&&/^\d{1,16}$/.test(x.unitId)&&typeof x.upgradeType==="string"&&/^[A-Za-z_]{1,40}$/.test(x.upgradeType)&&integer(x.target,1,25))
        &&new Set(c.jobs[0].upgrades.map(x=>x.unitId+":"+x.upgradeType)).size===c.jobs[0].upgrades.length;
    case "buyResources":
      return exact(c,["city","offers","amount_to_buy"])&&marketCity(c.city)&&integer(c.amount_to_buy,1,MAX_AMOUNT)
        &&Array.isArray(c.offers)&&c.offers.length>0&&c.offers.length<=50&&c.offers.every(buyQuote)
        &&new Set(c.offers.map(o=>o.resource)).size===1
        &&c.amount_to_buy<=c.offers.reduce((n,o)=>n+Number(o.amountAvailable),0);
    case "sellResources":
      if(!integer(c.amount_to_sell,1,MAX_AMOUNT)||!integer(c.resource_type,0,4))return false;
      if(c.mode==="create_offer")return exact(c,["mode","amount_to_sell","price","resource_type","sell_market_capacity","city"])
        &&marketCity(c.city)&&integer(c.price,1,1e9)&&integer(c.sell_market_capacity,0,1e12);
      return c.mode==="sell_to_offers"&&exact(c,["mode","amount_to_sell","offers","resource_type","city_to_buy_from"])
        &&marketCity(c.city_to_buy_from)&&Array.isArray(c.offers)&&c.offers.length>0&&c.offers.length<=50
        &&c.offers.every(sellQuote)&&c.amount_to_sell<=c.offers.reduce((n,o)=>n+Number(o[2]),0);
    case "loginDaily":
      return exact(c,["wine_city","wood_city","luxury_city","favour_tasks","collect_ambrosia"])
        && city(c.wine_city) && (c.wood_city===null||city(c.wood_city))
        && (c.luxury_city===null||city(c.luxury_city)) && typeof c.collect_ambrosia==="boolean"
        && Array.isArray(c.favour_tasks) && c.favour_tasks.length<=4
        && new Set(c.favour_tasks).size===c.favour_tasks.length
        && c.favour_tasks.every(x=>["resource","look","online","complete"].includes(x));
    case "research":
      if(exact(c,["study_choice"]))return validStudyChoice(c.study_choice);
      return exact(c,["cities_ids","qty"]) && ids(c.cities_ids,1)
        && (c.qty===null || (c.cities_ids.length===1&&integer(c.qty,1,10000)));
    case "tavernManager":
      if(exact(c,["run_hours","fixed_servings"]))return c.run_hours===0&&validFixedTavern(c.fixed_servings);
      return exact(c,["cities_ids","run_hours","notification_mode"])
        && (c.cities_ids===null||ids(c.cities_ids,1)) && integer(c.run_hours,0,24)
        && integer(c.notification_mode,1,3);
    case "activateMiracle":
      return exact(c,["wonder","iterations"]) && typeof c.wonder==="string" && /^[1-8]$/.test(c.wonder)
        && integer(c.iterations,1,100);
    case "activateShrine":
      return exact(c,["godids","mode","times"]) && Array.isArray(c.godids)
        && c.godids.length>0 && c.godids.length<=6 && new Set(c.godids).size===c.godids.length
        && c.godids.every(x=>integer(x,1,6)) && integer(c.mode,1,3)
        && (c.mode===2?c.times===0:integer(c.times,1,10));
    case "donationBot":
      return exact(c,["cities_dict","waiting_time","donate_method"])
        && integer(c.waiting_time,1,10080) && integer(c.donate_method,1,3)
        && obj(c.cities_dict) && Object.keys(c.cities_dict).length>=1 && Object.keys(c.cities_dict).length<=100
        && Object.entries(c.cities_dict).every(([id,row])=>/^[1-9][0-9]{0,11}$/.test(id)&&obj(row)
          && exact(row,["donation_type","percentage"]) && ["resource","tradegood","both"].includes(String(row.donation_type))
          && typeof row.donation_type==="string" && integer(row.percentage,0,c.donate_method===3?MAX_AMOUNT:100));
    case "autoPirate": {
      if (!exact(c,["pirateCount","pirateSchedule","pirateMissionChoice","pirateMissionDayChoice","pirateMissionNightChoice","dayStart","dayEnd","nightStart","nightEnd","autoConvert","convertPerMission","maxRandomWaitingTime","piracyCities"])
        || !integer(c.pirateCount,1,100000)||typeof c.pirateSchedule!=="boolean"
        || !integer(c.maxRandomWaitingTime,0,3600)||!Array.isArray(c.piracyCities)||c.piracyCities.length!==1
        || !obj(c.piracyCities[0])||!exact(c.piracyCities[0],["id"])||!city(c.piracyCities[0].id)
        || (c.autoConvert!=="y"&&c.autoConvert!=="n")
        || (c.autoConvert==="n"?c.convertPerMission!==0:!(c.convertPerMission==="all"||integer(c.convertPerMission,0,MAX_AMOUNT)))) return false;
      return c.pirateSchedule
        ? c.pirateMissionChoice===null&&integer(c.pirateMissionDayChoice,1,9)&&integer(c.pirateMissionNightChoice,1,9)
          && [c.dayStart,c.dayEnd,c.nightStart,c.nightEnd].every(x=>integer(x,0,23))
        : integer(c.pirateMissionChoice,1,9)&&[c.pirateMissionDayChoice,c.pirateMissionNightChoice,c.dayStart,c.dayEnd,c.nightStart,c.nightEnd].every(x=>x===null);
    }
    case "searchForIslandSpaces":
      return exact(c,["time","islandList","fights"])&&integer(c.time,3,1440)
        && Array.isArray(c.islandList)&&c.islandList.length<=100&&new Set(c.islandList).size===c.islandList.length
        && c.islandList.every(x=>typeof x==="string"&&/^(?:[1-9][0-9]?|100):(?:[1-9][0-9]?|100)$/.test(x))
        && (c.fights==="y"||c.fights==="n");
    case "dumpWorld":
      return exact(c,["waiting_time","coords","radius","shallow","non_empty_islands"])
        && typeof c.waiting_time==="number"&&Number.isFinite(c.waiting_time)&&c.waiting_time>=1&&c.waiting_time<=10
        && typeof c.shallow==="boolean"&&typeof c.non_empty_islands==="boolean"
        && (c.shallow?c.coords===null&&c.radius===null&&c.non_empty_islands===false
          : (c.coords===null?c.radius===null:Array.isArray(c.coords)&&c.coords.length===2&&c.coords.every(x=>integer(x,0,100))&&integer(c.radius,0,200)));
    case "alertAttacks":
      return exact(c,["minutes"]) && integer(c.minutes,3,1440);
    case "alertLowWine":
      return exact(c,["hours","auto_transfer","transfer_amount"]) && integer(c.hours,1,720)
        && typeof c.auto_transfer === "boolean"
        && (c.auto_transfer ? integer(c.transfer_amount,1,MAX_AMOUNT) : c.transfer_amount === 0);
    case "sendResources": {
      if (!exact(c,["routes","useFreighters"]) || typeof c.useFreighters !== "boolean"
        || !Array.isArray(c.routes) || c.routes.length < 1 || c.routes.length > 20) return false;
      const totals = new Map<number,number[]>();
      for (const r of c.routes) {
        if (!obj(r) || !(exact(r,["from","to","resources"]) || (exact(r,["from","to","resources","island","recipient"]) && city(r.island) && city(r.recipient))) || !city(r.from) || !city(r.to)
          || r.from === r.to || !amounts(r.resources) || !positive(r.resources)) return false;
        const total = totals.get(r.from) ?? [0,0,0,0,0];
        for (let i=0;i<5;i++) total[i] += Number(r.resources[i]);
        if (total.some(n=>n>MAX_AMOUNT)) return false;
        totals.set(r.from,total);
      }
      return true;
    }
    case "distributeResources":
      return exact(c,["resource","mode","cities_ids","useFreighters"])
        && (MATERIALS as readonly unknown[]).includes(c.resource)
        && (c.mode === "even" || (c.mode === "producers" && c.resource !== "wood"))
        && ids(c.cities_ids,2) && typeof c.useFreighters === "boolean";
    case "consolidateResources":
      return exact(c,["limits","sourceCityIds","destinationCityId","intervalInHours","shipType"])
        && amounts(c.limits,-1) && c.limits.some(n=>n!==-1)
        && ids(c.sourceCityIds,1) && city(c.destinationCityId) && !c.sourceCityIds.includes(c.destinationCityId)
        && integer(c.intervalInHours,1,336) && integer(c.shipType,1,3);
    case "resourceTransportManager": {
      if (typeof c.useFreighters !== "boolean" || !integer(c.interval_hours,0,720)
        || typeof c.notify !== "string" || !["none","start","all"].includes(c.notify)) return false;
      const common = ["mode","interval_hours","resource_config","useFreighters","notify"];
      if (c.mode === "consolidate")
        return (exact(c,[...common,"origin_cities","destination_city","send_mode"]) || (exact(c,[...common,"origin_cities","destination_city","send_mode","island","recipient"]) && city(c.island) && city(c.recipient)))
          && ids(c.origin_cities,1) && city(c.destination_city) && !c.origin_cities.includes(c.destination_city)
          && (c.send_mode === "keep" || c.send_mode === "send")
          && amounts(c.resource_config,0,true)
          && (c.send_mode === "keep" ? c.resource_config.some(n=>n!==null) : positive(c.resource_config));
      return c.mode === "distribute" && exact(c,[...common,"origin_city","destination_cities"])
        && city(c.origin_city) && ids(c.destination_cities,1) && !c.destination_cities.includes(c.origin_city)
        && amounts(c.resource_config) && positive(c.resource_config);
    }
  }
}
export function validNativeLaunch(value: unknown): boolean {
  return obj(value) && exact(value,["task","config","request_id","confirmed"])
    && value.confirmed === true && typeof value.request_id === "string"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.request_id)
    && validNativeConfig(value.task,value.config);
}
export type PlayerAccount = {id:string; player?:string; label?:string; name?:string; email?:string|null; world?:string};
const imported = /^Imported IkaBot (?:account|identity)(?: [0-9]+)?$/i;
export function playerName(a: PlayerAccount): string {
  return [a.player,a.label,a.name,a.email,a.id].find(v=>typeof v==="string" && v.trim() && !imported.test(v.trim()))?.trim() ?? a.id;
}
export function playerNames(accounts: PlayerAccount[]): Record<string,string> {
  const counts = new Map<string,number>();
  for (const a of accounts) {const key=playerName(a).toLowerCase();counts.set(key,(counts.get(key)??0)+1);}
  return Object.fromEntries(accounts.map(a=>[a.id,counts.get(playerName(a).toLowerCase())!>1
    ? `${playerName(a)} · ${a.world || "—"} (${a.id})` : playerName(a)]));
}
export type City = {id:number;name:string;coords?:string};
export function scopedCities(value: unknown, account: string): City[] {
  if (!obj(value) || value.account_id !== account || value.synthetic_demo === true || !Array.isArray(value.cities))
    return [];
  const result: City[]=[];
  for (const row of value.cities) {
    if (!obj(row) || !city(row.id) || typeof row.name !== "string" || !row.name.trim()
      || result.some(c=>c.id===row.id)) return [];
    result.push({id:row.id,name:row.name,coords:typeof row.coords==="string"?row.coords:undefined});
  }
  return result;
}
export function readyPreflight(value:unknown,account:string,task:NativeTask|"trainArmy"|"donate"|"reorganizeCityBuildings"|"constructBuilding"|"stationArmy"|"autoBarbarians"|"attackBarbarians"|"vacationMode"|WorkerTask):boolean {
  return obj(value) && value.account_id===account && value.task===task && value.ready===true
    && value.unresolved_request===false;
}


export type AlertTask = "alertAttacks" | "alertLowWine";
export type BatchTarget = {id:string; name:string; enabled:boolean};
export type BatchReceipt = {account:string; status:"started"|"blocked"|"uncertain"|"not attempted"};
// Only account-independent alert settings can be shared. City-bound drafts
// must instead be independently authored for each account.
export async function launchAlertBatch(
  task:AlertTask, config:Record<string,unknown>, targets:BatchTarget[],
  preflight:(id:string)=>Promise<unknown>,
  dispatch:(id:string,requestId:string)=>Promise<unknown>,
  requestId:()=>string, active:()=>boolean,
):Promise<BatchReceipt[]> {
  if(!["alertAttacks","alertLowWine"].includes(task)||!validNativeConfig(task,config)
      ||targets.length<1||targets.length>32||new Set(targets.map(a=>a.id)).size!==targets.length
      ||targets.some(a=>!a.id||!a.enabled))throw new Error("Invalid batch");
  const rows:BatchReceipt[]=targets.map(a=>({account:a.id,status:"not attempted"}));
  for(let i=0;i<targets.length;i++){
    if(!active())return rows;
    const id=targets[i].id;
    try{if(!readyPreflight(await preflight(id),id,task))rows[i].status="blocked";}
    catch{rows[i].status="blocked";}
  }
  if(rows.some(r=>r.status==="blocked")||!active())return rows;
  for(let i=0;i<targets.length;i++){
    if(!active())return rows;
    const id=targets[i].id;
    try{
      const rid=requestId(), receipt=await dispatch(id,rid);
      if(!obj(receipt)||receipt.account_id!==id||receipt.request_id!==rid||receipt.task!==task
          ||!["started","running"].includes(String(receipt.status))) {
        rows[i].status="uncertain";return rows;
      }
      rows[i].status="started";
    }catch{rows[i].status="uncertain";return rows;}
  }
  return rows;
}


export const WORKER_TASKS = ["modifyProduction","modifyAcademyWorkers","modifyTempleWorkers"] as const;
export type WorkerTask = typeof WORKER_TASKS[number];
export function isWorkerTask(task:unknown):task is WorkerTask {
  return (WORKER_TASKS as readonly unknown[]).includes(task);
}
export function validWorkerDraft(task:unknown,draft:unknown):boolean {
  if(!isWorkerTask(task)||!obj(draft)||!integer(draft.percentage,0,100))return false;
  const extra=Object.hasOwn(draft,"additional_city_ids")?["additional_city_ids"]:[];
  if(extra.length&&(!ids(draft.additional_city_ids,1)||draft.additional_city_ids.length>31))return false;
  return task==="modifyProduction"
    ? exact(draft,["percentage","project","overcharge",...extra])&&["resource","tradegood","both"].includes(String(draft.project))
      &&typeof draft.project==="string"&&typeof draft.overcharge==="boolean"&&(!draft.overcharge||draft.percentage===100)
    : exact(draft,["percentage",...extra]);
}
export function validWorkerLaunch(value:unknown):boolean {
  return obj(value)&&exact(value,["task","preview_id","request_id","confirmed"])&&isWorkerTask(value.task)
    &&typeof value.preview_id==="string"&&/^[A-Za-z0-9_-]{43}$/.test(value.preview_id)
    &&typeof value.request_id==="string"&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.request_id)
    &&value.confirmed===true;
}

export type ExternalCity = {id:number;island:number;recipient:number;name:string;owner:string};
export function scopedExternalCities(value:unknown,account:string,x:number,y:number):ExternalCity[] {
  if (!obj(value) || value.account_id!==account || value.x!==x || value.y!==y ||
      !Array.isArray(value.cities) || value.cities.length>100 ||
      !value.cities.every(r=>obj(r)&&exact(r,["id","island","recipient","name","owner"])&&city(r.id)&&city(r.island)&&city(r.recipient)&&
        typeof r.name==="string"&&r.name.length>0&&r.name.length<=120&&typeof r.owner==="string"&&r.owner.length>0&&r.owner.length<=120) ||
      new Set(value.cities.map(r=>r.id)).size!==value.cities.length || new Set(value.cities.map(r=>r.island)).size>1)
    throw new Error("Invalid island inventory");
  return value.cities as ExternalCity[];
}

export type LocatedExternalCity = ExternalCity & {x:number;y:number};
export function removeIslandCities(rows:LocatedExternalCity[],x:number,y:number):LocatedExternalCity[]{
  return rows.filter(r=>r.x!==x||r.y!==y);
}
export function mergeIslandCities(rows:LocatedExternalCity[],incoming:ExternalCity[],x:number,y:number):{cities:LocatedExternalCity[];invalidated:number[]}{
  const found=new Set(incoming.map(r=>r.id));
  const keep=removeIslandCities(rows,x,y).filter(r=>!found.has(r.id));
  if(new Set(keep.map(r=>r.x+":"+r.y)).size>=10)throw new Error("Island limit reached");
  const invalidated=rows.filter(r=>!keep.includes(r)).map(r=>r.id);
  return {cities:[...keep,...incoming.map(r=>({...r,x,y}))],invalidated};
}

export type FirstLoadTiming = {cargo:number;total_seconds:number;loading_seconds:number;travel_seconds:number;queue_seconds:number};
export type FullRouteModel = {loads:number;last_cargo:number;last_loading_seconds:number;delivery_seconds:number};
export type ShipmentObservation = {from:number;to:number;origin_name:string;destination_name:string;
  resources:number[];stock:number[];destination_space:number[]|null;first_load_limit:number;minimum_loads:number|null;first_load_timing?:FirstLoadTiming|null;full_route_model?:FullRouteModel|null};
export type ShipmentPlan = {account_id:string;routes:ShipmentObservation[];useFreighters:boolean;
  capacity:number;available_ships:number;total_ships:number;ready:boolean;preview_id:string|null;expires_in:number|null};
function shipmentObservation(value:unknown,account:string,config:unknown,requireTicket:boolean):ShipmentPlan {
  if (!validNativeConfig("sendResources",config)||!obj(config)||!obj(value)||value.account_id!==account||
      value.useFreighters!==config.useFreighters||!integer(value.capacity,0,1e8)||!integer(value.total_ships,0,1e8)||
      !integer(value.available_ships,0,value.total_ships)||value.ready!==Boolean(value.capacity&&value.total_ships)||
      !Array.isArray(value.routes)||!Array.isArray(config.routes)||value.routes.length!==config.routes.length)
    throw new Error("Invalid shipment plan");
  const full=value.capacity*value.total_ships,free=value.capacity*value.available_ships;
  const quantities=(v:unknown):v is number[]=>Array.isArray(v)&&v.length===5&&v.every(n=>integer(n,0,1e15));
  const stocks=new Map<number,{stock:number[];sum:number[]}>();
  for(let i=0;i<value.routes.length;i++){
    const row=value.routes[i],r=config.routes[i];
    if(!obj(row)||row.from!==r.from||row.to!==r.to||!quantities(row.resources)||
       row.resources.some((n,j)=>n!==r.resources[j])||!quantities(row.stock)||
       (r.recipient===undefined?!quantities(row.destination_space):row.destination_space!==null)||
       typeof row.origin_name!=="string"||!row.origin_name||row.origin_name.length>250||
       typeof row.destination_name!=="string"||!row.destination_name||row.destination_name.length>250)
      throw new Error("Invalid shipment route");
    const cargo=row.resources.reduce((a,b)=>a+b,0),space=row.destination_space;
    const limit=Array.isArray(space)?row.resources.reduce((a,b,j)=>a+Math.min(b,space[j]),0):cargo;
    if(row.first_load_limit!==Math.min(cargo,free,limit)||row.minimum_loads!==(full?Math.ceil(cargo/full):null))
      throw new Error("Invalid shipment calculation");
    const timing=row.first_load_timing;
    if(timing!==undefined&&timing!==null){
      if(!obj(timing)||Object.keys(timing).length!==5||!integer(timing.cargo,1,1e15)||timing.cargo!==row.first_load_limit||
         !integer(timing.total_seconds,0,31536000)||!integer(timing.loading_seconds,0,31536000)||
         !integer(timing.travel_seconds,1,31536000)||!integer(timing.queue_seconds,0,31536000)||
         timing.total_seconds!==timing.loading_seconds+timing.travel_seconds+timing.queue_seconds)
        throw new Error("Invalid first-load timing");
    }

    const model=row.full_route_model;
    if(model!==undefined&&model!==null){
      if(!obj(model)||Object.keys(model).length!==4||!obj(timing)||value.routes.length!==1||
         value.available_ships!==value.total_ships||!Array.isArray(space)||row.resources.some((n,j)=>n>space[j])||
         !integer(model.loads,1,1e15)||model.loads!==row.minimum_loads||!integer(model.last_cargo,1,1e15)||
         model.last_cargo!==cargo-(model.loads-1)*(row.first_load_limit as number)||
         !integer(timing.loading_seconds,0,31536000)||!integer(timing.travel_seconds,1,31536000)||
         !integer(timing.queue_seconds,0,31536000)||!integer(timing.total_seconds,0,31536000)||
         !integer(model.last_loading_seconds,0,timing.loading_seconds)||
         !integer(model.delivery_seconds,timing.total_seconds,31536000)||
         model.delivery_seconds!==timing.queue_seconds+(model.loads-1)*timing.loading_seconds+model.last_loading_seconds+(2*model.loads-1)*timing.travel_seconds)
        throw new Error("Invalid full-route model");
    }
    const id=r.from as number,previous=stocks.get(id)??{stock:row.stock,sum:[0,0,0,0,0]};
    if(previous.stock.some((n,j)=>n!==(row.stock as number[])[j]))throw new Error("Stock changed");
    const sum=previous.sum.map((n,j)=>n+(row.resources as number[])[j]);
    if(sum.some((n,j)=>n>previous.stock[j]))throw new Error("Insufficient stock");
    stocks.set(id,{stock:previous.stock,sum});
  }
  if(requireTicket&&value.ready&&(typeof value.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(value.preview_id)||!integer(value.expires_in,1,120)))
    throw new Error("Invalid shipment ticket");
  return value as unknown as ShipmentPlan;
}


export function scopedShipmentPlan(value:unknown,account:string,config:unknown):ShipmentPlan{
  return shipmentObservation(value,account,config,true);
}
export function scopedShipmentObservation(value:unknown,account:string,config:unknown):Omit<ShipmentPlan,"preview_id"|"expires_in">{
  return shipmentObservation(value,account,config,false);
}
