import {validNativeConfig,scopedShipmentPlan,type ShipmentPlan} from "./native-task-contract.ts";
type Draft=Record<string,unknown>;
type DailyObservation={cities:Record<string,string>;favour:number;limit:number;reset_seconds:number;collectable:number};
type MarketObservation={rows:{city:string;player:string;amount:number;unit_price:number}[];gold_total:number;gold_available:number|null;mode:string};
type Review={market?:MarketObservation;preview_id:string;expires_in:number;daily?:DailyObservation;shipment?:ShipmentPlan};
const obj=(v:unknown):v is Draft=>!!v&&typeof v==="object"&&!Array.isArray(v);
const int=(v:unknown,lo:number,hi:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=lo&&v<=hi;
const equal=(a:unknown,b:unknown):boolean=>Array.isArray(a)&&Array.isArray(b)?a.length===b.length&&a.every((v,i)=>equal(v,b[i])):obj(a)&&obj(b)?Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>Object.hasOwn(b,k)&&equal(a[k],b[k])):a===b;
export function validRewardDistributionRequest(v:unknown){
  return obj(v)&&Object.keys(v).length===2&&["loginDaily","distributeResources","buyResources","sellResources"].includes(String(v.task))&&validNativeConfig(v.task,v.draft);
}
export function parseRewardDistributionReview(v:unknown,account:string,task:string,draft:Draft):Review{
  if(!obj(v)||Object.keys(v).length!==6||v.account_id!==account||v.task!==task||!equal(v.draft,draft)||
    typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)||!int(v.expires_in,1,120)||!obj(v.observation))throw new Error("Invalid review");
  const base={preview_id:v.preview_id,expires_in:v.expires_in},o=v.observation;
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
