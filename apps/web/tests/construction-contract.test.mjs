import {test} from "node:test";
import assert from "node:assert/strict";
import {scopedConstructionPlan,validSupply} from "../lib/construction-contract.ts";
const options={source_ids:[2,3],useFreighters:false,round_up:true,supply_only:false};
const targets=[{position:1,target_level:6}];
const space=[1000,1000,1000,1000,1000];
const routes=[{from:2,to:1,origin_name:"First",destination_name:"Target",resources:[400,0,150,0,0],stock:[400,0,150,0,0],destination_space:space,first_load_limit:200,minimum_loads:2},{from:3,to:1,origin_name:"Second",destination_name:"Target",resources:[400,0,50,0,0],stock:[500,0,100,0,0],destination_space:space,first_load_limit:200,minimum_loads:2}];
const plan={account_id:"alpha",city_id:1,city_name:"Target",costs:[1000,0,200,0,0],available:[250,0,30,0,0],missing:[750,0,170,0,0],estimated_seconds:120,buildings:[{position:1,name:"Town Hall",current_level:5,target_level:6}],ready:true,preview_id:"a".repeat(43),expires_in:120,supply:{options,target:[800,0,200,0,0],remaining:[0,0,0,0,0],destination_space:space,shipment:{routes,useFreighters:false,capacity:100,available_ships:2,total_ships:3,ready:true}}};
test("construction supply validates exact reviewed route and rounded shortage",()=>{
 assert.equal(validSupply(options,1),true);
 assert.equal(validSupply({...options,source_ids:[1]},1),false);
 assert.equal(scopedConstructionPlan(plan,"alpha",1,targets,options,[1,2,3]).ready,true);
 assert.throws(()=>scopedConstructionPlan(plan,"beta",1,targets,options,[1,2,3]));
 assert.throws(()=>scopedConstructionPlan(plan,"alpha",1,targets,options,[1,2]));
 assert.throws(()=>scopedConstructionPlan(plan,"alpha",1,targets,undefined,[1,2,3]));
 const changed=structuredClone(plan);changed.supply.shipment.routes[0].resources[0]=399;
 assert.throws(()=>scopedConstructionPlan(changed,"alpha",1,targets,options,[1,2,3]));
});
