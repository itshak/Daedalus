import {validWorkerDraft} from "./native-task-contract.ts";
export type ProductionDraft={resource:string;mode:"maximum"|"percentage"|"exact";amount:number|null;overcharge:boolean;available_only:boolean;allow_fallback:boolean;fill_both?:true};
export type PriorityRow={city_id:number;draft:ProductionDraft};
export type PriorityPlan={city_id:number;island_id:number;resource:string;luxury:string;target_kind:string;donor_kind:string;
  target_before:number;donor_before:number;desired:number|null;target_after:number|null;donor_release:number;donor_after:number|null;
  shortfall:number|null;fallback:boolean;free_citizens:number|null;target_capacity:[number|null,number|null];donor_capacity:[number,number];draft:ProductionDraft};
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
      ||!Array.isArray(p.target_capacity)||p.target_capacity.length!==2||!p.target_capacity.every(n=>n===null||int(n,1000000))||!cap(p.donor_capacity)||!int(p.target_before,2000000)||!int(p.donor_before,2000000)
      ||(p.desired!==null&&!int(p.desired,2000000))||!int(p.donor_release,2000000)||typeof p.fallback!=="boolean"
      ||(p.free_citizens!==null&&!int(p.free_citizens,2000000)))throw Error("Invalid production plan");
    const [normal,extra]=p.target_capacity as [number|null,number|null];
    if(normal===null||extra===null){
      if(d.mode!=="maximum"||!d.allow_fallback||d.available_only||d.fill_both||!p.fallback||!p.donor_before
        ||p.donor_release!==p.donor_before||p.desired!==null||p.target_after!==null||p.donor_after!==null||p.shortfall!==null
        ||p.donor_before>p.donor_capacity[0]+p.donor_capacity[1])throw Error("Invalid unknown-capacity fallback");
      continue;
    }
    const maximum=normal+(d.overcharge?extra:0);
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
      let donor=p.donor_before-release;
      if(d.fill_both){
        if(p.free_citizens===null)throw Error("Unknown population");
        const cap=p.donor_capacity[0]+(d.overcharge?p.donor_capacity[1]:0);
        donor=Math.max(donor,Math.min(cap,donor+p.free_citizens+p.target_before+release-target));
      }
      if(p.donor_release!==release||p.target_after!==target||p.donor_after!==donor||p.shortfall!==desired-target)throw Error("Invalid allocation");
    }
  }
  return v as unknown as PriorityReview;
}

const runPattern=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
export type ProductionRun={run_id:string;status:string;cities:{
  city_id:number;resource:string;status:string;target_before:number;donor_before:number;desired:number|null;donor_release:number;
  stages:{stage:string;kind:string;value:number;status:string;observed?:{resource:number;tradegood:number}}[];
  result:{city_id:number;target:number;donor:number;shortfall:number}|null
}[]};
export type ReconcileReview={account_id:string;run_id:string;status:"review"|"reconciled";preview_id?:string;expires_in?:number;
  observations:{city_id:number;city_name:string;island_id:number;luxury:string;resource:number;tradegood:number}[]};
export function verifyProductionRuns(data:unknown,account:string):ProductionRun[]{
  if(!obj(data)||data.account_id!==account||!Array.isArray(data.runs)||data.runs.length>20)throw Error("Invalid history");
  const runs=new Set();
  for(const run of data.runs){
    if(!obj(run)||typeof run.run_id!=="string"||!runPattern.test(run.run_id)||runs.has(run.run_id)
      ||!["prepared","complete","partial","rejected","reconciled"].includes(String(run.status))
      ||!Array.isArray(run.cities)||run.cities.length<1||run.cities.length>16)throw Error("Invalid production run");
    runs.add(run.run_id);const cities=new Set();
    for(const row of run.cities){
      if(!obj(row)||!int(row.city_id,999999999999)||!row.city_id||cities.has(row.city_id)
        ||!["wood","wine","marble","crystal","sulfur"].includes(String(row.resource))
        ||!["not_started","running","complete","stale","rejected"].includes(String(row.status))
        ||!["target_before","donor_before","donor_release"].every(k=>int(row[k],2000000))||(row.desired!==null&&!int(row.desired,2000000))
        ||!Array.isArray(row.stages)||row.stages.length>3)throw Error("Invalid production receipt");
      cities.add(row.city_id);const stages=new Set();
      for(const stage of row.stages){
        if(!obj(stage)||!["release","target","restore","secondary"].includes(String(stage.stage))||stages.has(stage.stage)
          ||!["resource","tradegood"].includes(String(stage.kind))||!["pending","confirmed","rejected"].includes(String(stage.status))
          ||!int(stage.value,2000000))throw Error("Invalid stage");
        if(stage.observed!==undefined&&(!obj(stage.observed)||!int(stage.observed.resource,2000000)||!int(stage.observed.tradegood,2000000)))throw Error("Invalid readback");
        stages.add(stage.stage);
      }
      if(row.result!==null&&(!obj(row.result)||row.result.city_id!==row.city_id||!int(row.result.target,2000000)
        ||!int(row.result.donor,2000000)||!int(row.result.shortfall,2000000)))throw Error("Invalid result");
    }
  }
  return data.runs as ProductionRun[];
}
export function verifyReconciliation(data:unknown,account:string,run:string,resolved=false):ReconcileReview{
  if(!obj(data)||data.account_id!==account||data.run_id!==run||data.status!==(resolved?"reconciled":"review")
    ||!Array.isArray(data.observations)||data.observations.length<1||data.observations.length>16
    ||(!resolved&&(typeof data.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(data.preview_id)||!int(data.expires_in,120)||!data.expires_in)))throw Error("Invalid reconciliation");
  const seen=new Set();
  for(const row of data.observations){
    if(!obj(row)||!int(row.city_id,999999999999)||!row.city_id||seen.has(row.city_id)||!int(row.island_id,999999999999)||!row.island_id
      ||typeof row.city_name!=="string"||!row.city_name||row.city_name.length>100||!["wine","marble","crystal","sulfur"].includes(String(row.luxury))
      ||!int(row.resource,2000000)||!int(row.tradegood,2000000))throw Error("Invalid reconciliation observation");
    seen.add(row.city_id);
  }
  return data as unknown as ReconcileReview;
}
