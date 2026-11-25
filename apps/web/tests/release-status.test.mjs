import {test} from "node:test";
import assert from "node:assert/strict";
import {parseReleaseStatus} from "../lib/release-status.ts";
import {allowedRequest} from "../lib/request-policy.ts";
test("release metadata accepts only exact published project asset links",()=>{
  const tag="desktop-preview-"+"a".repeat(12),base="https://github.com/itshak/Daedalus/releases";
  const result={controller_version:"0.1.0a0",controller_revision:null,catalog_status:"available",preview:{
    tag,revision_prefix:tag.slice(-12),published_at:"2026-11-25T00:00:00Z",notarization:"unnotarized_preview",
    release_url:base+"/tag/"+tag,dmg_url:base+"/download/"+tag+"/Daedalus-macos-preview.dmg",
    checksum_url:base+"/download/"+tag+"/Daedalus-macos-preview.dmg.sha256"}};
  assert.deepEqual(parseReleaseStatus(result),result);
  assert.throws(()=>parseReleaseStatus({...result,preview:{...result.preview,dmg_url:"https://example.invalid/installer"}}));
  assert.equal(allowedRequest("GET",["release-status"],new URLSearchParams()),true);
  assert.equal(allowedRequest("POST",["release-status"],new URLSearchParams()),false);
});
