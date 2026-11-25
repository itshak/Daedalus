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
