export const ACTIVITY_STATUSES=["dispatching","started","rejected","unconfirmed","operator_reconciled"] as const;
export type ReceiptStatus=typeof ACTIVITY_STATUSES[number];
export type ActivityFilter="all"|ReceiptStatus;
export type ActivityEvent={request_id:string;task:string;status:ReceiptStatus;created_at:number|null;updated_at:number|null};
export type ActivityPage={account_id:string;events:ActivityEvent[];next_before:number|null};
function object(v:unknown):v is Record<string,unknown>{return typeof v==="object"&&v!==null&&!Array.isArray(v);}
const timestamp=(v:unknown)=>v===null||(typeof v==="number"&&Number.isFinite(v)&&v>=0&&v<=253402300799);
export function scopedActivity(value:unknown,account:string,before:number|null,status:ActivityFilter):ActivityPage{
  if(!object(value)||value.account_id!==account||!Array.isArray(value.events)||value.events.length>50||
    (value.next_before!==null&&(typeof value.next_before!=="number"||!Number.isSafeInteger(value.next_before)||value.next_before<=0||(before!==null&&value.next_before>=before))))throw new Error("Invalid activity scope");
  const seen=new Set<string>();
  for(const row of value.events){
    if(!object(row)||Object.keys(row).length!==5||typeof row.request_id!=="string"||
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(row.request_id)||seen.has(row.request_id)||
      typeof row.task!=="string"||!/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(row.task)||
      !ACTIVITY_STATUSES.includes(row.status as ReceiptStatus)||(status!=="all"&&row.status!==status)||
      !timestamp(row.created_at)||!timestamp(row.updated_at))throw new Error("Invalid activity receipt");
    seen.add(row.request_id);
  }
  return value as unknown as ActivityPage;
}
export function activityCsv(rows:ActivityEvent[]):string{
  return ["request_id,task,status,created_at,updated_at",...rows.map(r=>[r.request_id,r.task,r.status,r.created_at??"",r.updated_at??""].join(","))].join("\n");
}
