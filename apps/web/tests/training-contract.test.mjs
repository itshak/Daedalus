import {test} from "node:test";
import assert from "node:assert/strict";
import {validTrainingDraft,scopedTrainingPlan} from "../lib/training-contract.ts";
import {allowedRequest} from "../lib/request-policy.ts";
const draft={city_ids:[1,2],train_troops:true,rounds:[[{unit_type_id:301,cantidad:2}],[{unit_type_id:302,cantidad:3}]],cycles:2};
const rows=[1,2].map(id=>({city_id:id,city_name:"Town "+id,position:3,stock:[100,0,0,0,100,10],
  rounds:[[{...draft.rounds[0][0],local_name:"Swordsman",costs:{wood:10,citizens:1}}],[{...draft.rounds[1][0],local_name:"Hoplite",costs:{wood:20,sulfur:5,citizens:1}}]],
  round_costs:[[20,0,0,0,0,2],[60,0,0,0,15,3]],total_costs:[160,0,0,0,30,10],ready:true}));
const plan={account_id:"alpha",...draft,cities:rows,ready:true,preview_id:"a".repeat(43),expires_in:120};
test("recruitment validates each round, city and total cost",()=>{
  assert.equal(validTrainingDraft(draft,1),true);
  assert.equal(validTrainingDraft(draft,2),false);
  assert.equal(validTrainingDraft({...draft,city_ids:[1,1]}),false);
  assert.equal(validTrainingDraft({...draft,cycles:11}),false);
  assert.equal(scopedTrainingPlan(plan,"alpha",draft,[1,2]).ready,true);
  assert.throws(()=>scopedTrainingPlan(plan,"beta",draft,[1,2]));
  assert.throws(()=>scopedTrainingPlan(plan,"alpha",draft,[1]));
  const changed=structuredClone(plan);changed.cities[0].total_costs[0]=159;
  assert.throws(()=>scopedTrainingPlan(changed,"alpha",draft,[1,2]));
});
test("only explicit reviewed training endpoints are allowed",()=>{
  assert.equal(allowedRequest("POST",["accounts","alpha","cities","1","training-plan"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","tasks","training-start"],new URLSearchParams()),true);
});
