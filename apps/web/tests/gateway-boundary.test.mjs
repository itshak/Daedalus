import {test} from "node:test";
import assert from "node:assert/strict";
import {readBoundedBody,BodyLimitExceeded} from "../lib/bounded-body.ts";
import {gatewayAuditRecord} from "../lib/gateway-audit.ts";

test("bounded stream reads enforce bytes, not JavaScript code units",async()=>{
 assert.equal(await readBoundedBody(new Response("ЯЯЯ").body,6),"ЯЯЯ");
 await assert.rejects(readBoundedBody(new Response("ЯЯЯ").body,5),BodyLimitExceeded);
 await assert.rejects(readBoundedBody(new Response(new Uint8Array([255])).body,5),TypeError);
});
test("audit records only fixed operation metadata and never include raw route segments",()=>{
 const id="12345678-1234-4234-8234-123456789abc";
 assert.equal(gatewayAuditRecord("GET",["warehouses","synthetic-private-id"],"owner",200,id),null);
 const record=gatewayAuditRecord("POST",["accounts","synthetic-private-id","tasks","synthetic-secret"],"owner",503,id);
 assert.equal(record.outcome,"uncertain");assert.equal(record.action,"other_reviewed_operation");
 assert.equal(record.operator_id,id);assert.doesNotMatch(JSON.stringify(record),/synthetic-private-id|synthetic-secret/);
 assert.equal(gatewayAuditRecord("POST",["tasks"],"owner",200,id).outcome,"controller_response");
});
