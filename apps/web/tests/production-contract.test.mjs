import {test} from "node:test";
import assert from "node:assert/strict";
import {verifyPriorityReview,verifyProductionRuns,verifyReconciliation} from "../lib/production-contract.ts";
import {allowedRequest} from "../lib/request-policy.ts";
const draft={resource:"crystal",mode:"maximum",amount:null,overcharge:true,available_only:false,allow_fallback:false};
const plan={city_id:1,island_id:2,resource:"crystal",luxury:"crystal",target_kind:"tradegood",donor_kind:"resource",target_before:400,donor_before:700,desired:900,target_after:900,donor_release:300,donor_after:400,shortfall:0,fallback:false,free_citizens:200,target_capacity:[750,150],donor_capacity:[700,100],draft};
const review=p=>({account_id:"a",city_id:1,task:"modifyProduction",ready:true,plans:[p],preview_id:"a".repeat(43),expires_in:120});
const verify=p=>verifyPriorityReview(review(p),"a",[{city_id:1,draft:p.draft}]);
test("priority review verifies exact displacement and account identity",()=>{
  assert.equal(verify(plan).plans[0].donor_release,300);
  assert.throws(()=>verify({...plan,donor_release:301}));
  assert.throws(()=>verifyPriorityReview(review(plan),"b",[{city_id:1,draft}]));
  assert.throws(()=>verify({...plan,draft:{...draft,available_only:true}}));
});
test("unknown-capacity fallback explicitly authorizes full release, not invented target",()=>{
  const fallback={...plan,desired:null,target_after:null,donor_after:null,shortfall:null,fallback:true,donor_release:700,target_capacity:[null,150],draft:{...draft,allow_fallback:true}};
  assert.equal(verify(fallback).plans[0].desired,null);
  assert.throws(()=>verify({...fallback,donor_release:699}));
  assert.throws(()=>verify({...fallback,target_after:900}));
});
test("both-resource review permits only bounded explicit secondary increase",()=>{
  const both={...plan,free_citizens:700,donor_release:0,donor_after:800,draft:{...draft,fill_both:true}};
  assert.equal(verify(both).plans[0].donor_after,800);
  assert.throws(()=>verify({...both,donor_after:801}));
});
test("history and reconciliation routes and receipts remain account scoped",()=>{
  const id="12345678-1234-4234-8234-123456789abc";
  const row={city_id:1,resource:"crystal",status:"running",target_before:400,donor_before:700,desired:null,donor_release:700,stages:[{stage:"release",kind:"resource",value:0,status:"pending"}],result:null};
  const history={account_id:"a",runs:[{run_id:id,status:"prepared",cities:[row]}]};
  assert.equal(verifyProductionRuns(history,"a")[0].cities[0].stages[0].status,"pending");
  assert.throws(()=>verifyProductionRuns(history,"b"));
  const reconciled={account_id:"a",run_id:id,status:"review",preview_id:"b".repeat(43),expires_in:120,observations:[{city_id:1,city_name:"Synthetic",island_id:2,luxury:"crystal",resource:0,tradegood:400}]};
  assert.equal(verifyReconciliation(reconciled,"a",id).observations[0].resource,0);
  assert.throws(()=>verifyReconciliation(reconciled,"b",id));
  assert.equal(allowedRequest("GET",["accounts","a","production-runs"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","a","production-runs",id,"reconcile"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","a","production-runs","invalid","reconcile"],new URLSearchParams()),false);
});


test("a definitively refused target and confirmed restoration are visible as partial execution",()=>{
  const id="12345678-1234-4234-8234-123456789abc";
  const row={city_id:1,resource:"crystal",status:"rejected",target_before:400,donor_before:700,
    desired:900,donor_release:300,stages:[
      {stage:"release",kind:"resource",value:400,status:"confirmed"},
      {stage:"target",kind:"tradegood",value:900,status:"rejected",observed:{resource:400,tradegood:400}},
      {stage:"restore",kind:"resource",value:700,status:"confirmed"}],
    result:{city_id:1,target:400,donor:700,shortfall:500}};
  assert.equal(verifyProductionRuns({account_id:"a",runs:[{run_id:id,status:"partial",cities:[row]}]},"a")[0].cities[0].stages[1].status,"rejected");
});
