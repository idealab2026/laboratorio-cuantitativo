import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyFullRoster,filterRoster} from "../src/competition-roster.mjs";

const doc=JSON.parse(readFileSync(new URL("../data/competition-roster.json",import.meta.url),"utf8"));
test("Institutional full-coverage manifest has exactly 64 independent functional slots",()=>{
 const result=verifyFullRoster(doc);
 assert.equal(result.count,64);
 assert.equal(result.groups.length,12);
 assert.equal(result.migrated,0);
 assert.equal(result.withReturns,0);
 assert.deepEqual(result.groups.map(x=>x.count).sort((a,b)=>a-b),[1,1,1,1,2,2,4,9,9,9,9,16]);
 assert.equal(new Set(doc.entries.map(x=>x.slot)).size,64);
 assert.ok(doc.entries.every(x=>x.record_status==="not_migrated"&&x.last_equity===null&&x.history.length===0));
});
test("Functional roster filters both by group and strategy query",()=>{
 const first=doc.entries[0];
 assert.equal(filterRoster(doc,{group:first.group}).length,9);
 assert.equal(filterRoster(doc,{query:first.name}).length>=1,true);
 assert.equal(filterRoster(doc,{query:"inexistente"}).length,0);
});
test("Unmigrated strategy cannot report fabricated profits, timestamps or exposure",()=>{
 for(const edit of [
   x=>x.entries[0].return_pct=12.5,
   x=>x.entries[0].activity="active",
   x=>x.entries[0].last_session="2026-10-30",
   x=>x.entries[0].positions=1,
   x=>x.entries[0].comparison.eligible=true,
   x=>x.entries[0].risk.volatility_pct=10,
   x=>x.entries[0].history=[{session:"2026-10-30",nav:120000}],
   x=>x.entries.pop(),
   x=>x.entries[1].slot=x.entries[0].slot,
   x=>x.data_class="paper_trading_real",
   x=>x.entries[0].record_status="verified_institutional"
 ]){
  const changed=structuredClone(doc);edit(changed);
  assert.throws(()=>verifyFullRoster(changed));
 }
});
test("The 64-row UI is distinct from the existing synthetic competitions",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 const workflow=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(site.includes("function full(){"));
 assert.ok(site.includes('fetch("./data/competition-roster.json"'));
 assert.ok(site.includes('full-group-select'));
 assert.ok(site.includes('full-export'));
 assert.ok(site.includes("Sin evidencia comparable"));
 assert.ok(html.includes('data-view="full"'));
 assert.ok(workflow.includes("data/competition-roster.json data/institutional-paper-feed.json dist/data/"));
 assert.ok(site.includes("function paperAccountingView(){"));
});

test("Academic origin labels are absent from institutional public output",()=>{
 const groups=new Set(doc.entries.map(x=>x.group));
 assert.ok(groups.has("Selección multicriterio · riesgo"));
 assert.ok(groups.has("Predicción cuantitativa · cuatro enfoques"));
 const readme=readFileSync(new URL("../README.md",import.meta.url),"utf8");
 const manifest=readFileSync(new URL("../data/competition-roster.json",import.meta.url),"utf8");
 const originPattern=/\bTF[GM]\b|\bpersonal_[a-z0-9_]+\b|\bsegundo[\s_-]+cerebro\b|\bmamg[0-9]{2}\b/i;
 assert.doesNotMatch(readme,originPattern);
 assert.doesNotMatch(manifest,originPattern);
});
