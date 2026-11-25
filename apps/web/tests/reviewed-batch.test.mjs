import {test} from "node:test";
import assert from "node:assert/strict";
import {validReviewBatch,launchReviewedBatch} from "../lib/reviewed-batch.ts";
import {allowedRequest} from "../lib/request-policy.ts";
const entries=[{account_id:"alpha",task:"constructionList",preview_id:"a".repeat(43)},{account_id:"beta",task:"modifyProduction",preview_id:"b".repeat(43)},{account_id:"gamma",task:"sendResources",preview_id:"c".repeat(43)}];
const check={account_ids:entries.map(e=>e.account_id),blocked:[]};
test("review batch strict contract and allowlist",()=>{
  assert.equal(validReviewBatch({entries}),true);
  for(const invalid of [{entries:[]},{entries:[entries[0],entries[0]]},{entries:[{...entries[0],task:"developer"}]},{entries:[{...entries[0],config:{}}]},{entries:[entries[0],{...entries[1],preview_id:entries[0].preview_id}]}])assert.equal(validReviewBatch(invalid),false);
  assert.equal(allowedRequest("POST",["tasks","reviewed-batch-check"],new URLSearchParams()),true);
  assert.equal(allowedRequest("GET",["tasks","reviewed-batch-check"],new URLSearchParams()),false);
});
test("blocked preflight starts nothing",async()=>{
  let calls=0;
  const rows=await launchReviewedBatch(entries,async()=>{calls++;return {...check,blocked:[{account_id:"beta",reason:"prerequisites"}]};},()=>"id",()=>true);
  assert.equal(calls,1);assert.deepEqual(rows.map(r=>r.status),["not attempted","blocked","not attempted"]);
});
test("separate scoped requests; halt on mismatched receipt",async()=>{
  const calls=[];let n=0;
  const rows=await launchReviewedBatch(entries,async(path,body)=>{
    calls.push([path,body]);if(calls.length===1)return check;
    const entry=entries[calls.length-2];
    return {account_id:entry.account_id,task:entry.task,request_id:body.request_id,status:entry.account_id==="beta"?"unknown":"started"};
  },()=>String(++n),()=>true);
  assert.deepEqual(rows.map(r=>r.status),["started","unconfirmed","not attempted"]);
  assert.equal(calls.length,3);
  assert.equal(calls[1][0],"accounts/alpha/tasks/construction-start");
  assert.equal(calls[2][0],"accounts/beta/tasks/worker-start");
  assert.equal(calls[2][1].task,"modifyProduction");
  assert.notEqual(calls[1][1].request_id,calls[2][1].request_id);
});
