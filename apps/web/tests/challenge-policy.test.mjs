import {test} from "node:test";
import assert from "node:assert/strict";
import {parseChallengePolicy,validChallengeDraft} from "../lib/challenge-policy.ts";
import {allowedRequest} from "../lib/request-policy.ts";
test("human challenge policy rejects foreign scope and solver configuration",()=>{
  const value={account_id:"alpha",mode:"stop",notification_ready:false};
  assert.deepEqual(parseChallengePolicy(value,"alpha"),value);
  assert.throws(()=>parseChallengePolicy(value,"beta"));
  const draft={mode:"notify_and_stop",expected_mode:"stop",confirmed:true};
  assert.equal(validChallengeDraft(draft),true);
  assert.equal(validChallengeDraft({...draft,mode:"automatic"}),false);
  assert.equal(validChallengeDraft({...draft,solver:"arbitrary"}),false);
  assert.equal(allowedRequest("GET",["accounts","alpha","challenge-policy"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","challenge-policy"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","challenge-policy"],new URLSearchParams("answer=unsafe")),false);
});
