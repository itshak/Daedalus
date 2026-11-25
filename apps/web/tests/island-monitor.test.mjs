import {test} from "node:test";
import assert from "node:assert/strict";
import {scopedExternalCities,validNativeConfig} from "../lib/native-task-contract.ts";
test("island monitor accepts exact bounded coordinates, including empty verified islands",()=>{
  assert.deepEqual(scopedExternalCities({account_id:"a",x:60,y:70,cities:[]},"a",60,70),[]);
  assert.throws(()=>scopedExternalCities({account_id:"b",x:60,y:70,cities:[]},"a",60,70));
  const draft={time:20,islandList:["60:70","1:100"],fights:"n"};
  assert.equal(validNativeConfig("searchForIslandSpaces",draft),true);
  assert.equal(validNativeConfig("searchForIslandSpaces",{...draft,islandList:[]}),true);
  assert.equal(validNativeConfig("searchForIslandSpaces",{...draft,islandList:["0:50"]}),false);
  assert.equal(validNativeConfig("searchForIslandSpaces",{...draft,islandList:["101:50"]}),false);
  assert.equal(validNativeConfig("searchForIslandSpaces",{...draft,islandList:["60:70","60:70"]}),false);
});
