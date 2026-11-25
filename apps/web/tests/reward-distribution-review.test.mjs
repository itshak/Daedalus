import {test} from "node:test";
import assert from "node:assert/strict";
import {parseRewardDistributionReview,validRewardDistributionRequest} from "../lib/reward-distribution-review.ts";
import {validReviewBatch} from "../lib/reviewed-batch.ts";
test("daily and distribution tickets are scoped to exact independent drafts",()=>{
 const draft={wine_city:101,wood_city:null,luxury_city:null,favour_tasks:[],collect_ambrosia:false};
 const daily={account_id:"alpha",task:"loginDaily",draft,preview_id:"a".repeat(43),expires_in:120,
   observation:{cities:{wine_city:"Athens"},favour:20,limit:100,reset_seconds:500,collectable:0}};
 assert.equal(validRewardDistributionRequest({task:"loginDaily",draft}),true);
 assert.equal(parseRewardDistributionReview(daily,"alpha","loginDaily",draft).daily.favour,20);
 assert.throws(()=>parseRewardDistributionReview(daily,"beta","loginDaily",draft));
 const d={resource:"wood",mode:"even",cities_ids:[101,102],useFreighters:false};
 const row={from:101,to:102,resources:[200,0,0,0,0],origin_name:"Athens",destination_name:"Sparta",stock:[400,0,0,0,0],destination_space:[500,0,0,0,0],first_load_limit:100,minimum_loads:2};
 const plan={account_id:"beta",task:"distributeResources",draft:d,preview_id:"b".repeat(43),expires_in:120,
   observation:{routes:[row],capacity:100,total_ships:1,available_ships:1,ready:true,useFreighters:false}};
 assert.equal(parseRewardDistributionReview(plan,"beta","distributeResources",d).shipment.routes[0].resources[0],200);
 assert.throws(()=>parseRewardDistributionReview({...plan,observation:{...plan.observation,routes:[{...row,to:103}]}},"beta","distributeResources",d));
 assert.equal(validReviewBatch({entries:[{account_id:"alpha",task:"loginDaily",preview_id:daily.preview_id},{account_id:"beta",task:"distributeResources",preview_id:plan.preview_id}]}),true);
});

test("market preview checks exact offer allocation and quoted gold",()=>{
 const city={id:"42",name:"Athens",cityName:"Athens",pos:4,rango:3,availableResources:[5000,1000,500,0,0]};
 const offer={ciudadDestino:"Market",jugadorAComprar:"Seller",amountAvailable:1000,tipo:"wood",precio:7,destinationCityId:"777",cityId:"42",position:"4",type:"444",resource:"resource"};
 const draft={city,offers:[offer],amount_to_buy:500};
 const observation={rows:[{city:"Market",player:"Seller",amount:500,unit_price:7}],gold_total:3500,gold_available:10000,mode:"buy"};
 const result={account_id:"alpha",task:"buyResources",draft,observation,preview_id:"a".repeat(43),expires_in:120};
 assert.equal(validRewardDistributionRequest({task:"buyResources",draft}),true);
 assert.equal(parseRewardDistributionReview(result,"alpha","buyResources",draft).market.gold_total,3500);
 assert.throws(()=>parseRewardDistributionReview({...result,observation:{...observation,gold_total:1}},"alpha","buyResources",draft));
});

test("account policy reviews verify academy and workshop scope",()=>{
 const draft={cities_ids:[101],qty:2};
 const observation={academies:[{city_id:101,city_name:"Athens",crystal:300000,cooldown:false,can_experiment_now:true}]};
 const result={account_id:"alpha",task:"research",draft,observation,preview_id:"a".repeat(43),expires_in:120};
 assert.equal(validRewardDistributionRequest({task:"research",draft}),true);
 assert.match(parseRewardDistributionReview(result,"alpha","research",draft).policySummary,/Athens/);
 assert.throws(()=>parseRewardDistributionReview({...result,observation:{academies:[{...observation.academies[0],city_id:102}]}},"alpha","research",draft));
 const job={jobs:[{city_id:101,upgrades:[{unitId:"301",upgradeType:"offensive",target:3}]}]};
 const upgrades={city_id:101,upgrades:[{unit_id:"301",name:"Unit",upgrade_type:"offensive",description:"Attack",current_level:1,max_level:4,target:3}]};
 const plan={...result,task:"UpgradeUnits",draft:job,observation:upgrades};
 assert.match(parseRewardDistributionReview(plan,"alpha","UpgradeUnits",job).policySummary,/level 1 → 3/);
 assert.throws(()=>parseRewardDistributionReview({...plan,observation:{...upgrades,upgrades:[{...upgrades.upgrades[0],current_level:3}]}},"alpha","UpgradeUnits",job));
 assert.equal(validReviewBatch({entries:[{account_id:"alpha",task:"research",preview_id:"a".repeat(43)},{account_id:"beta",task:"UpgradeUnits",preview_id:"b".repeat(43)}]}),true);
});

test("recurring transport and island policy review checks observed scope",()=>{
 const draft={limits:[0,-1,100,-1,-1],sourceCityIds:[101],destinationCityId:102,intervalInHours:2,shipType:1};
 const cities=[{id:101,name:"Athens",coords:"10:20",stock:[1000,0,0,0,0],space:[2000,0,0,0,0]},{id:102,name:"Sparta",coords:"10:20",stock:[0,0,0,0,0],space:[2000,0,0,0,0]}];
 const observation={cities,fleets:{trade:{capacity:100,free:2,total:3}},external:null};
 const value={account_id:"alpha",task:"consolidateResources",draft,observation,preview_id:"a".repeat(43),expires_in:120};
 assert.equal(validRewardDistributionRequest({task:"consolidateResources",draft}),true);
 assert.match(parseRewardDistributionReview(value,"alpha","consolidateResources",draft).policySummary,/Athens/);
 assert.throws(()=>parseRewardDistributionReview({...value,observation:{...observation,cities:[cities[0],{...cities[1],id:999}]}},"alpha","consolidateResources",draft));
 assert.throws(()=>parseRewardDistributionReview({...value,observation:{...observation,fleets:{trade:{capacity:0,free:0,total:0}}}},"alpha","consolidateResources",draft));
 const monitor={time:5,islandList:["10:20"],fights:"n"};
 const reviewed={...value,task:"searchForIslandSpaces",draft:monitor,observation:{islands:["10:20"]}};
 assert.match(parseRewardDistributionReview(reviewed,"alpha","searchForIslandSpaces",monitor).policySummary,/10:20/);
 assert.throws(()=>parseRewardDistributionReview({...reviewed,observation:{islands:["20:10"]}},"alpha","searchForIslandSpaces",monitor));
 assert.equal(validReviewBatch({entries:[{account_id:"alpha",task:"consolidateResources",preview_id:value.preview_id},{account_id:"beta",task:"searchForIslandSpaces",preview_id:"b".repeat(43)}]}),true);
});

test("warehouse fill shares storage across all source cities and deducts incoming cargo",()=>{
 const draft={destination_city:103,resource:"marble",useFreighters:false};
 const observation={destination_city:103,destination_name:"Corinth",stock:350,free_space:150,incoming:20,budget:130,amount:130,sources:[{city_id:101,city_name:"Athens",stock:100,amount:100},{city_id:102,city_name:"Sparta",stock:200,amount:30}],capacity:100,total_ships:3,available_ships:2};
 const value={account_id:"alpha",task:"fillCityWarehouse",draft,observation,preview_id:"a".repeat(43),expires_in:120};
 assert.equal(validRewardDistributionRequest({task:"fillCityWarehouse",draft}),true);
 assert.match(parseRewardDistributionReview(value,"alpha","fillCityWarehouse",draft).policySummary,/planned transfer: 130/);
 assert.throws(()=>parseRewardDistributionReview({...value,observation:{...observation,amount:150}},"alpha","fillCityWarehouse",draft));
 assert.throws(()=>parseRewardDistributionReview({...value,observation:{...observation,sources:[observation.sources[0],{...observation.sources[1],amount:50}]}},"alpha","fillCityWarehouse",draft));
 assert.throws(()=>parseRewardDistributionReview(value,"beta","fillCityWarehouse",draft));
});
