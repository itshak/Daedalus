import {test} from "node:test";
import assert from "node:assert/strict";
import {fixedTavernReview,validNativeConfig} from "../lib/native-task-contract.ts";
test("fixed tavern review uses actual serving choices and rejects inconsistent data",()=>{
  const row={city_id:11,city_name:"Athens",has_tavern:true,serving_level:1,wine_per_hour:5,serving_options:[[0,0],[1,5],[2,12],[3,20],[4,30]]};
  const draft=fixedTavernReview([row],75);
  assert.deepEqual(draft.rows,[{city_id:11,city_name:"Athens",current_level:1,max_level:4,target_level:3,current_wine:5,target_wine:20}]);
  assert.equal(validNativeConfig("tavernManager",{run_hours:0,fixed_servings:draft}),true);
  assert.equal(validNativeConfig("tavernManager",{run_hours:2,fixed_servings:draft}),false);
  assert.equal(fixedTavernReview([row,row],75),null);
  assert.equal(fixedTavernReview([{...row,wine_per_hour:6}],75),null);
  assert.equal(fixedTavernReview([{...row,serving_options:null}],75),null);
  draft.rows[0].target_level=4;
  assert.equal(validNativeConfig("tavernManager",{run_hours:0,fixed_servings:draft}),false);
});
