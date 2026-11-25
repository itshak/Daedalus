import {test} from "node:test";
import assert from "node:assert/strict";
import {scopedStudyChoices,validNativeConfig} from "../lib/native-task-contract.ts";

test("research advisor choices are named, exact and mutually exclusive with experiments",()=>{
  const row={index:0,name:"Navigation",research_type:"seafaring"};
  assert.deepEqual(scopedStudyChoices([row]),[row]);
  assert.equal(scopedStudyChoices(undefined),null);
  assert.equal(validNativeConfig("research",{study_choice:row}),true);
  assert.equal(validNativeConfig("research",{study_choice:row,cities_ids:[1],qty:1}),false);
  assert.equal(validNativeConfig("research",{study_choice:{...row,research_type:"a&url=x"}}),false);
  assert.throws(()=>scopedStudyChoices([row,row]));
  assert.throws(()=>scopedStudyChoices([{...row,ajaxrequest:"arbitrary"}]));
});
