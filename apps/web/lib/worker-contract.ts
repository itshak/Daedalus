import {validWorkerDraft,type WorkerTask} from "./native-task-contract.ts";
export type WorkerDraft={percentage:number;project?:string;overcharge?:boolean;additional_city_ids?:number[]};
export type WorkerAssignment={city_id:number;city_name:string;project:string|null;current:number|null;maximum:number;extra:number;target:number};
export type WorkerPlan=WorkerAssignment&{task:WorkerTask;account_id:string;percentage:number;overcharge:boolean;ready:true;preview_id:string;expires_in:number;additional_city_ids?:number[];assignments?:WorkerAssignment[]};
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const integer=(v:unknown,min:number,max:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=min&&v<=max;
function row(v:unknown,id:number,project:string|null,task:WorkerTask,draft:WorkerDraft):v is WorkerAssignment&Record<string,unknown>{
  return obj(v)&&v.city_id===id&&v.project===project&&typeof v.city_name==="string"&&v.city_name.length>0&&v.city_name.length<=100&&
    integer(v.maximum,0,1e6)&&integer(v.extra,0,1e6)&&integer(v.target,0,2e6)&&
    (v.current===null||integer(v.current,0,2e6))&&v.target===Math.floor(v.maximum*draft.percentage/100)+(draft.overcharge?v.extra:0)&&
    (task==="modifyProduction"||v.extra===0);
}
export function scopedWorkerPlan(v:unknown,account:string,city:number,task:WorkerTask,draft:WorkerDraft,owned:number[]):WorkerPlan{
  const cities=[city,...(draft.additional_city_ids??[])],projects=draft.project==="both"?["resource","tradegood"]:[draft.project??null];
  if(!validWorkerDraft(task,draft)||new Set(cities).size!==cities.length||cities.some(id=>!owned.includes(id))||
    !obj(v)||v.account_id!==account||v.task!==task||v.city_id!==city||v.percentage!==draft.percentage||v.project!==(draft.project??null)||
    v.overcharge!==Boolean(draft.overcharge)||v.ready!==true||typeof v.city_name!=="string"||!v.city_name||v.city_name.length>100||
    JSON.stringify(v.additional_city_ids)!==JSON.stringify(draft.additional_city_ids)||
    typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)||!integer(v.expires_in,1,120))throw new Error("Invalid worker preview");
  if(cities.length>1||projects.length>1){
    const expected=cities.flatMap(id=>projects.map(project=>({id,project})));
    if(!Array.isArray(v.assignments)||v.assignments.length!==expected.length||
      !v.assignments.every((r,i)=>row(r,expected[i].id,expected[i].project,task,draft)))throw new Error("Invalid worker assignment rows");
    const rows=v.assignments as WorkerAssignment[];
    const names=new Map<number,string>();
    for(const r of rows){if(names.has(r.city_id)&&names.get(r.city_id)!==r.city_name)throw new Error("City changed");names.set(r.city_id,r.city_name);}
    const current=rows.some(r=>r.current===null)?null:rows.reduce((n,r)=>n+r.current!,0);
    if(names.get(city)!==v.city_name||v.current!==current||["maximum","extra","target"].some(k=>v[k]!==rows.reduce((n,r)=>n+r[k as "maximum"|"extra"|"target"],0)))throw new Error("Invalid totals");
  }else if(v.assignments!==undefined||!row(v,city,projects[0],task,draft))throw new Error("Invalid worker preview");
  return v as unknown as WorkerPlan;
}
