import {validWorkerDraft} from "./native-task-contract";
export type ProductionDraft={resource:string;mode:"maximum"|"percentage"|"exact";amount:number|null;overcharge:boolean;available_only:boolean;allow_fallback:boolean};
export type PriorityRow={city_id:number;draft:ProductionDraft};
export type PriorityPlan={city_id:number;island_id:number;resource:string;luxury:string;target_kind:string;donor_kind:string;
  target_before:number;donor_before:number;desired:number;target_after:number|null;donor_release:number;donor_after:number|null;
  shortfall:number|null;fallback:boolean;free_citizens:number|null;target_capacity:[number,number];donor_capacity:[number,number];draft:ProductionDraft};
export type PriorityReview={account_id:string;city_id:number;task:"modifyProduction";ready:true;plans:PriorityPlan[];preview_id:string;expires_in:number};
function obj(v:unknown):v is Record<string,unknown>{return !!v&&typeof v==="object"&&!Array.isArray(v);}
function int(v:unknown,max:number):v is number{return typeof v==="number"&&Number.isInteger(v)&&v>=0&&v<=max;}
function cap(v:unknown):v is [number,number]{return Array.isArray(v)&&v.length===2&&v.every(n=>int(n,1000000));}
export function verifyPriorityReview(v:unknown,account:string,rows:PriorityRow[]):PriorityReview {
  if(!validWorkerDraft("modifyProduction",{priority:rows})||!obj(v)||v.account_id!==account||v.task!=="modifyProduction"
    ||v.city_id!==rows[0].city_id||v.ready!==true||typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)
    ||!int(v.expires_in,120)||v.expires_in===0||!Array.isArray(v.plans)||v.plans.length!==rows.length)throw Error("Invalid production review");
  for(const [i,p] of v.plans.entries()){
    const row=rows[i],d=row.draft;
    if(!obj(p)||p.city_id!==row.city_id||!int(p.island_id,999999999999)||p.island_id===0||p.resource!==d.resource
      ||!["wine","marble","crystal","sulfur"].includes(String(p.luxury))
      ||(d.resource!=="wood"&&p.luxury!==d.resource)||p.target_kind!==(d.resource==="wood"?"resource":"tradegood")
      ||p.donor_kind!==(d.resource==="wood"?"tradegood":"resource")||!obj(p.draft)
      ||!validWorkerDraft("modifyProduction",{priority:[{city_id:p.city_id,draft:p.draft}]})
      ||Object.entries(d).some(([k,x])=>(p.draft as Record<string,unknown>)[k]!==x)
      ||!cap(p.target_capacity)||!cap(p.donor_capacity)||!int(p.target_before,2000000)||!int(p.donor_before,2000000)
      ||!int(p.desired,2000000)||!int(p.donor_release,2000000)||typeof p.fallback!=="boolean"
      ||(p.free_citizens!==null&&!int(p.free_citizens,2000000)))throw Error("Invalid production plan");
    const [normal,extra]=p.target_capacity,maximum=normal+(d.overcharge?extra:0);
    const desired=d.mode==="maximum"?maximum:d.mode==="percentage"?Math.floor(normal*d.amount!/100)+(d.overcharge?extra:0):d.amount!;
    const needed=Math.max(0,desired-p.target_before);
    if(p.desired!==desired||desired>maximum||p.target_before>normal+extra||p.donor_before>p.donor_capacity[0]+p.donor_capacity[1])throw Error("Invalid production capacity");
    if(p.fallback){
      if(!d.allow_fallback||d.available_only||p.free_citizens!==null||!needed||!p.donor_before||p.donor_release!==p.donor_before
        ||p.target_after!==null||p.donor_after!==null||p.shortfall!==null)throw Error("Invalid fallback");
    }else{
      if(needed&&p.free_citizens===null)throw Error("Unknown population");
      const release=d.available_only?0:Math.min(p.donor_before,Math.max(0,needed-(p.free_citizens??0)));
      const target=Math.min(desired,p.target_before+(p.free_citizens??0)+release);
      if(p.donor_release!==release||p.target_after!==target||p.donor_after!==p.donor_before-release||p.shortfall!==desired-target)throw Error("Invalid allocation");
    }
  }
  return v as unknown as PriorityReview;
}
