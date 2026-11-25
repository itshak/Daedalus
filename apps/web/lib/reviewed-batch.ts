const endpoints:Record<string,string>={constructionList:"construction-start",sendResources:"shipment-start",donate:"donation-start",
  modifyProduction:"worker-start",modifyAcademyWorkers:"worker-start",modifyTempleWorkers:"worker-start",reorganizeCityBuildings:"layout-start",
  constructBuilding:"build-start",stationArmy:"station-start",autoBarbarians:"grind-start",attackBarbarians:"attack-start",vacationMode:"vacation-start"};
export type ReviewEntry={account_id:string;task:string;preview_id:string};
export type QueuedReview=ReviewEntry&{accountName:string;summary:string;expiresAt:number};
export type BatchResult={account_id:string;status:"started"|"blocked"|"unconfirmed"|"not attempted";request_id?:string;reason?:string};
function obj(v:unknown):v is Record<string,unknown>{return typeof v==="object"&&v!==null&&!Array.isArray(v);}
export function validReviewBatch(v:unknown):boolean{
  if(!obj(v)||Object.keys(v).length!==1||!Array.isArray(v.entries)||v.entries.length<1||v.entries.length>32)return false;
  const accounts=new Set(),tickets=new Set();
  for(const row of v.entries){
    if(!obj(row)||Object.keys(row).length!==3||typeof row.account_id!=="string"||!/^[a-z][a-z0-9_-]{0,47}$/.test(row.account_id)
       ||typeof row.task!=="string"||!Object.hasOwn(endpoints,row.task)||typeof row.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(row.preview_id)
       ||accounts.has(row.account_id)||tickets.has(row.preview_id))return false;
    accounts.add(row.account_id);tickets.add(row.preview_id);
  }
  return true;
}
export async function launchReviewedBatch(entries:ReviewEntry[],call:(path:string,body:unknown)=>Promise<unknown>,
  uuid:()=>string,active:()=>boolean):Promise<BatchResult[]>{
  if(!validReviewBatch({entries}))throw new Error("Invalid batch");
  const rows:BatchResult[]=entries.map(e=>({account_id:e.account_id,status:"not attempted"}));
  const checked=await call("tasks/reviewed-batch-check",{entries});
  if(!obj(checked)||!Array.isArray(checked.account_ids)||checked.account_ids.length!==entries.length||
     checked.account_ids.some((id,i)=>id!==entries[i].account_id)||!Array.isArray(checked.blocked))throw new Error("Invalid check");
  const seen=new Set();
  for(const row of checked.blocked){
    if(!obj(row)||Object.keys(row).length!==2||typeof row.account_id!=="string"||seen.has(row.account_id)||
       !entries.some(e=>e.account_id===row.account_id)||typeof row.reason!=="string"||
       !["review_unavailable","prerequisites","unavailable"].includes(row.reason))throw new Error("Invalid check");
    seen.add(row.account_id);
    const i=entries.findIndex(e=>e.account_id===row.account_id);
    rows[i]={account_id:row.account_id,status:"blocked",reason:row.reason};
  }
  if(seen.size)return rows;
  for(let i=0;i<entries.length;i++){
    if(!active())break;
    const entry=entries[i],rid=uuid();
    try{
      const endpoint=endpoints[entry.task];
      const reply=await call("accounts/"+encodeURIComponent(entry.account_id)+"/tasks/"+endpoint,
        {preview_id:entry.preview_id,request_id:rid,confirmed:true,...(endpoint==="worker-start"?{task:entry.task}:{})});
      if(!obj(reply)||reply.account_id!==entry.account_id||reply.task!==entry.task||reply.request_id!==rid||reply.status!=="started")throw new Error("Unconfirmed");
      rows[i]={account_id:entry.account_id,status:"started",request_id:rid};
    }catch{
      rows[i]={account_id:entry.account_id,status:"unconfirmed",request_id:rid};break;
    }
  }
  return rows;
}
