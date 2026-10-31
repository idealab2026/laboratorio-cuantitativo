import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyIssuerCatalog,filterIssuers} from "../src/catalog.mjs";

const catalog=JSON.parse(readFileSync(new URL("../data/universe.json",import.meta.url),"utf8"));

test("Public catalogue contains 25 issuer-only entries",()=>{
 assert.equal(verifyIssuerCatalog(catalog),true);
 assert.equal(catalog.issuers.length,25);
 for(const ticker of ["MSFT","META","ADBE","PLTR","AMZN","CAT","NET"]){
  assert.ok(catalog.issuers.some(i=>i.ticker===ticker));
 }
});
test("No prices, investment targets, return forecasts, direct reports or private links are published",()=>{
 const text=JSON.stringify(catalog);
 assert.doesNotMatch(text,/https?:\/\//);
 for(const i of catalog.issuers){
  for(const f of ["price","priceAsOf","bearCagr","baseCagr","bullCagr","bearTarget","baseTarget","bullTarget","buyPrice15","nextEarnings","reportUrl"]){
   assert.equal(i[f],null,i.ticker+" "+f);
  }
 }
});
test("Catalog rejects false public pricing and unreviewed thesis status",()=>{
 const withPrice=structuredClone(catalog);
 withPrice.issuers[0].price=100;
 assert.throws(()=>verifyIssuerCatalog(withPrice),/Unverified financial/);
 const withReport=structuredClone(catalog);
 withReport.issuers[0].reportUrl="https://example.com/private";
 assert.throws(()=>verifyIssuerCatalog(withReport),/Unverified financial/);
 const withStatus=structuredClone(catalog);
 withStatus.issuers[0].status="Completada";
 assert.throws(()=>verifyIssuerCatalog(withStatus),/Unverified editorial/);
});
test("Issuer filtering sorts, searches and avoids duplicates",()=>{
 assert.equal(filterIssuers(catalog).length,25);
 assert.deepEqual(filterIssuers(catalog,"microsoft").map(x=>x.ticker),["MSFT"]);
 assert.ok(filterIssuers(catalog,"ROBÓTICA").length>=2);
 assert.equal(new Set(filterIssuers(catalog).map(x=>x.ticker)).size,25);
});
test("UI distinguishes genuine issuer names from synthetic results with compact activity and sign",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.match(src,/issuerTableRows/);
 assert.match(src,/function syntheticTheses/);
 assert.match(src,/function sparkline/);
 assert.match(src,/perf-positive/);
 assert.match(src,/perf-negative/);
 assert.match(src,/Actividad paper/);
 assert.match(src,/NO_MARKET_FEED|verifyIssuerCatalog/);
});
