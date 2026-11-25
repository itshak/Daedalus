import {test} from "node:test";
import assert from "node:assert/strict";
import {validNativeConfig,validNativeLaunch,playerNames,scopedCities,readyPreflight,MAX_AMOUNT} from "../lib/native-task-contract.ts";
test("fixed shipment: strict route shape, positive quantities, distinct cities, no external/raw override",()=>{
  const route={from:1,to:2,resources:[5,0,0,0,0]};
  const config={routes:[route],useFreighters:false};
  assert.equal(validNativeConfig("sendResources",config),true);
  for(const r of [{...route,to:1},{...route,to:"2"},{...route,island:9},{...route,resources:[0,0,0,0,0]},{...route,resources:[-1,0,0,0,0]}])
    assert.equal(validNativeConfig("sendResources",{...config,routes:[r]}),false);
  assert.equal(validNativeConfig("sendResources",{...config,transfer_id:"untrusted"}),false);
  assert.equal(validNativeConfig("sendResources",{...config,routes:[{...route,resources:[MAX_AMOUNT,0,0,0,0]},route]}),false);
});
test("resource policies and alerts are operation-specific",()=>{
  assert.equal(validNativeConfig("distributeResources",{resource:"wine",mode:"producers",cities_ids:[1,2],useFreighters:true}),true);
  assert.equal(validNativeConfig("distributeResources",{resource:"wood",mode:"producers",cities_ids:[1,2],useFreighters:true}),false);
  assert.equal(validNativeConfig("consolidateResources",{limits:[-1,0,20,-1,-1],sourceCityIds:[1],destinationCityId:2,intervalInHours:2,shipType:3}),true);
  assert.equal(validNativeConfig("consolidateResources",{limits:[-1,-1,-1,-1,-1],sourceCityIds:[1],destinationCityId:2,intervalInHours:2,shipType:3}),false);
  const manager={mode:"consolidate",origin_cities:[1],destination_city:2,send_mode:"keep",resource_config:[0,null,null,null,null],interval_hours:0,useFreighters:false,notify:"none"};
  assert.equal(validNativeConfig("resourceTransportManager",manager),true);
  assert.equal(validNativeConfig("resourceTransportManager",{...manager,send_mode:"send"}),false);
  assert.equal(validNativeConfig("resourceTransportManager",{mode:"distribute",origin_city:1,destination_cities:[2],resource_config:[1,0,0,0,0],interval_hours:4,useFreighters:true,notify:"all"}),true);
  assert.equal(validNativeConfig("alertAttacks",{minutes:3}),true);
  assert.equal(validNativeConfig("alertAttacks",{minutes:2}),false);
  assert.equal(validNativeConfig("alertLowWine",{hours:4,auto_transfer:true,transfer_amount:0}),false);
  assert.equal(validNativeConfig("alertLowWine",{hours:4,auto_transfer:false,transfer_amount:0}),true);
});
test("launch requires reviewed operation, exact shape, confirmation and v4 request ID",()=>{
  const request={task:"alertAttacks",config:{minutes:20},confirmed:true,request_id:"12345678-1234-4234-8234-123456789abc"};
  assert.equal(validNativeLaunch(request),true);
  for(const invalid of [{...request,confirmed:false},{...request,task:"developer"},{...request,request_id:"123"},{...request,config:{minutes:20,token:"secret"}},{...request,extra:true}])
    assert.equal(validNativeLaunch(invalid),false);
});
test("player first, duplicate display, scoped inventory and preflight fail closed",()=>{
  const accounts=[{id:"a",player:"Monjo",label:"Imported IkaBot identity 01",email:"a@example.org"},{id:"b",player:"Ais"},{id:"c",player:"Monjo",world:"s2"}];
  const names=playerNames(accounts);
  assert.match(names.a,/^Monjo/);assert.notEqual(names.a,names.c);assert.equal(names.b,"Ais");
  const data={account_id:"a",cities:[{id:1,name:"Actual city"}]};
  assert.equal(scopedCities(data,"a").length,1);assert.deepEqual(scopedCities(data,"b"),[]);
  assert.deepEqual(scopedCities({...data,synthetic_demo:true},"a"),[]);
  const p={account_id:"a",task:"alertAttacks",ready:true,unresolved_request:false};
  assert.equal(readyPreflight(p,"a","alertAttacks"),true);
  assert.equal(readyPreflight(p,"b","alertAttacks"),false);
  assert.equal(readyPreflight({...p,unresolved_request:true},"a","alertAttacks"),false);
});
