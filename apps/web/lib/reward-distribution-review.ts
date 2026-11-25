import {REVIEW_ENDPOINTS} from "./generated-operation-contract.ts";
import {validNativeConfig,scopedShipmentPlan,type ShipmentPlan} from "./native-task-contract.ts";
type Draft=Record<string,unknown>;
type DailyObservation={cities:Record<string,string>;favour:number;limit:number;reset_seconds:number;collectable:number};
type MarketObservation={rows:{city:string;player:string;amount:number;unit_price:number}[];gold_total:number;gold_available:number|null;mode:string};
export const POLICY_TASKS=["research","tavernManager","activateMiracle","activateShrine","UpgradeUnits","consolidateResources","resourceTransportManager","donationBot","searchForIslandSpaces","dumpWorld","autoPirate"] as const;
export function policyTask(task:string){return (POLICY_TASKS as readonly string[]).includes(task);}
export function reviewRoute(task:string){return (REVIEW_ENDPOINTS as Readonly<Record<string,string>>)[task];}
type Review={policySummary?:string;market?:MarketObservation;preview_id:string;expires_in:number;daily?:DailyObservation;shipment?:ShipmentPlan};
const obj=(v:unknown):v is Draft=>!!v&&typeof v==="object"&&!Array.isArray(v);
const int=(v:unknown,lo:number,hi:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=lo&&v<=hi;
const equal=(a:unknown,b:unknown):boolean=>Array.isArray(a)&&Array.isArray(b)?a.length===b.length&&a.every((v,i)=>equal(v,b[i])):obj(a)&&obj(b)?Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>Object.hasOwn(b,k)&&equal(a[k],b[k])):a===b;
export function validRewardDistributionRequest(v:unknown){
  return obj(v)&&Object.keys(v).length===2&&(["loginDaily","distributeResources","buyResources","sellResources"].includes(String(v.task))||policyTask(String(v.task)))&&validNativeConfig(v.task,v.draft);
}
export function parseRewardDistributionReview(v:unknown,account:string,task:string,draft:Draft):Review{
  if(!obj(v)||Object.keys(v).length!==6||v.account_id!==account||v.task!==task||!equal(v.draft,draft)||
    typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)||!int(v.expires_in,1,120)||!obj(v.observation))throw new Error("Invalid review");
  const base={preview_id:v.preview_id,expires_in:v.expires_in},o=v.observation;
  if(policyTask(task))return {...base,policySummary:policySummary(task,draft,o)};
  if(task==="loginDaily"){
    const keys=["wine_city","wood_city","luxury_city"].filter(k=>draft[k]!==null);
    if(Object.keys(o).length!==5||!obj(o.cities)||Object.keys(o.cities).length!==keys.length||
       !keys.every(k=>typeof (o.cities as Draft)[k]==="string"&&String((o.cities as Draft)[k]).length>0&&String((o.cities as Draft)[k]).length<=120&& !/[<>\x00-\x1f]/.test(String((o.cities as Draft)[k])))||
       !int(o.limit,1,1e9)||!int(o.favour,0,o.limit)||!int(o.reset_seconds,0,1e9)||!int(o.collectable,0,100))throw new Error("Invalid daily observation");
    return {...base,daily:o as DailyObservation};
  }
  if(task==="buyResources"||task==="sellResources"){
    const mode=task==="buyResources"?"buy":String(draft.mode);
    let remaining=Number(task==="buyResources"?draft.amount_to_buy:draft.amount_to_sell);
    const offers:unknown[][]=mode==="buy"?(draft.offers as Draft[]).slice().sort((a,b)=>Number(a.precio)-Number(b.precio)).map(r=>[r.ciudadDestino,r.jugadorAComprar,r.amountAvailable,r.precio]):
      mode==="create_offer"?[[(draft.city as Draft).name,"",remaining,draft.price]]:(draft.offers as unknown[][]);
    const rows:MarketObservation["rows"]=[];
    for(const [city,player,available,price] of offers){
      const amount=Math.min(remaining,Number(available));
      if(amount){rows.push({city:String(city),player:String(player),amount,unit_price:Number(price)});remaining-=amount;}
    }
    const total=rows.reduce((n,r)=>n+r.amount*r.unit_price,0);
    if(remaining||!int(total,1,Number.MAX_SAFE_INTEGER)||Object.keys(o).length!==4||
      !equal(o.rows,rows)||o.gold_total!==total||o.mode!==mode||(mode==="buy"?!int(o.gold_available,total,Number.MAX_SAFE_INTEGER):o.gold_available!==null))
      throw new Error("Invalid market allocation");
    return {...base,market:o as MarketObservation};
  }
  if(task!=="distributeResources"||!Array.isArray(o.routes)||!Array.isArray(draft.cities_ids))throw new Error("Invalid distribution review");
  const ids=draft.cities_ids,index=["wood","wine","marble","crystal","sulfur"].indexOf(String(draft.resource));
  const routes=o.routes.map(r=>{
    if(!obj(r)||!ids.includes(r.from)||!ids.includes(r.to)||!Array.isArray(r.resources)||r.resources.some((n,i)=>i!==index&&n!==0))throw new Error("Foreign route");
    return {from:r.from,to:r.to,resources:r.resources};
  });
  const shipment=scopedShipmentPlan({...o,account_id:account,...base},account,{routes,useFreighters:draft.useFreighters});
  if(!shipment.ready)throw new Error("No usable fleet");
  const destinations=new Map<number,{space:number[];amounts:number[]}>();
  for(const row of shipment.routes){
    if(!row.destination_space)throw new Error("Missing destination storage");
    const prev=destinations.get(row.to)??{space:row.destination_space,amounts:[0,0,0,0,0]};
    if(!equal(prev.space,row.destination_space))throw new Error("Destination storage changed");
    const amounts=prev.amounts.map((v,i)=>v+row.resources[i]);
    if(amounts.some((v,i)=>v>prev.space[i]))throw new Error("Insufficient destination storage");
    destinations.set(row.to,{space:prev.space,amounts});
  }
  return {...base,shipment};
}

const keys=(v:Draft,fields:string[])=>Object.keys(v).length===fields.length&&fields.every(k=>Object.hasOwn(v,k));
const name=(v:unknown):v is string=>typeof v==="string"&&v.length>0&&v.length<=160&&!/[<>\x00-\x1f]/.test(v);
const city=(v:unknown)=>int(v,1,999999999999);
function policySummary(task:string,d:Draft,o:Draft):string{
  const bad=()=>{throw new Error("Invalid account policy observation");};
  if(["consolidateResources","resourceTransportManager","donationBot","searchForIslandSpaces","dumpWorld","autoPirate"].includes(task))
    return recurringSummary(task,d,o);
  if(task==="research"&&d.study_choice){
    if(!keys(o,["study"])||!equal(o.study,d.study_choice)||!obj(o.study))return bad();
    return "Verified study: "+o.study.name;
  }
  if(task==="research"||task==="tavernManager"){
    if(task==="tavernManager"&&d.fixed_servings){
      if(!keys(o,["fixed_servings"])||!equal(o.fixed_servings,d.fixed_servings)||!obj(o.fixed_servings)||!Array.isArray(o.fixed_servings.rows))return bad();
      return o.fixed_servings.rows.map(r=>r.city_name+": "+r.current_level+" → "+r.target_level+"; wine/hour "+r.current_wine+" → "+r.target_wine).join("\n");
    }
    const research=task==="research",key=research?"academies":"taverns",rows=o[key];
    if(!keys(o,[key])||!Array.isArray(rows)||rows.length<1||rows.length>100)return bad();
    const ids:number[]=[],lines:string[]=[];
    for(const r of rows){
      if(!obj(r)||!city(r.city_id)||!name(r.city_name)||ids.includes(Number(r.city_id)))return bad();
      ids.push(Number(r.city_id));
      if(research){
        if(!keys(r,["city_id","city_name","crystal","cooldown","can_experiment_now"])||!int(r.crystal,0,1e15)||typeof r.cooldown!=="boolean"||typeof r.can_experiment_now!=="boolean"||(r.can_experiment_now&&(r.cooldown||r.crystal<300000))||(d.qty!==null&&r.crystal<300000))return bad();
        lines.push(r.city_name+": "+r.crystal+" crystal; cooldown: "+r.cooldown+"; ready: "+r.can_experiment_now);
      }else{
        if(!keys(r,["city_id","city_name","wine","serving_level","wine_per_hour"])||!int(r.wine,0,1e15)||!int(r.serving_level,0,150)||!int(r.wine_per_hour,0,1e9))return bad();
        lines.push(r.city_name+": wine "+r.wine+"; serving "+r.serving_level+"; wine/hour "+r.wine_per_hour);
      }
    }
    if(d.cities_ids!==null&&(!Array.isArray(d.cities_ids)||!equal([...ids].sort((a,b)=>a-b),[...d.cities_ids].sort((a,b)=>a-b))))return bad();
    return lines.join("\n");
  }
  if(task==="activateMiracle"){
    const r=o.miracle;
    if(!keys(o,["miracle"])||!obj(r)||!keys(r,["city_id","temple_city","island_id","wonder","wonder_name","level","available","available_in_seconds"])||r.wonder!==d.wonder||!city(r.city_id)||!name(r.temple_city)||!name(r.wonder_name)||typeof r.island_id!=="string"||!/^\d{1,30}$/.test(r.island_id)||!int(r.level,0,5)||typeof r.available!=="boolean"||!int(r.available_in_seconds,0,604800))return bad();
    return r.wonder_name+" · "+r.temple_city+" · level "+r.level+"; available in "+r.available_in_seconds+" seconds";
  }
  if(task==="activateShrine"){
    const r=o.shrine;
    if(!keys(o,["shrine","favor_per_cycle"])||!Array.isArray(d.godids)||o.favor_per_cycle!==100*d.godids.length||!obj(r)||!keys(r,["city_id","city_name","position","favor"])||!city(r.city_id)||!name(r.city_name)||!int(r.position,0,80)||!int(r.favor,0,1e12))return bad();
    return r.city_name+": "+r.favor+" observed favour; "+o.favor_per_cycle+" per cycle";
  }
  const jobs=d.jobs,rows=o.upgrades;
  if(!Array.isArray(jobs)||jobs.length!==1||!obj(jobs[0])||!Array.isArray(jobs[0].upgrades)||!keys(o,["city_id","upgrades"])||o.city_id!==jobs[0].city_id||!Array.isArray(rows)||rows.length!==jobs[0].upgrades.length)return bad();
  const choices=jobs[0].upgrades;
  return rows.map((r,i)=>{
    const c=choices[i];
    if(!obj(r)||!obj(c)||!keys(r,["unit_id","name","upgrade_type","description","current_level","max_level","target"])||r.unit_id!==c.unitId||r.upgrade_type!==c.upgradeType||r.target!==c.target||!name(r.name)||typeof r.description!=="string"||r.description.length>100||!int(r.current_level,0,24)||!int(r.target,1,25)||!int(r.max_level,r.target,25)||r.current_level>=r.target)return bad();
    return r.name+" ("+r.upgrade_type+"): level "+r.current_level+" → "+r.target;
  }).join("\n");
}

const coordinate=(v:unknown):v is string=>typeof v==="string"&&/^(?:[1-9][0-9]?|100):(?:[1-9][0-9]?|100)$/.test(v);
function recurringSummary(task:string,d:Draft,o:Draft):string{
 const bad=()=>{throw new Error("Invalid recurring observation");};
 if(task==="dumpWorld"){
   if(!equal(o,{scope:d.coords===null?"world":"region",aggregate_only:true}))return bad();
   return "Private aggregate map report; no identifying player records.";
 }
 if(task==="searchForIslandSpaces"){
   const a=o.islands;
   if(!keys(o,["islands"])||!Array.isArray(a)||a.length<1||a.length>100||!a.every(coordinate)||new Set(a).size!==a.length||!Array.isArray(d.islandList)||(d.islandList.length>0&&!equal([...a].sort(),[...d.islandList].sort())))return bad();
   return "Verified islands: "+a.join(", ");
 }
 if(task==="autoPirate"){
   const r=o.fortress;
   if(!keys(o,["fortress","human_challenge"])||o.human_challenge!=="stop"||!obj(r)||!keys(r,["city_id","city_name","fortress_level","missions"])||!Array.isArray(d.piracyCities)||r.city_id!==d.piracyCities[0].id||!name(r.city_name)||!int(r.fortress_level,1,100)||!Array.isArray(r.missions)||r.missions.length<1||r.missions.length>9)return bad();
   const seen=new Set<number>();
   for(const m of r.missions){
     if(!obj(m)||!keys(m,["number","duration_seconds"])||!int(m.number,1,9)||seen.has(m.number)||r.fortress_level<2*m.number-1||!int(m.duration_seconds,1,86400))return bad();
     seen.add(m.number);
   }
   const requested=d.pirateSchedule?[d.pirateMissionDayChoice,d.pirateMissionNightChoice]:[d.pirateMissionChoice];
   if(!requested.every(x=>seen.has(Number(x))))return bad();
   return r.city_name+": fortress level "+r.fortress_level+"; stops at a human challenge.";
 }
 let expected:number[],extra:string[]=[];
 if(task==="donationBot"){
   if(!keys(o,["cities"])||!obj(d.cities_dict))return bad();
   expected=Object.keys(d.cities_dict).map(Number);
 }else{
   if(!keys(o,["cities","fleets","external"])||!obj(o.fleets))return bad();
   const source=task==="consolidateResources"?d.sourceCityIds:d.mode==="consolidate"?d.origin_cities:[d.origin_city];
   const dest=task==="consolidateResources"?[d.destinationCityId]:d.mode==="consolidate"?[d.destination_city]:d.destination_cities;
   if(!Array.isArray(source)||!Array.isArray(dest))return bad();
   expected=[...source,...(d.recipient!==undefined?[]:dest)].map(Number);
   const ext=o.external;
   if(d.recipient!==undefined){
     if(!obj(ext)||!keys(ext,["id","island","recipient","name","owner"])||ext.id!==dest[0]||ext.island!==d.island||ext.recipient!==d.recipient||!name(ext.name)||!name(ext.owner))return bad();
     extra.push("External destination: "+ext.name+" — "+ext.owner+"; storage unknown");
   }else if(ext!==null)return bad();
   const fleets=d.shipType===3?["trade","freighter"]:d.shipType===2||d.useFreighters===true?["freighter"]:["trade"];
   if(!keys(o.fleets,fleets))return bad();
   let usable=false;
   for(const [k,r] of Object.entries(o.fleets)){
     if(!obj(r)||!keys(r,["capacity","free","total"])||!int(r.capacity,0,1e8)||!int(r.total,0,1e8)||!int(r.free,0,r.total))return bad();
     usable=usable||Boolean(r.capacity&&r.total);
     extra.push(k+": "+r.free+"/"+r.total+" free, "+r.capacity+" cargo per ship");
   }
   if(!usable)return bad();
 }
 if(!Array.isArray(o.cities)||o.cities.length!==expected.length)return bad();
 const seen=new Set<number>(),lines:string[]=[];
 for(const row of o.cities){
   if(!obj(row)||!keys(row,["id","name","coords","stock","space"])||!city(row.id)||!expected.includes(Number(row.id))||seen.has(Number(row.id))||!name(row.name)||!coordinate(row.coords)||![row.stock,row.space].every(a=>Array.isArray(a)&&a.length===5&&a.every(n=>int(n,0,1e15))))return bad();
   seen.add(Number(row.id));lines.push(row.name+" ("+row.coords+"): stock "+(row.stock as number[]).join(" / ")+"; free space "+(row.space as number[]).join(" / "));
 }
 return [...lines,...extra].join("\n");
}
