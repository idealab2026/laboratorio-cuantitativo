import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyPaperFeed} from "../src/paper-feed.mjs";

const roster=JSON.parse(readFileSync(new URL("../data/competition-roster.json",import.meta.url),"utf8"));
const placeholder=JSON.parse(readFileSync(new URL("../data/institutional-paper-feed.json",import.meta.url),"utf8"));
test("No institutional source means no public NAV, positions or fabricated activity",()=>{
 const result=verifyPaperFeed(placeholder,roster);
 assert.equal(result.status,"not_connected");
 assert.equal(result.count,0);
 assert.equal(result.bySlot.size,0);
});
test("Browser rejects unverified source identity and mismatched NAV",()=>{
 const source={identity:{vendor:"Yahoo Finance",client:"yfinance",market:"XNYS",
  auto_adjust:false,actions:true},session:"2026-10-30",sha256:"a".repeat(64),
  rights_attested:true,requested:504,observed:504,constituents_observed:503,missing:0};
 const line={slot:"IL-010",activity:"active",currency:"USD",first_session:"2026-10-29",
  last_session:"2026-10-30",initial_capital:100000,last_equity:110000,
  return_pct:10,day_return_pct:10,
  risk:{volatility_pct:null,max_drawdown_pct:0,sharpe_0rf:null},
  positions:1,pending_orders:0,source_snapshot_sha256:"a".repeat(64),
  config_sha256:"b".repeat(64),comparison:{eligible:true,universe_id:"us_503_frozen"},
  history:[{date:"2026-10-29",nav:100000},{date:"2026-10-30",nav:110000}]};
 const doc={schema:"idealab_institutional_paper_feed_v1",status:"source_verified",
  producer:"idealab_institutional_core",generated_at_utc:"2026-10-31T18:00:00Z",
  source,tracks:[line],signature:"c".repeat(64)};
 assert.equal(verifyPaperFeed(doc,roster).count,1);
 for(const mutation of [
  d=>d.tracks[0].last_equity=120000,
  d=>d.tracks[0].risk.max_drawdown_pct=-7,
  d=>d.tracks[0].source_snapshot_sha256="d".repeat(64),
  d=>d.source.identity.vendor="Another Feed",
  d=>d.source.rights_attested=false,
  d=>d.tracks[0].slot="IL-999",
  d=>d.tracks[0].history.reverse()
 ]){
  const bad=structuredClone(doc);mutation(bad);
  assert.throws(()=>verifyPaperFeed(bad,roster));
 }
});
test("Registered client viewer differentiates disabled feed from synthetic demo",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 assert.ok(site.includes("loadInstitutionalPaperFeed()"));
 assert.ok(site.includes("institutional-paper-feed.json"));
 assert.ok(site.includes("verifyPaperFeed("));
 assert.ok(site.includes("Sin fuente institucional acreditada"));
 assert.ok(html.includes('data-view="full"'));
 const build=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(build.includes("paper_feed.py --validate"));
});
