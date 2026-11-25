import {test} from "node:test";
import assert from "node:assert/strict";
import {scopedStationPlan} from "../lib/station-contract.ts";
const draft={destination_city_id:2,ground:true,all_origins:true,both:true};
const rows=[1,3].flatMap(id=>[true,false].map(ground=>({city_id:id,city_name:"City "+id,ground,total:5,weight:ground?10:null,capacity:ground?20:null})));
const plan={account_id:"a",city_id:1,city_name:"City 1",destination_name:"Target",...draft,total:20,weight:20,capacity:20,ready:true,deployments:rows,preview_id:"a".repeat(43),expires_in:120};
test("all-city ground and fleet plans account for shared capacity",()=>{
  assert.equal(scopedStationPlan(plan,"a",1,draft,[1,2,3]).total,20);
  assert.throws(()=>scopedStationPlan(plan,"b",1,draft,[1,2,3]));
  assert.throws(()=>scopedStationPlan(plan,"a",1,draft,[1,2,3,4]));
  assert.throws(()=>scopedStationPlan({...plan,capacity:40},"a",1,draft,[1,2,3]));
  assert.throws(()=>scopedStationPlan({...plan,deployments:rows.slice(1)},"a",1,draft,[1,2,3]));
  assert.throws(()=>scopedStationPlan({...plan,both:undefined},"a",1,draft,[1,2,3]));
});
