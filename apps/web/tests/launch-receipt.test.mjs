import {test} from "node:test";
import assert from "node:assert/strict";
import {confirmedLaunch,launchReceipt,activityReceipt} from "../lib/launch-receipt.ts";
const id="12345678-1234-4123-8123-123456789abc",task="fillCityWarehouse",account="alpha";
const started={account_id:account,task,request_id:id,status:"started",task_id:"a".repeat(24),pid:123};
const activity=(status,overrides={})=>({account_id:account,next_before:null,events:[{request_id:id,task,status,created_at:1,updated_at:2,...overrides}]});
test("confirmed receipt is account, task and request bound",()=>{
 assert.equal(launchReceipt(started,account,task,id),"started");
 assert.equal(launchReceipt({...started,pid:null},account,task,id),"uncertain");
 assert.equal(launchReceipt({...started,account_id:"beta"},account,task,id),"uncertain");
});
test("lost response reconciles via exact durable receipt without another launch",async()=>{
 let starts=0,reads=0;
 const result=await confirmedLaunch(async()=>{starts++;throw Error("lost");},async()=>{reads++;return activity("started");},account,task,id);
 assert.equal(result,"started");assert.equal(starts,1);assert.equal(reads,1);
});
test("uncertain, foreign and unrelated activity never imply success",()=>{
 assert.equal(activityReceipt(activity("unconfirmed"),account,task,id),"uncertain");
 assert.equal(activityReceipt(activity("started",{task:"sendResources"}),account,task,id),"uncertain");
 assert.equal(activityReceipt(activity("rejected"),account,task,id),"rejected");
 assert.throws(()=>activityReceipt({...activity("started"),account_id:"beta"},account,task,id));
});
