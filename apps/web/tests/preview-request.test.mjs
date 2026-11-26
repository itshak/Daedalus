import {test} from "node:test";
import assert from "node:assert/strict";
import {controllerTimeout,isReviewPreview,fillPreviewMessage,fillPreviewHttpMessage} from "../lib/preview-request.ts";

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

test("warehouse failure identifies gateway, access and endpoint errors without raw details",()=>{
  assert.match(fillPreviewHttpMessage(524),/connection failed/);
  assert.match(fillPreviewHttpMessage(403),/access denied/);
  assert.match(fillPreviewHttpMessage(404),/endpoint unavailable/);
  assert.match(fillPreviewHttpMessage(503),/backend failed/);
  assert.equal(fillPreviewMessage(fillPreviewHttpMessage(524)),fillPreviewHttpMessage(524));
});
