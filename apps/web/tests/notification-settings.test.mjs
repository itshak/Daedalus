import {test} from "node:test";
import assert from "node:assert/strict";
import {allowedRequest} from "../lib/request-policy.ts";
import {notificationOwnerAllowed,validNotificationEnvelope,validNotificationSettings,parseNotificationReceipt} from "../lib/notification-settings.ts";
test("provider configuration is owner-only and permits encrypted writes only",()=>{
  const parts=["accounts","alpha","notifications","telegram","complete"];
  assert.equal(allowedRequest("POST",parts,new URLSearchParams()),true);
  assert.equal(allowedRequest("GET",parts,new URLSearchParams()),false);
  assert.equal(allowedRequest("POST",parts,new URLSearchParams("unsafe=1")),false);
  assert.equal(notificationOwnerAllowed("owner",parts),true);
  assert.equal(notificationOwnerAllowed("operator",parts),false);
  assert.equal(notificationOwnerAllowed("viewer",parts),false);
  assert.equal(validNotificationEnvelope({mode:"replace",bot_token:"synthetic"}),false);
  assert.equal(validNotificationEnvelope({ticket_id:"a".repeat(43),version:1,confirmed_global:true,client_key:"a".repeat(87),nonce:"a".repeat(16),ciphertext:"a".repeat(23)}),true);
  assert.equal(validNotificationSettings("discord",{mode:"replace",webhook_url:"https://127.0.0.1/"}),false);
  assert.throws(()=>parseNotificationReceipt({account_id:"beta",provider:"telegram",scope:"worker_global",result:"configured"},"alpha","telegram"));
});
