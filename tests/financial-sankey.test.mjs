import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyFinancialSankeys,renderFinancialSankey} from "../src/financial-sankey.mjs";
import {renderThesisReport} from "../src/thesis-report.mjs";

const doc=JSON.parse(readFileSync(new URL("../data/financial-sankeys.json",import.meta.url),"utf8"));
const thesis=JSON.parse(readFileSync(new URL("../data/public-theses.json",import.meta.url),"utf8"));
const map=verifyFinancialSankeys(doc,new Set(thesis.records.map(x=>x.ticker)));

test("Every MIDAS company has a traceable audited/official Sankey slot",()=>{
 assert.equal(map.size,25);
 const verified=[...map.values()].filter(c=>c.periods.length).map(c=>c.ticker).sort();
 assert.deepEqual(verified,["ADBE","AMZN","CAT","META","MSFT","NFLX","PLTR"]);
 assert.equal([...map.values()].filter(c=>c.status==="awaiting_official_statement").length,18);
 for(const company of map.values()){
  const out=renderFinancialSankey(company);
  if(company.periods.length){
   assert.match(out,/<svg role="img"/);
   assert.match(out,/Conciliación exacta del resultado operativo/);
   assert.match(out,/Documento oficial/);
   assert.doesNotMatch(out,/(?:NaN|Infinity|undefined|href="http:)/);
   for(const period of company.periods){
    const total=period.expenses.reduce((s,x)=>s+x.value,0)+period.operating_income;
    assert.ok(Math.abs(total-period.revenue)<=.006,company.ticker);
    assert.ok(period.source.url.startsWith("https://"));
   }
  }else{
   assert.match(out,/Desglose oficial pendiente de verificar/);
   assert.doesNotMatch(out,/<svg/);
  }
 }
});

test("Annual and quarterly periods stay separate, and no prices or estimates enter flows",()=>{
 const m=map.get("MSFT");
 const latest=renderFinancialSankey(m);
 assert.match(latest,/Q1 FY2027/);
 assert.match(latest,/92\.279 M USD/);
 assert.match(latest,/45\.915 M USD/);
 assert.match(latest,/financial-sankey-period/);
 const annual=renderFinancialSankey(m,"2026FY");
 assert.match(annual,/FY2026/);
 assert.match(annual,/331\.839 M USD/);
 assert.match(annual,/155\.237 M USD/);
 assert.match(annual,/No mezclar con flujos de caja ni con CAGR de las tesis/);
 const small=map.get("PLTR");
 assert.match(renderFinancialSankey(small),/1\.414,015 M USD/);
 assert.match(renderFinancialSankey(map.get("META")) ,/cargo judicial extraordinario/);
});

test("Wrong issuer, bad source, negative expense and nonreconciling figures fail closed",()=>{
 const copy=structuredClone(doc);copy.companies[0].periods[0].operating_income++;
 assert.throws(()=>verifyFinancialSankeys(copy,new Set(thesis.records.map(x=>x.ticker))),/Descuadre/);
 const wrong=structuredClone(doc);wrong.companies[0].ticker="FAKE";
 assert.throws(()=>verifyFinancialSankeys(wrong,new Set(thesis.records.map(x=>x.ticker))));
 const bad=structuredClone(doc);bad.companies[0].periods[0].source.url="https://random.example.com/123";
 assert.throws(()=>verifyFinancialSankeys(bad,new Set(thesis.records.map(x=>x.ticker))));
 const badOther=structuredClone(doc);badOther.companies[0].periods[0].expenses[0].value=-1;
 assert.throws(()=>verifyFinancialSankeys(badOther,new Set(thesis.records.map(x=>x.ticker))));
});

test("All reports display the same finance chapter, and no missing issuer gets fake numbers",()=>{
 for(const record of thesis.records){
  const html=renderThesisReport(record,null,map.get(record.ticker));
  assert.equal((html.match(/class="thesis-report-section"/g)||[]).length,9);
  assert.match(html,/id="report-financial"/);
  if(!map.get(record.ticker).periods.length)assert.match(html,/Desglose oficial pendiente/);
  else assert.match(html,/financial-sankey-canvas/);
 }
 const page=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.match(page,/state\.financialSankeys=verifyFinancialSankeys/);
 assert.match(page,/financial-sankey-period/);
 assert.match(page,/financialPeriodByTicker\.set/);
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 assert.match(html,/financial-sankey\.css/);
 const workflow=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.match(workflow,/data\/financial-sankeys\.json/);
 assert.match(workflow,/src\/financial-sankey\.mjs/);
});
