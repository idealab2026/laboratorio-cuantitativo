import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {algorithmTheory,paperLeaderboard} from "../src/algorithm-detail.mjs";
import {verifyOriginalPaper} from "../src/original-paper.mjs";
import {sortFullCompetitionRows} from "../src/competition-roster.mjs";

const doc=JSON.parse(readFileSync(new URL("../strategy_state/dashboard.json",import.meta.url),"utf8"));
const mapping=JSON.parse(readFileSync(new URL("../data/original-track-map.json",import.meta.url),"utf8"));
const archive=verifyOriginalPaper(doc,mapping);
const source=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");

test("64 algorithm fiches expose noninvented reference theory and mathematics",()=>{
 assert.equal(doc.tracks.length,64);
 for(const track of doc.tracks){
  const info=algorithmTheory(track.id,track.group);
  for(const field of ["theory","equation","signal","validation","scope"]){
   assert.equal(typeof info[field],"string",track.id+" "+field);
   assert.ok(info[field].length>20,track.id+" "+field);
  }
 }
 for(const [sourceId,expected] of [
  ["buy_the_dip_corpus_2026_v0","buyDip"],
  ["capital_cycle_inflection_2026","capitalCycle"],
  ["classic_sp500_macd_12_26_9","macd"],
  ["classic_sp500_turtle_55_20_long","turtle"],
  ["turtle_short_20_10","turtleShort"],
  ["weekly_ml_lgbm_ranker_2026","lightgbmRank"],
  ["weekly_ml_lstm_2026","lstm"],
  ["timesfm_2p5_daily_eur_paper","timesfm"],
  ["markowitz_weights","markowitz"]
 ])assert.equal(algorithmTheory(sourceId).familyId,expected);
});

test("Leader comes only from validated archived paper NAV and is independently sorted descending",()=>{
 const rows=doc.tracks.map(t=>({
  id:mapping[t.id],name:t.label,record:archive.bySlot.get(mapping[t.id])||null
 }));
 const highest=paperLeaderboard(rows);
 assert.ok(highest);
 assert.equal(highest.record.return_pct,Math.max(...rows.filter(x=>x.record).map(x=>x.record.return_pct)));
 assert.equal(highest.record.session_count,highest.record.history.length);
 assert.equal(highest.record.first_session,highest.record.history[0].date);
 assert.equal(highest.record.last_session,highest.record.history.at(-1).date);
 const ordered=sortFullCompetitionRows(rows,{key:"return",ascending:false});
 assert.equal(ordered[0].id,highest.id);
 assert.equal(ordered.at(-1).record,null);
 assert.equal(paperLeaderboard([{id:"missing",record:null},
  {id:"invalid",record:{return_pct:30,first_session:"",session_count:0}}]),null);
});

test("Original records preserve verified first dates and all sessions, not market calendar estimates",()=>{
 assert.equal(archive.bySlot.size,48);
 for(const record of archive.bySlot.values()){
  assert.match(record.first_session,/^\d{4}-\d{2}-\d{2}$/);
  assert.equal(record.session_count,record.history.length);
  assert.equal(record.first_session,record.history[0].date);
  assert.equal(record.last_session,record.history.at(-1).date);
  assert.ok(record.sourceId);
  assert.ok(record.initial_capital>0);
 }
});

test("One button per row opens a separate algorithm profile instead of inline blocks",()=>{
 for(const expected of [
  'button("Ver detalle","full-detail",id',
  'else if(action==="full-detail")',
  'state.algorithmId=value;go("algorithm")',
  'algorithm:algorithmFiche',
  'function algorithmFiche(){',
  'function fullHistoryChart(points){',
  'function fullRosterRows(){',
  '"start","Inicio"',
  '"sessions","Sesiones"',
  '"return","Rent. acumulada"',
  '"detail","Detalle"',
  'fullRosterSort:"return",fullRosterAsc:false',
  'function go(view){',
  'u.searchParams.set("algorithm",state.algorithmId)',
  'state.algorithmId=new URLSearchParams(location.search).get("algorithm")',
  'Formulación matemática de referencia',
  'Las fechas indicadas corresponden a las sesiones NAV'
 ])assert.ok(source.includes(expected),"Missing public UI contract: "+expected);
 for(const obsolete of [
  '<div class="source-health-strip"><div><span class="label">Funciones registradas',
  'card(\'<h3>Condiciones de publicación de cada diario',
  'button("Capital Cycle · IL-038","full-focus","IL-038"',
  'card(\'<h3>65 · '
 ])assert.equal(source.includes(obsolete),false,"Obsolete block remains");
 assert.equal(html.includes('aria-label="Estadísticas del laboratorio"'),false);
 assert.equal(html.includes('DIARIOS PAPER · CAPITAL VIRTUAL · DATOS HISTÓRICOS DE MERCADO'),false);
});

test("Missing return/session data remains N/D and proposals do not enter the winner board",()=>{
 const sorted=sortFullCompetitionRows([
  {id:"IL-001",name:"A",group:"x",record:{return_pct:-5,first_session:"2026-10-01",session_count:4}},
  {id:"IL-R001",name:"Proposal",group:"x",candidate:{status:"PENDIENTE"},record:null},
  {id:"IL-003",name:"Unavailable",group:"x",record:null}
 ],{key:"return",ascending:false});
 assert.equal(sorted[0].id,"IL-001");
 assert.deepEqual(sorted.slice(1).map(r=>r.id),["IL-003","IL-R001"]);
 assert.equal(paperLeaderboard(sorted).id,"IL-001");
 assert.equal(algorithmTheory("not_a_model").familyId,"general");
});


test("Operation audit documents real fills, inferred holds and dated trade markers without fabricating decisions",async()=>{
 const {verifyOperationsAudit,renderOperationsAudit}=await import("../src/operations-audit.mjs");
 const sha="a".repeat(64);
 const tracks=Object.fromEntries(Array.from({length:64},(_,idx)=>[
  "IL-"+String(idx+1).padStart(3,"0"),
  {source_id:"demo_test_"+idx,status:"no_executed_actions_documented",
   source_path:null,source_sha256:null,currency:"USD",sessions:[],prices:{}}
 ]));
 tracks["IL-038"]={
  source_id:"capital_cycle_inflection_2026",status:"partial_executions_documented",
  source_path:"capital_cycle_state/ledger.json",source_sha256:sha,currency:"USD",
  sessions:[
   {date:"2026-10-01",audit_note:null,actions:[
     {ticker:"AAPL",side:"buy",price:150,quantity:5,
      reason:"Compra vinculada a puntuación de selección documentada.",
      reason_basis:"recorded",signal_date:"2026-09-30",evidence:"capital_cycle_state/ledger.json"}]},
   {date:"2026-10-02",audit_note:null,actions:[
     {ticker:"AAPL",side:"hold",price:null,quantity:null,
      reason:"Posición abierta, sin salida registrada. Mantenimiento inferido.",
      reason_basis:"inferred_position_continuity",signal_date:null,
      evidence:"capital_cycle_state/ledger.json"}]},
   {date:"2026-10-05",audit_note:null,actions:[
     {ticker:"AAPL",side:"sell",price:153,quantity:5,
      reason:"Salida por señal registrada.",
      reason_basis:"recorded",signal_date:"2026-10-02",
      evidence:"capital_cycle_state/ledger.json"}]}
  ],
  prices:{AAPL:[
   {date:"2026-10-01",price:151,source:"dated_market_close",snapshot_sha256:sha},
   {date:"2026-10-02",price:152,source:"dated_market_close",snapshot_sha256:sha}
  ]}
 };
 const doc={schema:"midas_operations_audit_v1",purpose:"read_only_paper_decision_evidence",
            asof:"2026-11-02",tracks};
 assert.deepEqual(verifyOperationsAudit(doc),{count:64,withExecution:1});
 const html=renderOperationsAudit(doc,"IL-038");
 for(const expected of ["Operaciones por sesión","AAPL","COMPRA","VENTA","MANTENER · INFERIDO",
   "Compra vinculada","Mantenimiento inferido","audit-price-chart","audit-buy-dot","audit-sell-dot",
   "2026-10-01","2026-10-05","Ejecuciones","signal"]){} // descriptions tested below
 for(const expected of ["Operaciones por sesión","AAPL","COMPRA","VENTA","MANTENER · INFERIDO",
   "Compra vinculada","Mantenimiento inferido","audit-price-chart","audit-buy-dot","audit-sell-dot",
   "2026-10-01","2026-10-05","Motivo"]){
  assert.ok(html.includes(expected),"Missing audit UI element: "+expected);
 }
 assert.ok(html.includes('id="audit-ticker"'));
 assert.ok(html.includes("Precio (USD)"));
 assert.ok(!html.includes("Cierre 2026-10-05:"));
 const vacant=renderOperationsAudit(doc,"IL-039");
 assert.ok(vacant.includes("Los NAV globales no bastan"));
 assert.throws(()=>verifyOperationsAudit({...doc,tracks:{...tracks,"IL-038":{
  ...tracks["IL-038"],sessions:[{date:"2026-10-01",actions:[{
   ...tracks["IL-038"].sessions[0].actions[0],side:"hold",price:150
  }]}]}}}));
});
test("Strategy profiles append source-driven sessions instead of attributing synthetic orders",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const workflow=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(site.includes('renderOperationsAudit(state.operationsAudit,id,state.auditTicker)'));
 assert.ok(site.includes('fetch("./data/operations-audit.json"'));
 assert.ok(site.includes('verifyOperationsAudit(document)'));
 assert.ok(site.includes('if(el.id==="audit-ticker")'));
 assert.ok(workflow.includes("python3 scripts/build_operations_audit.py --output dist/data/operations-audit.json"));
 assert.ok(workflow.includes("node --check src/operations-audit.mjs"));
});
