import {test} from "node:test";
import assert from "node:assert/strict";
import {scopedActivity,activityCsv} from "../lib/activity-history.ts";
test("receipt pages are scoped, bounded, and export only reviewed metadata",()=>{
  const event={request_id:"a1234567-1234-4234-8234-123456789abc",task:"alertAttacks",status:"started",created_at:null,updated_at:1};
  const page={account_id:"a",events:[event],next_before:5};
  assert.equal(scopedActivity(page,"a",10,"all").events[0].task,"alertAttacks");
  assert.throws(()=>scopedActivity(page,"b",null,"all"));
  assert.throws(()=>scopedActivity(page,"a",5,"all"));
  assert.throws(()=>scopedActivity(page,"a",null,"rejected"));
  assert.throws(()=>scopedActivity({...page,events:[{...event,task:"=1+1"}]},"a",null,"all"));
  assert.throws(()=>scopedActivity({...page,events:[{...event,token:"secret"}]},"a",null,"all"));
  assert.match(activityCsv(page.events),/alertAttacks,started,,1/);
});
