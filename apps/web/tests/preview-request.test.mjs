import {test} from "node:test";
import assert from "node:assert/strict";
import {controllerTimeout,isReviewPreview,fillPreviewMessage} from "../lib/preview-request.ts";

test("only reviewed read-only previews get an extended timeout",()=>{
 const preview=["accounts","alpha","reward-distribution-plan"];
 assert.equal(isReviewPreview(preview,"POST"),true);
 assert.equal(controllerTimeout(preview,"POST"),115000);
 assert.equal(controllerTimeout(["accounts","alpha","tasks","fill-warehouse-start"],"POST"),25000);
 assert.equal(controllerTimeout(preview,"GET"),12000);
});
test("only allowlisted nonsecret warehouse reasons can cross the gateway",()=>{
 const message="Incoming cargo could not be verified. No transfer was started.";
 assert.equal(fillPreviewMessage(message),message);
 assert.equal(fillPreviewMessage("synthetic private payload"),null);
 assert.equal(fillPreviewMessage({detail:message}),null);
});
