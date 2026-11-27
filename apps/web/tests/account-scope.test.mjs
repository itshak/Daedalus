import test from "node:test";
import assert from "node:assert/strict";
import {parseScope,scopedAccounts,reconcileScope,eligibleTarget} from "../lib/account-scope.ts";
const rows=[{id:"a",player:"same"},{id:"b",player:"same"},{id:"c",enabled:false}];
test("all, explicit one/multiple/empty use IDs, not nicknames",()=>{
  assert.deepEqual(scopedAccounts(rows,parseScope(null)),rows);
  for(const ids of [["b"],["a","b"],[]]){
    const scope=parseScope(JSON.stringify({mode:"explicit",ids}));
    assert.deepEqual(scopedAccounts(rows,scope).map(a=>a.id),ids);
    assert.deepEqual(parseScope(JSON.stringify(scope)),scope);
  }
});
test("deleted/unauthorized IDs never broaden an explicit scope",()=>{
  assert.deepEqual(reconcileScope({mode:"explicit",ids:["b"]},["a"]),{mode:"explicit",ids:[]});
  assert.deepEqual(parseScope("broken"),{mode:"explicit",ids:[]});
  assert.deepEqual(parseScope('{"mode":"explicit","ids":["a","a"]}'),{mode:"explicit",ids:["a"]});
});
test("single eligible target is automatic; invalid target never broadens",()=>{
  assert.equal(eligibleTarget(["a"],"b"),"a");
  assert.equal(eligibleTarget(["a","b"],"c"),"");
  assert.equal(eligibleTarget([],"a"),"");
  assert.equal(eligibleTarget(["a","b"],"b"),"b");
});
