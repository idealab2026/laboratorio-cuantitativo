import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {renderThesisReport,verifyFullReports} from "../src/thesis-report.mjs";

const theses=JSON.parse(readFileSync(new URL("../data/public-theses.json",import.meta.url),"utf8"));
const published=JSON.parse(readFileSync(new URL("../data/thesis-reports.json",import.meta.url),"utf8"));
const allowed=new Set(theses.records.map(r=>r.ticker));
const full=verifyFullReports(published,allowed);

test("Canonical website has 25 same-layout thesis routes with exactly 5 full research documents",()=>{
 assert.equal(theses.records.length,25);
 assert.deepEqual([...full.keys()].sort(),["ADBE","CAT","META","MSFT","PLTR"]);
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.match(site,/renderThesisReport\(state\.publicTheses\.get\(ticker\),state\.fullReports\.get\(ticker\)\|\|null\)/);
 assert.match(site,/midas-thesis-mode/);
 assert.match(site,/verifyFullReports\(await full\.json\(\)/);
 for(const row of theses.records){
  const html=renderThesisReport(row,full.get(row.ticker)||null);
  assert.equal((html.match(/class="thesis-report-section"/g)||[]).length,8);
  assert.ok(html.includes('href="./reports/'+row.ticker+'.pdf"'));
  assert.ok(html.includes('target="_blank" rel="noopener noreferrer"'));
  assert.ok(html.includes("Valoración y escenarios"));
  assert.ok(html.includes("IDEA LAB / MIDAS"));
  if(full.has(row.ticker)){
   assert.match(html,/EDICIÓN WEB ÍNTEGRA/);
   assert.ok(html.length>7000);
  }else{
   assert.match(html,/FICHA DOCUMENTAL/);
   assert.match(html,/no está disponible en la edición pública/);
  }
 }
});

test("Canonical report content contains no private URLs or emails",()=>{
 for(const [ticker,doc] of full){
  assert.match(ticker,/^[A-Z0-9.]+$/);
  assert.equal(doc.publication_gate,"approved");
  assert.ok(doc.source_text.length>8000);
  assert.doesNotMatch(doc.source_text,/https?:\/\/|personal_[a-z0-9_]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/i);
 }
 assert.throws(()=>verifyFullReports({schema:published.schema,reports:[{
  ticker:"MSFT",publication_gate:"approved",source_text:"A".repeat(600)+" https://docs.google.com"
 }]},allowed));
});

test("Thesis charts and prices are derived only from historical public records",()=>{
 const r=theses.records.find(x=>x.ticker==="MSFT");
 const html=renderThesisReport(r,full.get("MSFT"));
 assert.match(html,/503,14/);
 assert.match(html,/250,15/);
 assert.match(html,/213,61/);
 assert.match(html,/1.001,88/);
 assert.match(html,/thesis-scenarios-chart/);
 assert.match(html,/2026-10-13/);
 assert.match(html,/Umbrales de entrada/);
});

test("View styling and Pages build always publish both web and PDF reports",()=>{
 const css=readFileSync(new URL("../src/thesis-report.css",import.meta.url),"utf8");
 assert.ok(css.includes("body.midas-thesis-mode .research-hero{display:none}"));
 assert.ok(css.includes("@media print"));
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 assert.ok(html.includes('href="./src/thesis-report.css'));
 const build=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(build.includes("build_thesis_pdfs.py"));
 assert.ok(build.includes("src/thesis-report.mjs"));
 assert.ok(build.includes("data/thesis-reports.json"));
 assert.ok(build.includes("dist/reports"));
});


test("Canonical research documents restore typographic hierarchy, tables and bullet lists",async()=>{
 const {renderCanonicalSource}=await import("../src/thesis-insights.mjs");
 const records=new Map(published.reports.map(x=>[x.ticker,x]));
 const msft=renderCanonicalSource(records.get("MSFT").source_text);
 assert.ok(msft.includes('class="thesis-source-body"'));
 assert.match(msft,/<table class="thesis-source-table">/);
 assert.match(msft,/<caption>FY2031 · tabla del documento original<\/caption>/);
 assert.match(msft,/<td>213,61<\/td>/);
 assert.match(msft,/class="thesis-source-heading">1\. Resumen ejecutivo de inversión<\/h3>/);
 assert.doesNotMatch(msft,/<span class="thesis-line-break">/);
 const meta=renderCanonicalSource(records.get("META").source_text);
 assert.match(meta,/Ficha de parámetros del informe original/);
 assert.match(meta,/META \| FY2031 \| ESCENARIOS ECONÓMICOS/);
 assert.match(meta,/<td>724,29 USD/);
 const pltr=renderCanonicalSource(records.get("PLTR").source_text);
 assert.match(pltr,/<ul class="thesis-source-list">/);
 assert.match(pltr,/<li>U\.S\. Commercial/);
 const cat=renderCanonicalSource(records.get("CAT").source_text);
 assert.match(cat,/negocio industrial de calidad/);
 const escaped=renderCanonicalSource("1. CABECERA\n<script>alert('x')</script>");
 assert.ok(!escaped.includes("<script>"));
 assert.match(escaped,/&lt;script&gt;/);
});
test("Explainers use only dated thesis data and clearly label interpolation, not live markets",async()=>{
 const {renderExplanatoryCharts}=await import("../src/thesis-insights.mjs");
 const msft=theses.records.find(x=>x.ticker==="MSFT");
 const graphic=renderExplanatoryCharts(msft);
 assert.equal((graphic.match(/class="thesis-insight-card/g)||[]).length,3);
 assert.equal((graphic.match(/class="thesis-explainer-svg"/g)||[]).length,3);
 assert.match(graphic,/2026–2031/);
 assert.match(graphic,/Evolución ilustrativa/);
 assert.match(graphic,/Rentabilidad total del periodo/);
 assert.match(graphic,/Disciplina de entrada/);
 assert.match(graphic,/526,30/);
 assert.match(graphic,/250,15/);
 assert.match(graphic,/52,47 %/);
 assert.match(graphic,/No es una cotización actual/);
 assert.doesNotMatch(graphic,/NaN|Infinity|undefined/);
 const full=renderThesisReport(msft,new Map(published.reports.map(x=>[x.ticker,x])).get("MSFT"));
 assert.ok(full.includes("render")===false||full.includes("thesis-source-body"));
 assert.equal((full.match(/class="thesis-explainer-svg"/g)||[]).length,3);
 const lacking=renderExplanatoryCharts({ticker:"TEST",referencePrice:null,bearTarget:null,baseTarget:null,bullTarget:null});
 assert.match(lacking,/No hay escenarios fechados/);
});
