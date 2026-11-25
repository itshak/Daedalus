import {test} from "node:test";
import assert from "node:assert/strict";
import {parseExtensionStatus,validExtensionDraft} from "../lib/extension-settings.ts";
import {allowedRequest} from "../lib/request-policy.ts";
test("extension registration is limited to exact approved ID, hash and state",()=>{
  const row={id:"reviewed",name:"Reviewed",sha256:"a".repeat(64),verified:true,registered:false};
  const value={account_id:"alpha",scope:"worker_global",legacy_override:false,unreviewed_count:1,extensions:[row]};
  assert.deepEqual(parseExtensionStatus(value,"alpha"),value);
  assert.throws(()=>parseExtensionStatus(value,"beta"));
  assert.throws(()=>parseExtensionStatus({...value,extensions:[{...row,path:"/private/file.py"}]},"alpha"));
  const draft={id:row.id,sha256:row.sha256,registered:true,expected_registered:false,confirmed_global:true};
  assert.equal(validExtensionDraft(draft),true);
  assert.equal(validExtensionDraft({...draft,id:"../code"}),false);
  assert.equal(validExtensionDraft({...draft,source:"arbitrary"}),false);
  assert.equal(allowedRequest("GET",["accounts","alpha","extensions"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","extensions"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","extensions"],new URLSearchParams("path=unsafe")),false);
});
