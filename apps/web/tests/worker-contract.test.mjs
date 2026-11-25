import {test} from "node:test";
import assert from "node:assert/strict";
import {scopedWorkerPlan} from "../lib/worker-contract.ts";
import {validWorkerDraft} from "../lib/native-task-contract.ts";
const task="modifyProduction",draft={percentage:50,project:"both",overcharge:false,additional_city_ids:[2]};
const rows=[1,2].flatMap(id=>["resource","tradegood"].map(project=>({city_id:id,city_name:"Town "+id,project,current:25,maximum:100,extra:20,target:50})));
const plan={account_id:"a",task,city_id:1,city_name:"Town 1",...draft,maximum:400,extra:80,current:100,target:200,assignments:rows,ready:true,preview_id:"a".repeat(43),expires_in:120};
test("multi-city worker review checks both projects and exact aggregate targets",()=>{
  assert.equal(validWorkerDraft(task,draft),true);
  assert.equal(validWorkerDraft(task,{...draft,additional_city_ids:[2,2]}),false);
  assert.equal(scopedWorkerPlan(plan,"a",1,task,draft,[1,2]).target,200);
  assert.throws(()=>scopedWorkerPlan(plan,"b",1,task,draft,[1,2]));
  assert.throws(()=>scopedWorkerPlan(plan,"a",1,task,draft,[1]));
  assert.throws(()=>scopedWorkerPlan({...plan,target:201},"a",1,task,draft,[1,2]));
  assert.throws(()=>scopedWorkerPlan({...plan,assignments:[...rows.slice(0,3),rows[0]]},"a",1,task,draft,[1,2]));
});
