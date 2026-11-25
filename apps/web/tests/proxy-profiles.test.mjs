import {test} from "node:test";
import assert from "node:assert/strict";
import {parseProxyStatus,validProxyDraft} from "../lib/proxy-profiles.ts";
import {allowedRequest} from "../lib/request-policy.ts";
test("only reviewed account network profiles and fixed actions are allowed",()=>{
  const revision="a".repeat(64),draft={action:"save",profile:"office",revision,confirmed:true};
  const state={account_id:"alpha",revision,enabled:false,current:null,allow_direct:true,busy:false,
    profiles:[{id:"office",label:"Office network",protocol:"http"}],result:"observed"};
  assert.equal(validProxyDraft(draft),true);
  assert.equal(validProxyDraft({...draft,profile:"legacy"}),false);
  assert.equal(validProxyDraft({...draft,url:"http://example.invalid:80"}),false);
  assert.equal(validProxyDraft({...draft,profile:"http://example.invalid:80"}),false);
  assert.deepEqual(parseProxyStatus(state,"alpha"),state);
  assert.throws(()=>parseProxyStatus(state,"beta"));
  assert.throws(()=>parseProxyStatus({...state,profiles:[{...state.profiles[0],url:"hidden"}]},"alpha"));
  assert.throws(()=>parseProxyStatus({...state,result:"saved"},"alpha",draft));
  assert.equal(parseProxyStatus({...state,enabled:true,current:"office",result:"saved"},"alpha",draft).current,"office");
  assert.equal(allowedRequest("GET",["accounts","alpha","proxy-settings"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","proxy-settings"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["accounts","alpha","proxy-settings"],new URLSearchParams("url=x")),false);
});
