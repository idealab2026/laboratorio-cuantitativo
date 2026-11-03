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
 assert.ok(html.includes('data-value="sessions"'));
 assert.ok(html.includes('data-value="operations"'));
 assert.ok(html.includes('id="audit-panel-operations"'));
 const operationTab=renderOperationsAudit(doc,"IL-038","AAPL",{tab:"operations",sort:"pnl",desc:true});
 assert.ok(operationTab.includes('id="audit-panel-operations" role="tabpanel"'));
 assert.ok(operationTab.includes("Precio de compra"));
 assert.ok(operationTab.includes("Precio de venta"));
 assert.ok(operationTab.includes("Rentabilidad %"));
 assert.ok(operationTab.includes("P/L total"));
 assert.ok(operationTab.includes("Dinero empleado en compra"));
 assert.ok(operationTab.includes("Nº acciones compradas"));
 assert.ok(operationTab.includes("VENTA · CERRADA"));
 assert.ok(operationTab.includes("2,00 %"));
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
 assert.ok(site.includes('renderOperationsAudit(state.operationsAudit,id,state.auditTicker,'));
 assert.ok(site.includes('fetch("./data/operations-audit.json"'));
 assert.ok(site.includes('verifyOperationsAudit(document)'));
 assert.ok(site.includes('if(el.id==="audit-ticker")'));
 assert.ok(workflow.includes("python3 scripts/build_operations_audit.py --output dist/data/operations-audit.json"));
 assert.ok(workflow.includes("node --check src/operations-audit.mjs"));
});


test("Market closing-price blue dots are explicitly distinguished from executed buy/sell orders",()=>{
 const src=readFileSync(new URL("../src/operations-audit.mjs",import.meta.url),"utf8");
 assert.ok(src.includes("Precio de cierre del mercado (no es una operación)"));
 assert.ok(src.includes("Los puntos azules son cierres observados de mercado, NO compras ni ventas del algoritmo."));
 assert.ok(src.includes("audit-legend-buy"));
 assert.ok(src.includes("audit-legend-sell"));
 assert.ok(src.includes("audit-close-dot"));
});


test("Every execution and retained market close shows its real price over the marker",async()=>{
 const {layoutAuditPriceLabels,renderOperationsAudit}=await import("../src/operations-audit.mjs");
 const observations=[
  {date:"2026-10-15",kind:"buy",price:104.57,x:60,y:139},
  {date:"2026-10-15",kind:"close",price:104.70,x:60,y:137},
  {date:"2026-10-16",kind:"close",price:104.82,x:100,y:131},
  {date:"2026-10-20",kind:"close",price:102.34,x:285,y:195},
  {date:"2026-10-27",kind:"sell",price:108.61,x:690,y:105},
  {date:"2026-10-27",kind:"close",price:108.72,x:690,y:103},
  {date:"2026-11-02",kind:"close",price:111.52,x:870,y:75}
 ];
 const labels=layoutAuditPriceLabels(observations);
 assert.equal(labels.length,observations.length,"Do not omit any real price");
 assert.equal(labels.filter(x=>x.kind==="buy").length,1);
 assert.equal(labels.filter(x=>x.kind==="sell").length,1);
 assert.equal(labels.filter(x=>x.kind==="close").length,5);
 assert.ok(labels.some(x=>x.text.includes("Compra")&&x.text.includes("104,57")));
 assert.ok(labels.some(x=>x.text.includes("Venta")&&x.text.includes("108,61")));
 assert.ok(labels.some(x=>x.kind==="close"&&x.text.includes("111,52")));
 for(const label of labels){
  assert.ok(label.y>=43&&label.y<=220);
  assert.ok(label.rect.left>=54&&label.rect.right<=885,"Price label inside SVG chart");
  const original=observations.find(x=>x.kind===label.kind&&x.price===label.price);
  assert.ok(original);
  assert.ok(label.y<original.y,"Displayed price must sit ABOVE its data point");
 }
 for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){
  const a=labels[i].rect,b=labels[j].rect;
  const overlap=a.left<b.right+3&&a.right>b.left-3&&a.top<b.bottom+2&&a.bottom>b.top-2;
  assert.equal(overlap,false,"Price callouts must not obscure each other");
 }
 const empty={schema:"midas_operations_audit_v1",purpose:"read_only_paper_decision_evidence",
  asof:"2026-11-02",tracks:Object.fromEntries(Array.from({length:64},(_,i)=>[
   "IL-"+String(i+1).padStart(3,"0"),
   {source_id:"test",status:"no_executed_actions_documented",
    source_path:null,source_sha256:null,currency:"USD",sessions:[],prices:{}}
  ]))};
 empty.tracks["IL-038"]={
  source_id:"capital_cycle_inflection_2026",status:"partial_executions_documented",
  source_path:"capital_cycle_state/ledger.json",source_sha256:"a".repeat(64),
  currency:"USD",sessions:[{date:"2026-10-15",actions:[
   {ticker:"ABT",side:"buy",price:104.57,quantity:5,reason:"Motivo registrado.",
    reason_basis:"recorded",evidence:"capital_cycle_state/ledger.json",signal_date:null}
  ]}],prices:{ABT:[{date:"2026-10-15",price:104.7,source:"dated_market_close",
   snapshot_sha256:"a".repeat(64)}]}
 };
 const html=renderOperationsAudit(empty,"IL-038","ABT");
 assert.ok(html.includes("audit-price-buy"));
 assert.ok(html.includes("audit-price-close"));
 assert.ok(html.includes("Compra 104,57"));
 assert.ok(html.includes("104,7"));
 assert.ok(html.includes("Si no hay punto rojo, no consta una venta"));
 assert.ok(!html.includes("audit-sell-dot"));
});


test("Shares and market close are shown for a held ABT without claiming a new fill",async()=>{
 const {verifyOperationsAudit,renderOperationsAudit}=await import("../src/operations-audit.mjs");
 const sha="a".repeat(64);
 const tracks=Object.fromEntries(Array.from({length:64},(_,i)=>[
  "IL-"+String(i+1).padStart(3,"0"),
  {source_id:"test",status:"no_executed_actions_documented",source_path:null,
   source_sha256:null,currency:"USD",sessions:[],prices:{}}
 ]));
 tracks["IL-012"]={
  source_id:"classic_sp500_genetic_frozen",status:"partial_executions_documented",
  source_path:"classic_sp500_state/ledger.json",source_sha256:sha,currency:"USD",
  sessions:[
   {date:"2026-10-15",actions:[{ticker:"ABT",side:"buy",price:105.0525,quantity:112.925792,
     reason:"Entrada desde regla genética congelada; señal exacta no registrada.",
     reason_basis:"engine_rule",signal_date:null,evidence:"classic_sp500_state/ledger.json",
     rule_source:"classic_sp500/run.py"}]},
   {date:"2026-11-02",actions:[{ticker:"ABT",side:"hold",price:null,quantity:112.925792,
     entry_price:105.0525,entry_date:"2026-10-15",reference_close:110.16000366,
     reference_sha256:sha,reason:"Reglas genéticas congeladas, stop vigente y objetivo vigente; posición inferida.",
     reason_basis:"inferred_position_continuity",signal_date:null,
     evidence:"classic_sp500_state/ledger.json",rule_source:"classic_sp500/run.py"}]}
  ],
  prices:{ABT:[{date:"2026-10-27",price:103.10,source:"dated_market_close",snapshot_sha256:sha},
   {date:"2026-11-02",price:110.16,source:"dated_market_close",snapshot_sha256:sha}]}
 };
 const doc={schema:"midas_operations_audit_v1",purpose:"read_only_paper_decision_evidence",
            asof:"2026-11-02",tracks};
 assert.deepEqual(verifyOperationsAudit(doc),{count:64,withExecution:1});
 const html=renderOperationsAudit(doc,"IL-012","ABT");
 assert.ok(html.includes("112,925792"),"Real shares displayed for hold");
 assert.ok(html.includes("110,16"),"Actual November close displayed");
 assert.ok(html.includes("105,053"),"Executed entry price retained separately");
 assert.ok(html.includes("Cierre de mercado de esta sesión (no es precio de orden)"));
 assert.ok(html.includes("Reglas genéticas congeladas"));
 assert.ok(html.includes("audit-buy-guide"));
 assert.ok(html.includes("audit-unobserved-gap"));
 assert.ok(html.includes("Sin cierres de mercado archivados"));
 assert.ok(html.includes("audit-buy-dot"));
 assert.ok(!html.includes("audit-sell-dot"));
});


test("KVUE entry survives corporate conversion and displays at price/date on chart, without fictitious sale",async()=>{
 const {verifyOperationsAudit,renderOperationsAudit}=await import("../src/operations-audit.mjs");
 const sha="a".repeat(64),source="classic_sp500_state/ledger.json";
 const tracks=Object.fromEntries(Array.from({length:64},(_,i)=>[
  "IL-"+String(i+1).padStart(3,"0"),
  {source_id:"slot_"+i,status:"no_executed_actions_documented",
   source_path:null,source_sha256:null,currency:"USD",sessions:[],prices:{}}
 ]));
 tracks["IL-012"]={source_id:"classic_sp500_genetic_frozen",
  status:"partial_executions_documented",source_path:source,source_sha256:sha,
  currency:"USD",coverage:{executions:1,priced_executions:1,unpriced_executions:0,corporate_conversions:1},
  sessions:[
   {date:"2026-10-15",actions:[{
     ticker:"KVUE",side:"buy",price:18.389189160346984,quantity:645.114733,
     reason:"Ejecutada por el motor",reason_basis:"engine_rule",price_basis:"corporate_original_entry",
     evidence:source,signal_date:null,rule_source:"classic_sp500/run.py"}]},
   {date:"2026-10-27",actions:[{
     ticker:"KVUE",side:"hold",price:null,quantity:645.114733,
     reason:"Posición mantenida de manera inferida",reason_basis:"inferred_position_continuity",
     evidence:source,signal_date:null}]},
   {date:"2026-11-02",actions:[{
     ticker:"KVUE",side:"corporate_action",price:null,quantity:645.114733,
     reason:"Conversión corporativa KVUE hacia KMB; no es una venta",
     reason_basis:"recorded",price_basis:"not_applicable",evidence:source,signal_date:null,
     successor_ticker:"KMB",successor_quantity:94,receivable_cash:2257.90,
     action_id:"KVUE_KMB_2026-11-02",recorded_at_utc:"2026-11-03T16:28:14+00:00"},
    {ticker:"KMB",side:"hold",price:null,quantity:94,
     reason:"Posición recibida por conversión; no comprada",
     reason_basis:"inferred_position_continuity",evidence:source,signal_date:null}]}
  ],
  prices:{KVUE:[{date:"2026-10-27",price:19.43,source:"dated_market_close",snapshot_sha256:sha},
    {date:"2026-10-30",price:19.31,source:"dated_market_close",snapshot_sha256:sha}]}
 };
 const doc={schema:"midas_operations_audit_v1",purpose:"read_only_paper_decision_evidence",
            asof:"2026-11-02",tracks};
 assert.equal(verifyOperationsAudit(doc).count,64);
 const html=renderOperationsAudit(doc,"IL-012","KVUE");
 for(const phrase of ["Compra 18,389","audit-buy-dot","audit-buy-guide",
    "Conversión → KMB","audit-corporate-marker","CONVERSIÓN CORPORATIVA",
    "KVUE → KMB","2257,90","conversión corporativa",
    "2026-10-15","2026-11-02","1 conversiones corporativas"]){
  assert.ok(html.toLowerCase().includes(phrase.toLowerCase()),"Missing: "+phrase);
 }
 assert.ok(!html.includes("audit-sell-dot"),"Merger is not a sale");
 const invalid=structuredClone(doc);invalid.tracks["IL-012"].sessions[2].actions[0].price=25;
 assert.throws(()=>verifyOperationsAudit(invalid),"Corporate action must never have sell price");
});
test("Every recorded order without recoverable fill price is still visible on its execution date",async()=>{
 const {renderOperationsAudit}=await import("../src/operations-audit.mjs");
 const tracks=Object.fromEntries(Array.from({length:64},(_,i)=>[
  "IL-"+String(i+1).padStart(3,"0"),
  {source_id:"s_"+i,status:"no_executed_actions_documented",
   source_path:null,source_sha256:null,currency:"USD",sessions:[],prices:{}}
 ]));
 tracks["IL-005"]={source_id:"test_ledger",status:"partial_executions_documented",
  source_path:"test/ledger.json",source_sha256:"a".repeat(64),currency:"USD",
  sessions:[{date:"2026-10-08",actions:[
   {ticker:"AAPL",side:"buy",quantity:1,price:null,reason:"Fill recorded; price unavailable",
     reason_basis:"not_recorded",price_basis:"not_recorded",
     evidence:"test/ledger.json",signal_date:null}]}],prices:{AAPL:[]}};
 const doc={schema:"midas_operations_audit_v1",
  purpose:"read_only_paper_decision_evidence",asof:"2026-11-02",tracks};
 const html=renderOperationsAudit(doc,"IL-005","AAPL");
 assert.ok(html.includes("Compra sin precio de mercado"));
 assert.ok(html.includes("2026-10-08"));
 assert.ok(html.includes("1 ejecuciones sin precio original trazable"));
 assert.ok(html.includes("audit-undocumented-guide"));
 assert.ok(!html.includes("audit-buy-dot"),"Unrecorded price must never be assigned a y-coordinate");
});
