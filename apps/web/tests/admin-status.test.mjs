import {test} from "node:test";
import assert from "node:assert/strict";
import {parseAdminStatus} from "../lib/admin-status.ts";
import {allowedRequest} from "../lib/request-policy.ts";
const settings={telegram:"configured",discord:"not_configured",proxy_enabled:true,proxy_protocol:"socks5",proxy_port:9050,proxy_auth:true,challenge_provider:"default",registered_extensions:0};
test("protected status permits only validated account-scoped projection",()=>{
  assert.deepEqual(parseAdminStatus({account_id:"a",settings},"a"),settings);
  assert.throws(()=>parseAdminStatus({account_id:"b",settings},"a"));
  for(const invalid of [{...settings,token:"secret"},{...settings,proxy_protocol:"https://secret"},{...settings,proxy_port:70000},{...settings,registered_extensions:-1},{...settings,proxy_enabled:false},{...settings,challenge_provider:"arbitrary"}])assert.throws(()=>parseAdminStatus({account_id:"a",settings:invalid},"a"));
});
test("browser permits read but not remote administrative mutation",()=>{
  const parts=["accounts","alpha","administrative-status"];
  assert.equal(allowedRequest("GET",parts,new URLSearchParams()),true);
  for(const method of ["POST","PUT","DELETE"])assert.equal(allowedRequest(method,parts,new URLSearchParams()),false);
  assert.equal(allowedRequest("GET",parts,new URLSearchParams("secret=true")),false);
});
