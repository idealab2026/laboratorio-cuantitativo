import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyFullRoster,filterRoster,technicalStage,technicalCoverage,verifyStrategyCandidates,filterStrategyCandidates,FULL_SORT_KEYS,sortFullCompetitionRows} from "../src/competition-roster.mjs";

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
 assert.ok(html.includes('data-view="competition"'));
 assert.ok(site.includes("function competition(){return full();}"));
 assert.ok(workflow.includes("data/competition-roster.json data/strategy-candidates.json data/institutional-paper-feed.json dist/data/"));
 assert.ok(site.includes("function paperAccountingView(){"));
});

test("Academic origin labels are absent from institutional public output",()=>{
 const groups=new Set(doc.entries.map(x=>x.group));
 assert.ok(groups.has("Selección multicriterio · riesgo"));
 assert.ok(groups.has("Predicción cuantitativa · cuatro enfoques"));
 const readme=readFileSync(new URL("../README.md",import.meta.url),"utf8");
 const manifest=readFileSync(new URL("../data/competition-roster.json",import.meta.url),"utf8");
 const originPattern=/\bTF[GM]\b|\bpersonal_[a-z0-9_]+\b/i;
 assert.doesNotMatch(readme,originPattern);
 assert.doesNotMatch(manifest,originPattern);
});

test("Readiness taxonomy counts only code and never declares economic activity",()=>{
 const counts=technicalCoverage(doc);
 assert.deepEqual(counts,{book_unstarted:13,signal_contract:9,pending:42});
 for(const row of doc.entries){
  const stage=technicalStage(row.slot);
  assert.ok(["book_unstarted","signal_contract","pending"].includes(stage.id));
  assert.equal(row.record_status,"not_migrated");
  assert.equal(row.return_pct,null);
 }
 assert.equal(technicalStage("IL-001").id,"book_unstarted");
 assert.equal(technicalStage("IL-010").id,"book_unstarted");
 assert.equal(technicalStage("IL-038").id,"book_unstarted");
 assert.equal(technicalStage("IL-019").id,"signal_contract");
 assert.equal(technicalStage("IL-027").id,"signal_contract");
 assert.equal(technicalStage("IL-045").id,"pending");
 assert.throws(()=>technicalStage("IL-999"));
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(!site.includes("Preparación del motor institucional nuevo:"));
 assert.ok(site.includes("originalStrategyName(item)"));
 assert.ok(site.includes("technicalStage(id).label"));
 assert.ok(site.includes('"Fase técnica"'));
});

test("Satellite Alternative Data registers as research-only 65th candidate, not a 65th signed paper slot",()=>{
 const candidate=JSON.parse(readFileSync(new URL("../data/strategy-candidates.json",import.meta.url),"utf8"));
 assert.deepEqual(verifyStrategyCandidates(candidate),{candidates:2,registeredPaperSlots:64});
 assert.equal(verifyFullRoster(doc).count,64);
 assert.equal(candidate.candidates[0].ordinal,65);
 assert.equal(candidate.candidates[0].id,"IL-R001");
 assert.equal(candidate.candidates[0].return_pct,null);
 assert.equal(candidate.candidates[1].ordinal,66);
 assert.equal(candidate.candidates[1].id,"IL-R002");
 assert.equal(candidate.candidates[1].return_pct,null);
 assert.equal(filterStrategyCandidates(candidate,{query:"Debate Alpha"}).length,1);
 assert.equal(filterStrategyCandidates(candidate,{query:"satellite"}).length,1);
 assert.equal(filterStrategyCandidates(candidate,{query:"WMT"}).length,1);
 assert.equal(filterStrategyCandidates(candidate,{query:"cacao"}).length,0);
 const tampered=structuredClone(candidate);tampered.candidates[0].return_pct=25;
 assert.throws(()=>verifyStrategyCandidates(tampered));
 const changed=structuredClone(candidate);changed.candidates[0].first_signal_at="2026-11-02";
 assert.throws(()=>verifyStrategyCandidates(changed));
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(site.includes('fetch("./data/strategy-candidates.json"'));
 assert.ok(site.includes("verifyStrategyCandidates(doc)"));
 assert.ok(site.includes("state.strategyCandidates"));
 assert.ok(site.includes('button("Ver detalle","full-detail",id'));
 assert.ok(site.includes("function algorithmFiche(){"));
 const release=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(release.includes("data/strategy-candidates.json data/institutional-paper-feed.json dist/data/"));
});


test("All MIDAS competition headings sort their effective paper records with N/D last",()=>{
 assert.equal(FULL_SORT_KEYS.length,14);
 const rows=[
  {id:"IL-001",name:"A benchmark",group:"Technical",record:{return_pct:-1.4,day_return_pct:0,positions:1,pending_orders:0,last_session:"2026-11-01",risk:{volatility_pct:15,max_drawdown_pct:-3},activity:"Active",currency:"USD",comparison:{eligible:true},history:[{nav:1},{nav:2}]}},
  {id:"IL-002",name:"B strategy",group:"Research",record:{return_pct:8.3,day_return_pct:2.3,positions:0,pending_orders:1,last_session:"2026-11-02",risk:{volatility_pct:22,max_drawdown_pct:-8},activity:"Cash",currency:"EUR",comparison:{eligible:false},history:[{nav:1},{nav:2},{nav:3}]}},
  {id:"IL-003",name:"C pending",group:"Research",record:null},
  {id:"IL-R001",name:"Satellite Alternative Data",group:"Data",record:null,candidate:{status:"PENDIENTE"}}
 ];
 for(const key of FULL_SORT_KEYS){
  for(const ascending of [true,false]){
   const snapshot=structuredClone(rows);
   const sorted=sortFullCompetitionRows(rows,{key,ascending});
   assert.equal(sorted.length,4);
   assert.deepEqual(rows,snapshot,"Comparator must not mutate source records");
   assert.equal(new Set(sorted.map(r=>r.id)).size,4);
  }
 }
 assert.deepEqual(sortFullCompetitionRows(rows,{key:"return",ascending:false}).map(r=>r.id),["IL-002","IL-001","IL-003","IL-R001"]);
 assert.deepEqual(sortFullCompetitionRows(rows,{key:"return",ascending:true}).map(r=>r.id),["IL-001","IL-002","IL-003","IL-R001"]);
 assert.deepEqual(sortFullCompetitionRows(rows,{key:"date",ascending:false}).map(r=>r.id),["IL-002","IL-001","IL-003","IL-R001"]);
 assert.deepEqual(sortFullCompetitionRows(rows,{key:"curve",ascending:false}).map(r=>r.id),["IL-002","IL-001","IL-003","IL-R001"]);
 assert.deepEqual(sortFullCompetitionRows(rows,{key:"positions",ascending:false}).slice(0,2).map(r=>r.id),["IL-001","IL-002"]);
 assert.deepEqual(sortFullCompetitionRows(rows,{key:"comparison",ascending:false}).slice(0,2).map(r=>r.id),["IL-001","IL-002"]);
 assert.throws(()=>sortFullCompetitionRows(rows,{key:"__proto__",ascending:true}));
 assert.throws(()=>sortFullCompetitionRows(rows,{key:"return",ascending:"desc"}));
});
test("Competition uses accessible sortable headers, shares ordering with export and preserves filters",()=>{
 const s=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 for(const label of ["Estrategia / ID","Familia","Actividad","Inicio","Sesiones","Último cierre","Divisa","Rent. acumulada","Rent. día","Drawdown","Comparabilidad","Detalle"]){
  assert.ok(s.includes('"'+label+'"'));
 }
 assert.ok(s.includes('data-action="full-column"'));
 assert.ok(s.includes('aria-sort="'));
 assert.ok(s.includes('sortFullCompetitionRows([...existing,...proposals]'));
 assert.ok(s.includes('...sortedFullRosterRows().map('));
 assert.ok(s.includes('document.querySelector("#full-rows")?.closest(".table-scroll")'));
 assert.ok(s.includes('if(e.target.id==="full-query")'));
 assert.ok(s.includes('if(el.id==="full-group-select")'));
});


test("Capital Cycle and Buy The Dip are searchable by their canonical names and mapped to original diaries",async()=>{
 const cycle=doc.entries.find(e=>e.slot==="IL-038"),dip=doc.entries.find(e=>e.slot==="IL-039");
 assert.ok(cycle.name.startsWith("Capital Cycle"));
 assert.ok(dip.name.startsWith("Buy The Dip"));
 assert.deepEqual(filterRoster(doc,{query:"capital cycle"}).map(x=>x.slot),["IL-038"]);
 assert.deepEqual(filterRoster(doc,{query:"buy the dip"}).map(x=>x.slot),["IL-039"]);
 assert.deepEqual(filterRoster(doc,{group:"Ciclo de capital",query:"Capital Cycle"}).map(x=>x.slot),["IL-038"]);
 const mapping=JSON.parse(readFileSync(new URL("../data/original-track-map.json",import.meta.url),"utf8"));
 assert.equal(mapping.capital_cycle_inflection_2026,"IL-038");
 assert.equal(mapping.buy_the_dip_corpus_2026_v0,"IL-039");
 const source=JSON.parse(readFileSync(new URL("../strategy_state/dashboard.json",import.meta.url),"utf8"));
 const {verifyOriginalPaper}=await import("../src/original-paper.mjs");
 const verified=verifyOriginalPaper(source,mapping);
 for(const id of ["IL-038","IL-039"]){
  const record=verified.bySlot.get(id);
  assert.ok(record&&record.history.length>=2, "Mapped original economic history must exist");
  assert.ok(Number.isFinite(record.return_pct));
  assert.match(record.last_session,/^\d{4}-\d{2}-\d{2}$/);
 }
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(site.includes('button("Ver detalle","full-detail",id'));
 assert.ok(site.includes('state.algorithmId=value;go("algorithm")'));
 assert.ok(site.includes('const leader=phase==="active"?paperLeaderboard(phases.active.map('),
  "Only active paper strategies should be eligible as current leader");
 assert.ok(site.includes('const phases=partitionCompetitionRows(d.entries);'));
});


test("All 64 institutional rows preserve the exact journal display names",async()=>{
 const mapping=JSON.parse(readFileSync(new URL("../data/original-track-map.json",import.meta.url),"utf8"));
 const source=JSON.parse(readFileSync(new URL("../strategy_state/dashboard.json",import.meta.url),"utf8"));
 const {verifyOriginalPaper}=await import("../src/original-paper.mjs");
 const original=verifyOriginalPaper(source,mapping);
 assert.equal(original.labels.size,64);
 assert.equal(original.bySlot.size,48); // absent diaries must still retain their original names
 for(const track of source.tracks){
  assert.equal(original.labels.get(mapping[track.id]),track.label);
 }
 assert.equal(original.labels.get("IL-038"),"Capital Cycle Inflection · underinvestment + calidad + giro");
 assert.equal(original.labels.get("IL-039"),"Buy The Dip corpus v0 · deep value + special situations");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(site.includes('state.originalPaper?.labels?.get(item.slot)||item.name'));
 assert.ok(site.includes('name:originalStrategyName(item)'));
 assert.ok(site.includes('originalStrategyName(item)].some('));
 assert.ok(site.includes("full-strategy-name"));
});
test("Responsive competition preserves explicit detail actions and compact mobile cards",()=>{
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(css.includes('.full-competition-table table{table-layout:fixed;width:100%;min-width:0'));
 assert.ok(css.includes('.paper-leader{'));
 assert.ok(css.includes('.algorithm-profile{'));
 assert.ok(css.includes('.detail-cell{'));
 assert.ok(css.includes('@media(max-width:1050px)'));
 assert.ok(css.includes('.full-competition-table .competition-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))'));
 assert.ok(css.includes('.full-competition-table .competition-row td:before'));
 assert.ok(site.includes('FULL_COMPETITION_COLUMNS=['));
 assert.ok(site.includes('function fullMobileSortControls()'));
 assert.ok(site.includes("data-label="));
 assert.ok(site.includes('if(el.id==="full-mobile-sort")'));
 assert.ok(site.includes('else if(action==="full-sort-direction")'));
 const keys=["Estrategia","Familia","Actividad","Inicio","Sesiones","Último cierre","Divisa","Rent. acumulada","Rent. día","Drawdown","Comparabilidad","Detalle"];
 for(const key of keys)assert.ok(site.includes('"'+key+'"'));
});


test("Competition removes the entire filter/export/explanatory toolbar without hiding paper records",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const begin=src.indexOf("function full(){"),end=src.indexOf("function fullHistoryChart(",begin);
 assert.ok(begin>=0&&end>begin);
 const competition=src.slice(begin,end);
 for(const removed of ["competition-filters","full-group-select","full-query","Exportar CSV","competition-disclaimer","full-count","Orden inicial: mayor rentabilidad acumulada"]){
  assert.ok(!competition.includes(removed),"Unwanted introductory block: "+removed);
 }
 assert.ok(competition.includes("fullRosterRows()"));
 assert.ok(competition.includes("fullRosterHeaders()"));
 assert.ok(competition.includes("fullMobileSortControls()"));
 assert.ok(competition.includes("paperLeaderboard("));
});
test("Competition displays No verificable for missing cells, keeping the numeric sort as missing",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const a=src.indexOf("function compactCell("),b=src.indexOf("function sortedFullRosterRows(",a);
 const cells=src.slice(a,b);
 assert.ok(cells.includes('html==="N/D"'));
 assert.ok(cells.includes('class="unverified-text">No verificable'));
 const full=src.slice(src.indexOf("function fullRosterRows(){"),src.indexOf("function full(){"));
 assert.ok(full.includes("finite(record.day_return_pct)"));
 assert.ok(full.includes("finite(risk.max_drawdown_pct)"));
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 assert.ok(css.includes(".full-competition-table .unverified-text"));
 assert.ok(css.includes("white-space:normal"));
});
test("Comparability explanation opens on hover, keyboard focus and in mobile sort controls",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 for(const term of ["mismo grupo de comparación","universo","divisa","costes","No comparable","Archivo","Investigación"]){
  assert.ok(src.toLocaleLowerCase("es").includes(term.toLocaleLowerCase("es")));
 }
 assert.ok(src.includes('role="tooltip"'));
 assert.ok(src.includes("aria-describedby="));
 assert.ok(src.includes('key==="comparison"?comparabilityHelp('));
 assert.ok(src.includes('comparabilityHelp("competition-comparability-tip-mobile")'));
 assert.ok(css.includes(".comparison-help-wrap:hover .comparison-help-popup"));
 assert.ok(css.includes(".comparison-help-wrap:focus-within .comparison-help-popup"));
 assert.ok(css.includes(".comparison-header:hover .comparison-help-popup"));
 assert.ok(css.includes(".full-competition-table{overflow:visible}"));
});
