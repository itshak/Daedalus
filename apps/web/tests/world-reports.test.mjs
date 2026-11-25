import {test} from "node:test";
import assert from "node:assert/strict";
import {parseWorldReports,parseWorldPage,collectWorldCsv} from "../lib/world-reports.ts";
import {allowedRequest} from "../lib/request-policy.ts";
test("map reports expose only bounded aggregate rows from the selected account",async()=>{
  const rid="a".repeat(24),meta={report_id:rid,completed_at:100,shallow:true,partial:false,island_count:1};
  const inventory={account_id:"a",reports:[meta]};
  assert.deepEqual(parseWorldReports(inventory,"a"),inventory);
  const page={...meta,account_id:"a",offset:0,rows:[[1,2,11,1,2,9,null,12]],next_offset:null};
  assert.equal(parseWorldPage(page,"a",rid,0).rows.length,1);
  assert.throws(()=>parseWorldPage(page,"b",rid,0));
  assert.throws(()=>parseWorldPage({...page,rows:[[1,2,11,1,2,9,null,"private"]]},"a",rid,0));
  assert.throws(()=>parseWorldPage({...page,next_offset:1},"a",rid,0));
  assert.match(await collectWorldCsv(async()=>page,"a",rid),/1,2,11,1,2,9,,12/);
  assert.equal(allowedRequest("GET",["accounts","a","world-reports",rid],new URLSearchParams("offset=0")),true);
  assert.equal(allowedRequest("GET",["accounts","a","world-reports",rid],new URLSearchParams("offset=10202")),false);
  assert.equal(allowedRequest("POST",["accounts","a","world-reports"],new URLSearchParams()),false);
});
