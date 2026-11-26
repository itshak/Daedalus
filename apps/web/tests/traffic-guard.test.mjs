import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {TrafficGuard} from "../lib/traffic-guard.ts";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("traffic guard isolates keys and expires bounded counters",()=>{
 let now=1000;const guard=new TrafficGuard(()=>now);
 assert.ok(guard.allow("a",2,60_000));assert.ok(guard.allow("a",2,60_000));assert.equal(guard.allow("a",2,60_000),false);
 assert.ok(guard.allow("b",1,60_000));now+=60_000;assert.ok(guard.allow("a",2,60_000));
});
test("web login goes through same-origin server and sets HttpOnly session cookies",()=>{
 assert.doesNotMatch(read("app/login/page.tsx"),/createBrowserClient/);
 assert.match(read("app/login/page.tsx"),/fetch\("\/api\/login"/);
 assert.match(read("lib/supabase.ts"),/httpOnly: true/);
 assert.match(read("app/api/login/route.ts"),/request.headers.get\("origin"\)/);
 assert.match(read("app/api/login/route.ts"),/\{signedIn:true\}/);
 assert.match(read("next.config.ts"),/frame-ancestors 'none'/);
});
