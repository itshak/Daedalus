/** Redacted operational audit metadata. No body, headers, account, URL, or credentials. */
import { REVIEW_START_ROUTES } from "./generated-operation-contract.ts";
const actions=new Set([...REVIEW_START_ROUTES,"tasks","reviewed-batch-check","stop","acknowledge","policy","bulk","pause","unpause","resume-now","import-saved-token","shipment-plan","reward-distribution-plan","construction-plan","training-plan","donation-plan","worker-plan","layout-plan","build-plan","station-plan","grind-plan","attack-plan","vacation-plan","construction-start","training-start","donation-start","worker-start","layout-start","build-start","station-start","grind-start","attack-start","vacation-start","begin","replace","clear","register","unregister","save","test"]);
export function gatewayAuditRecord(method:string,parts:string[],role:string,status:number,operatorId:string){
  if(method!=="POST"&&method!=="PUT")return null;
  const action=parts.at(-1)??"";
  return {event:"daedalus_gateway_mutation",operator_id:/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(operatorId)?operatorId:"unknown",role:["owner","operator","viewer"].includes(role)?role:"unknown",method,action:actions.has(action)?action:"other_reviewed_operation",outcome:status>=200&&status<300?"controller_response":status>=400&&status<500?"rejected":"uncertain",status:Number.isInteger(status)&&status>=100&&status<=599?status:502};
}
