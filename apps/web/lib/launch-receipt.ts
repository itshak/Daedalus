import {scopedActivity} from "./activity-history.ts";
type Outcome="started"|"rejected"|"uncertain";
const object=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
export function launchReceipt(value:unknown,account:string,task:string,requestId:string):Outcome {
  if(!object(value)||value.account_id!==account||value.task!==task||value.request_id!==requestId)return "uncertain";
  if(value.status==="started"&&typeof value.task_id==="string"&&/^[a-f0-9]{24}$/.test(value.task_id)&&typeof value.pid==="number"&&Number.isSafeInteger(value.pid)&&value.pid>0)return "started";
  return value.status==="rejected"?"rejected":"uncertain";
}
export function activityReceipt(value:unknown,account:string,task:string,requestId:string):Outcome {
  const page=scopedActivity(value,account,null,"all");
  const match=page.events.find(r=>r.request_id===requestId&&r.task===task);
  return match?.status==="started"?"started":match?.status==="rejected"?"rejected":"uncertain";
}
/** One dispatch only. On a lost response, consult read-only durable receipts;
 * never infer success from an unrelated task or retry a state-changing call. */
export async function confirmedLaunch(dispatch:()=>Promise<unknown>,readActivity:()=>Promise<unknown>,account:string,task:string,requestId:string):Promise<Outcome>{
  try{
    const outcome=launchReceipt(await dispatch(),account,task,requestId);
    if(outcome!=="uncertain")return outcome;
  }catch{/* lost/rejected response: durable receipt is authoritative */}
  try{return activityReceipt(await readActivity(),account,task,requestId);}
  catch{return "uncertain";}
}
