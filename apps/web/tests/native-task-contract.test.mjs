import {test} from "node:test";
import assert from "node:assert/strict";
import {validNativeConfig,validNativeLaunch,playerNames,scopedCities,readyPreflight,MAX_AMOUNT,launchAlertBatch,validWorkerDraft,validWorkerLaunch} from "../lib/native-task-contract.ts";
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
  assert.equal(validNativeConfig("resourceTransportManager",{...manager,notify:["none"]}),false);
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

test("domain editors accept exact native contracts and reject foreign-shaped data",()=>{
  const cases=[
    ["loginDaily",{wine_city:1,wood_city:null,luxury_city:2,favour_tasks:["resource"],collect_ambrosia:false}],
    ["research",{cities_ids:[1,2],qty:null}],
    ["tavernManager",{cities_ids:[1],run_hours:8,notification_mode:1}],
    ["activateMiracle",{wonder:"3",iterations:1}],
    ["activateShrine",{godids:[1,2],mode:2,times:0}],
    ["donationBot",{cities_dict:{"1":{donation_type:"resource",percentage:10}},waiting_time:10,donate_method:1}],
    ["autoPirate",{pirateCount:1,pirateSchedule:false,pirateMissionChoice:1,pirateMissionDayChoice:null,pirateMissionNightChoice:null,dayStart:null,dayEnd:null,nightStart:null,nightEnd:null,autoConvert:"n",convertPerMission:0,maxRandomWaitingTime:0,piracyCities:[{id:1}]}],
    ["searchForIslandSpaces",{time:10,islandList:["50:50"],fights:"n"}],
    ["dumpWorld",{waiting_time:2,coords:[50,50],radius:5,shallow:false,non_empty_islands:true}]
  ];
  for(const [task,c] of cases){
    assert.equal(validNativeConfig(task,c),true,task);
    assert.equal(validNativeConfig(task,{...c,raw:"override"}),false,task);
  }
  assert.equal(validNativeConfig("research",{cities_ids:[1,2],qty:1}),false);
  assert.equal(validNativeConfig("activateShrine",{godids:[1,1],mode:2,times:0}),false);
  assert.equal(validNativeConfig("donationBot",{cities_dict:{"1":{donation_type:"resource",percentage:101}},waiting_time:10,donate_method:1}),false);
});
test("military and trade forms accept reviewed inventory shapes and bounded quantities",()=>{
  const train={city:{id:"1",pos:"2",cityName:"Town"},tranings:[[{unit_type_id:301,cantidad:5}]],trainTroops:true,replicate:"n",countRepeat:0,cityTrainings:[],units:[]};
  const upgrade={jobs:[{city_id:1,upgrades:[{unitId:"301",upgradeType:"attack",target:2}]}]};
  const city={id:"1",pos:2,rango:3,name:"Town",cityName:"Town",availableResources:[100,100,100,100,100]};
  const quote={ciudadDestino:"Other",jugadorAComprar:"Trader",amountAvailable:5,tipo:"Wood",precio:4,destinationCityId:"2",cityId:"1",position:"2",type:"1",resource:"resource"};
  const buy={city,offers:[quote],amount_to_buy:5};
  const sell={mode:"create_offer",amount_to_sell:5,price:4,resource_type:0,sell_market_capacity:10,city};
  for(const [task,c] of [["trainArmy",train],["UpgradeUnits",upgrade],["buyResources",buy],["sellResources",sell]]){
    assert.equal(validNativeConfig(task,c),true,task);
    assert.equal(validNativeConfig(task,{...c,extra:"no"}),false,task);
  }
  assert.equal(validNativeConfig("trainArmy",{...train,replicate:"y"}),false);
  assert.equal(validNativeConfig("buyResources",{...buy,amount_to_buy:6}),false);
  assert.equal(validNativeConfig("sellResources",{...sell,price:0}),false);
});

test("alert batch preflights every account before any dispatch and stops on uncertainty",async()=>{
  const targets=["a","b","c"].map(id=>({id,name:id,enabled:true}));
  const calls=[];
  const preflight=async id=>{calls.push("pre:"+id);return {account_id:id,task:"alertAttacks",ready:id!=="b",unresolved_request:false};};
  const dispatch=async id=>{calls.push("start:"+id);throw new Error("should not run");};
  const blocked=await launchAlertBatch("alertAttacks",{minutes:20},targets,preflight,dispatch,()=>crypto.randomUUID(),()=>true);
  assert.deepEqual(calls,["pre:a","pre:b","pre:c"]);
  assert.deepEqual(blocked.map(r=>r.status),["not attempted","blocked","not attempted"]);
  calls.length=0;
  const receipts=await launchAlertBatch("alertAttacks",{minutes:20},targets,async id=>{
    calls.push("pre:"+id);return {account_id:id,task:"alertAttacks",ready:true,unresolved_request:false};
  },async(id,rid)=>{
    calls.push("start:"+id);
    return {account_id:id,request_id:rid,task:"alertAttacks",status:id==="b"?"unconfirmed":"started"};
  },()=>crypto.randomUUID(),()=>true);
  assert.deepEqual(calls,["pre:a","pre:b","pre:c","start:a","start:b"]);
  assert.deepEqual(receipts.map(r=>r.status),["started","uncertain","not attempted"]);
  await assert.rejects(launchAlertBatch("sendResources",{minutes:20},targets,preflight,dispatch,()=>crypto.randomUUID(),()=>true));
});

test("worker assignments accept only operation-specific drafts and reviewed tickets",()=>{
  assert.equal(validWorkerDraft("modifyProduction",{percentage:100,project:"resource",overcharge:true}),true);
  assert.equal(validWorkerDraft("modifyAcademyWorkers",{percentage:0}),true);
  assert.equal(validWorkerDraft("modifyTempleWorkers",{percentage:50}),true);
  assert.equal(validWorkerDraft("modifyProduction",{percentage:50,project:"resource",overcharge:true}),false);
  assert.equal(validWorkerDraft("modifyAcademyWorkers",{percentage:50,expected:{}}),false);
  assert.equal(validWorkerDraft("modifyTempleWorkers",{percentage:true}),false);
  const receipt={task:"modifyAcademyWorkers",preview_id:"a".repeat(43),request_id:"12345678-1234-4234-8234-123456789abc",confirmed:true};
  assert.equal(validWorkerLaunch(receipt),true);
  assert.equal(validWorkerLaunch({...receipt,task:"developer"}),false);
  assert.equal(validWorkerLaunch({...receipt,confirmed:false}),false);
  assert.equal(validWorkerLaunch({...receipt,config:{}}),false);
});
