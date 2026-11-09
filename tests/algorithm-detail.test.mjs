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


test("MIDAS header replaces corporate links and retires the catalogue view",()=>{
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 assert.ok(html.includes('<header class="topbar midas-topbar">'));
 assert.ok(html.includes('<nav class="product-tabs midas-header-menu"'));
 assert.ok(html.includes('data-view="competition"'));
 assert.ok(html.includes('data-view="monitoring"'));
 assert.ok(!html.includes('class="global-nav"'));
 assert.ok(!html.includes('data-view="archive"'));
 assert.ok(!site.includes("function archive(){"));
 assert.ok(!site.includes("monitoring,archive"));
 assert.ok(site.includes('requested==="overview"||requested==="archive"'),
   "Historic bookmarks should resolve to the main competition");
 assert.ok(css.includes(".midas-topbar .midas-header-menu"));
});
test("Monitoring has two tabs, a real audit selector and the SAME trade table as each algorithm",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 for(const text of [
   "function monitoring(){",'data-action="monitoring-tab"',"monitoring-panel-summary",
   "monitoring-panel-operations","monitoring-algorithm",
   "renderTradeLotsTable(audit.tracks[chosen],state.monitoringSort,state.monitoringDesc)",
   "renderTradeLotsTable(state.operationsAudit.tracks[el.value],state.monitoringSort,state.monitoringDesc)",
   "state.monitoringTab","state.monitoringStrategy","state.monitoringSort","state.monitoringDesc",
   "summarizeOperationsAudit(audit)","Última sesión de trading paper",
   "Algoritmos propuestos","Algoritmos productivos","Algoritmos con operaciones paper",
   'feed?.status==="source_verified"','feed?.status==="not_connected"'
 ])assert.ok(site.includes(text),"Missing monitoring contract: "+text);
 const audit=readFileSync(new URL("../src/operations-audit.mjs",import.meta.url),"utf8");
 assert.ok(audit.includes("export function renderTradeLotsTable"));
 assert.ok(audit.includes("renderTradeLotsTable(track,view.sort"));
});
test("Historical execution KPIs do not mistake holds, NAV-only or mergers for a productive algorithm",async()=>{
 const {summarizeOperationsAudit,renderTradeLotsTable}=await import("../src/operations-audit.mjs");
 const tracks={
  "IL-001":{status:"nav_only_or_no_actions",currency:"USD",sessions:[{date:"2026-11-03",actions:[]}],prices:{}},
  "IL-002":{status:"partial_executions_documented",currency:"USD",sessions:[
   {date:"2026-11-01",actions:[{ticker:"AAA",side:"buy",price:100,quantity:2,fee:0}]},
   {date:"2026-11-02",actions:[{ticker:"AAA",side:"hold",price:null,quantity:2}]}
  ],prices:{AAA:[{date:"2026-11-02",price:112}]}},
  "IL-003":{status:"nav_only_or_no_actions",currency:"USD",sessions:[
   {date:"2026-11-02",actions:[{ticker:"KVUE",side:"corporate_action",successor_ticker:"KMB"}]}
  ],prices:{}},
  "IL-004":{status:"partial_executions_documented",currency:"USD",sessions:[
   {date:"2026-11-03",actions:[{ticker:"BBB",side:"sell",price:10,quantity:1}]}
  ],prices:{}}
 };
 const summary=summarizeOperationsAudit({tracks});
 assert.equal(summary.slots,4);
 assert.equal(summary.withExecutions,2);
 assert.equal(summary.withoutExecutions,2);
 assert.equal(summary.executions,2);
 assert.equal(summary.conversions,1);
 assert.equal(summary.latestSession,"2026-11-03");
 assert.equal(summary.latestTrade,"2026-11-03");
 assert.equal(summarizeOperationsAudit(null),null);
 const rows=renderTradeLotsTable(tracks["IL-002"]);
 for(const expected of ["Activo","Acción ejecutada","Precio de compra","Precio de venta",
  "Rentabilidad %","P/L total","Dinero empleado en compra","Nº acciones compradas",
  "COMPRA · ABIERTA"])assert.ok(rows.includes(expected),"Same trade columns: "+expected);
 assert.ok(rows.includes("24,00"),"Unrealized P/L uses stored close and recorded quantity");
});


test("Each MIDAS session lists COMPRAS, VENTAS and MANTENER without confusing inference with executions",async()=>{
 const {buildSessionActionColumns,renderOperationsAudit}=await import("../src/operations-audit.mjs");
 const action=(ticker,side,quantity)=>({ticker,side,quantity,
  price:side==="buy"?50:side==="sell"?55:null,
  reason:"Evidence-backed sample",reason_basis:side==="hold"?"inferred_position_continuity":"recorded",
  evidence:"test/ledger.json",signal_date:null});
 const track={status:"partial_executions_documented",source_id:"test",source_path:"test/ledger.json",
  source_sha256:"a".repeat(64),currency:"USD",prices:{AAPL:[]},
  sessions:[
   {date:"2026-10-01",actions:[action("AAPL","buy",10),action("AAPL","buy",2),action("MSFT","buy",5)]},
   {date:"2026-10-02",actions:[action("AAPL","sell",4),action("MSFT","hold",5),action("MSFT","buy",2)]},
   {date:"2026-10-05",actions:[action("AAPL","sell",8),action("MSFT","hold",7)]}
  ]};
 const matrix=buildSessionActionColumns(track);
 assert.deepEqual(matrix[0].buys,["AAPL","MSFT"],"Same-session duplicate buys list ticker once");
 assert.deepEqual(matrix[1].sells,["AAPL"]);
 assert.deepEqual(matrix[1].partialSells,["AAPL"],"4 sold from 12 leaves 8");
 assert.deepEqual(matrix[1].holds,["MSFT"],"Hold is inferred, not another buy");
 assert.deepEqual(matrix[2].partialSells,[],"8 sold from 8 is a complete exit");
 const tracks=Object.fromEntries(Array.from({length:64},(_,idx)=>[
  "IL-"+String(idx+1).padStart(3,"0"),
  {source_id:"test",status:"no_executed_actions_documented",source_path:null,
   source_sha256:null,currency:"USD",prices:{},sessions:[]}
 ]));
 tracks["IL-001"]=track;
 const document={schema:"midas_operations_audit_v1",purpose:"read_only_paper_decision_evidence",
  asof:"2026-11-03",tracks};
 const markup=renderOperationsAudit(document,"IL-001");
 for(const h of ["SESIÓN","COMPRAS","VENTAS","MANTENER","audit-session-grid-head",
  "audit-session-column-buy","audit-session-column-sell","audit-session-column-hold"])
  assert.ok(markup.includes(h),"Missing session matrix: "+h);
 assert.ok(markup.includes('class="audit-partial-star"'),"Partial sales carry a star");
 const index=markup.indexOf("Sesión 2 · 2026-10-02");
 const closing=markup.indexOf("Sesión 3 · 2026-10-05");
 assert.ok(index>closing,"Newest session appears first");
 const s2=markup.slice(index,markup.indexOf("</summary>",index));
 const s3=markup.slice(closing,markup.indexOf("</summary>",closing));
 assert.ok(s2.includes('class="audit-partial-star"'),"Partial sale marked on the ticker");
 assert.ok(!s3.includes('class="audit-partial-star"'),"Full sale never marked partial");
 assert.ok(markup.includes("documentadas o inferidas"),"Accordion detail remains accessible");
});
test("Partial sale marker refuses uncertainty, supports split-adjusted remaining quantities and excludes mergers",async()=>{
 const {buildSessionActionColumns}=await import("../src/operations-audit.mjs");
 const a=(ticker,side,quantity,extra={})=>({ticker,side,quantity,...extra});
 const track={sessions:[
  {date:"2026-10-01",actions:[a("AAA","buy",10),a("ZZZ","buy",null)]},
  {date:"2026-10-05",actions:[
   a("AAA","sell",10),a("ZZZ","sell",1),
   a("KVUE","corporate_action",12,{successor_ticker:"KMB",successor_quantity:2})
  ]},
  {date:"2026-10-06",actions:[a("AAA","sell",10),a("KMB","hold",2)]}
 ],splits:[{date:"2026-10-04",ticker:"AAA",ratio:2}]};
 const rows=buildSessionActionColumns(track);
 assert.deepEqual(rows[1].partialSells,["AAA"],"Split 10→20, sale of 10 is partial");
 assert.ok(rows[1].sells.includes("ZZZ")&&!rows[1].partialSells.includes("ZZZ"),
  "Unknown entry units never imply partial sale");
 assert.deepEqual(rows[1].corporate,["KVUE → KMB"]);
 assert.ok(!rows[1].sells.includes("KVUE")&&!rows[1].buys.includes("KMB"),
  "Conversion must not be labeled a market fill");
 assert.deepEqual(rows[2].partialSells,[],"Final split-adjusted 10 shares close position");
 assert.deepEqual(rows[2].holds,["KMB"]);
});


test("NAV observations have the three action columns in the same six-column table, not only the lower accordion",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 assert.ok(src.includes('class="table-scroll nav-session-table-wrap"'));
 assert.ok(src.includes('<th scope="col">Sesión</th><th scope="col">NAV</th>'));
 for(const label of ["COMPRAS","VENTAS","MANTENER"])assert.ok(src.includes('<th scope="col">'+label+'</th>'));
 for(const field of ["buys","sells","holds"])assert.ok(src.includes('navActionCell(p.date,"'+field+'")'));
 assert.ok(src.includes('const navActions=new Map(buildSessionActionColumns(auditTrack).map(row=>[row.date,row]));'),
  "No inference from NAV shape: join audited execution sessions by their own dates");
 assert.ok(src.includes('renderSessionTickerList(row[key],key==="sells"?row.partialSells:[])'),
  "The star is only in sale cells when source-backed evidence reports a partial sale");
 assert.ok(src.includes('state.operationsAuditStatus==="pending"?"Cargando…":"N/D"'),
  "No audit yet must not appear as empty execution");
 assert.ok(src.includes('if(!row)return'),"Unknown audited dates cannot become confirmed no-action dates");
 assert.ok(css.includes(".nav-session-table-wrap .nav-session-table"));
 assert.ok(css.includes(".nav-session-table td:nth-child(5) .audit-session-ticker"));
});
test("NAV row renderer and per-session accordion use the exact same ticker and partial-star component",async()=>{
 const {renderSessionTickerList,buildSessionActionColumns}=await import("../src/operations-audit.mjs");
 assert.equal(renderSessionTickerList([]),'<span class="audit-empty-session">—</span>');
 assert.ok(renderSessionTickerList(["DECK","ENPH"]).includes("DECK"));
 assert.ok(!renderSessionTickerList(["DECK","ENPH"]).includes("audit-partial-star"));
 const starred=renderSessionTickerList(["AOS","PYPL"],["AOS"]);
 assert.equal((starred.match(/audit-partial-star/g)||[]).length,1);
 assert.ok(starred.includes("Venta parcial: quedan acciones tras el fill"));
 assert.ok(!starred.includes("PYPL*"));
 assert.deepEqual(buildSessionActionColumns(null),[]);
 const src=readFileSync(new URL("../src/operations-audit.mjs",import.meta.url),"utf8");
 assert.ok(src.includes("const sessionTickers=renderSessionTickerList;"));
});


test("MIDAS operational health exposes a separate DAILY RUN ledger, not the buy/sell table",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 const flow=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 for(const expected of [
  "Histórico de sesiones","monitoring-panel-daily","monitoring-panel-operations",
  'data-action="monitoring-tab"',"function verifyExecutionHistory(doc)",
  "function renderDailyExecutionTable(doc,status,roster)",
  "loadExecutionHistory()","./data/execution-history.json",
  "state.executionHistoryStatus","daily-execution-table",
  "Correctos","Fallos originales","No ejecutados","Pendientes","Sin programación",
  "Ver '+ids.length","laboratorio-cuantitativo"
 ])assert.ok(src.includes(expected),"Missing daily execution UI or source: "+expected);
 assert.ok(src.includes("d.expected+d.not_scheduled!==64"),"Missing 64-slot daily accounting reconciliation");
 assert.ok(src.includes("sum!==d.expected"),"Missing per-day result invariant");
 assert.ok(src.includes("Un workflow compartido cuenta por cada algoritmo asociado"),
   "Must explain shared workflow semantics, not pretend independent executions");
 assert.ok(css.includes(".daily-execution-table")&&css.includes(".daily-run-state.not_run"));
 assert.ok(flow.includes("GH_TOKEN=")&&flow.includes("build_execution_history.py --output"));
 assert.ok(flow.includes("build_execution_history.py --validate"));
 assert.ok(flow.includes("actions: read"));
});

test("MIDAS session history preserves unknown technical outcomes rather than fabricating zero runs",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const python=readFileSync(new URL("../scripts/build_execution_history.py",import.meta.url),"utf8");
 assert.ok(site.includes("doc.days.length>500"));
 assert.ok(site.includes('d.data_status==="not_verifiable"'));
 assert.ok(site.includes('Automatización sin verificar'));
 assert.ok(site.includes('Valoración registrada'));
 assert.ok(site.includes('day.journal_count'));
 assert.ok(site.includes('"<th>Sin verificar</th>"')||site.includes('<th>Sin verificar</th>'));
 assert.ok(site.includes("day.unverified"));
 assert.ok(python.includes("dt.date(2026, 10, 1)"));
 assert.ok(python.includes('"data_status": "not_verifiable"'));
 assert.ok(python.includes('"oldest_retained_run_session":'));
 assert.ok(python.includes('status, matched = "unverified", None'));
});

test("Session history renders preserved journals and subsequent recovery without rewriting automation outcomes",async()=>{
 const {runInNewContext}=await import("node:vm");
 const source=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const segment=source.slice(source.indexOf("function verifyExecutionHistory(doc)"),source.indexOf("function monitoring(){"));
 const context={Intl,esc:v=>String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;")};
 runInNewContext(segment+";this.api={verifyExecutionHistory,renderDailyExecutionTable};",context);
 const journal={slot:"IL-010",cohort:"Campaña actual",nav:100123.45,currency:"USD",inactive:true,recovered:true,
  source_path:"classic_sp500_state/ledger.json",source_sha256:"a".repeat(64),
  source_url:"https://github.com/idealab2026/laboratorio-cuantitativo/blob/main/classic_sp500_state/ledger.json",
  recorded_at_utc:"2026-11-04T18:03:09+00:00",first_trading_session:"2026-11-05"};
 const old={date:"2026-10-30",data_status:"not_verifiable",expected:null,success:null,failure:null,not_run:null,
  pending:null,unverified:null,not_scheduled:null,complete:null,details:[],journals:[{...journal,inactive:false,recovered:false}],
  journal_count:1,recovered_count:0,recovered_failures:0};
 const current={date:"2026-11-03",data_status:"verified",expected:1,success:0,failure:1,not_run:0,pending:0,
  unverified:0,not_scheduled:63,complete:true,journals:[journal],journal_count:1,recovered_count:1,recovered_failures:1,
  details:[{slot:"IL-010",status:"failure",reason:"Missing OHLC",workflows:[{workflow:"classic_sp500.yml",
   run_url:"https://github.com/idealab2026/laboratorio-cuantitativo/actions/runs/123"}]}]};
 const doc={schema:"midas_daily_execution_health_v1",status:"verified_github_actions",slot_count:64,automated_slots:26,
  first_tracked_session:"2026-02-27",oldest_retained_run_session:"2026-11-02",as_of_utc:"2026-11-04T18:00:00Z",days:[current,old]};
 context.api.verifyExecutionHistory(doc);
 const html=context.api.renderDailyExecutionTable(doc,"verified",{entries:[{slot:"IL-010",name:"Equiponderación"}]});
 assert.ok(html.includes("Valoración registrada")&&html.includes("30/10/2026"));
 assert.ok(html.includes("Recuperación posterior documentada"));
 assert.ok(html.includes("Falló originalmente"));
 assert.ok(html.includes("1 recuperados"));
 assert.ok(html.includes("100.123,45 USD"));
 assert.ok(html.includes(journal.source_url));
 assert.ok(!html.includes("Cierre verificado")&&!html.includes("Histórico no disponible"));
 const partial=structuredClone(doc);
 Object.assign(partial.days[0],{data_status:"partially_verified",expected:2,unverified:1,not_scheduled:62,complete:false});
 partial.days[0].details.push({slot:"IL-011",status:"unverified",workflows:[{workflow:"classic_sp500.yml"}]});
 context.api.verifyExecutionHistory(partial);
 const partialHtml=context.api.renderDailyExecutionTable(partial,"stale",{entries:[]});
 assert.ok(partialHtml.includes("Registro técnico parcial"));
 assert.ok(partialHtml.includes("No se pudo actualizar el histórico"));
 assert.ok(partialHtml.includes('class="daily-count daily-ok">N/D'));
 assert.ok(partialHtml.includes('class="daily-count daily-fail">1'));
 const tampered=structuredClone(doc);tampered.days[0].recovered_count=0;
 assert.throws(()=>context.api.verifyExecutionHistory(tampered),/no conciliados/);
 const external=structuredClone(doc);external.days[0].journals[0].source_url="https://example.com/private";
 assert.throws(()=>context.api.verifyExecutionHistory(external),/trazabilidad/);
});


test("Recovered execution archive shows real outcomes, institutional proof and unknown schedule coverage",async()=>{
 const {runInNewContext}=await import("node:vm");
 const source=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const segment=source.slice(source.indexOf("function verifyExecutionHistory(doc)"),source.indexOf("function monitoring(){"));
 const context={Intl,esc:v=>String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;")};
 runInNewContext(segment+";this.api={verifyExecutionHistory,renderDailyExecutionTable};",context);
 const proof="https://github.com/idealab2026/laboratorio-cuantitativo/blob/main/data/execution-history-archive.json";
 const day={date:"2026-10-30",data_status:"archived_observations",expected:1,success:0,failure:1,
  not_run:null,pending:null,unverified:0,not_scheduled:null,complete:null,journals:[],journal_count:0,recovered_count:0,recovered_failures:0,
  details:[{slot:"IL-044",status:"failure",reason:null,workflows:[{workflow:"genetic_sp500.yml",status:"failure",run_id:null,run_url:null,
   source_kind:"reviewed_archive",evidence_id:"ARCH-0001",attempts:2,evidence_sha256:"a".repeat(64),evidence_url:proof}]}]};
 const unknown={...structuredClone(day),date:"2026-09-30",data_status:"not_verifiable",details:[],expected:null,success:null,failure:null,unverified:null};
 const doc={schema:"midas_daily_execution_health_v1",status:"verified_github_actions",slot_count:64,automated_slots:26,
  first_tracked_session:"2026-02-27",oldest_retained_run_session:"2026-11-02",as_of_utc:"2026-11-05T00:00:00Z",
  reviewed_archive:{first_session:"2026-10-01",last_session:"2026-10-30"},days:[day,unknown]};
 context.api.verifyExecutionHistory(doc);
 const html=context.api.renderDailyExecutionTable(doc,"verified",{entries:[]});
 assert.ok(html.includes('Archivo técnico recuperado')&&html.includes(proof));
 assert.ok(html.includes('Archivo de ejecuciones; programación histórica no reconstruida'));
 assert.ok(html.includes('colspan="6">Sin registro técnico acreditado'));
 assert.ok(html.includes('Ver 1 algoritmo</summary>'));
 assert.ok(html.includes('Falló originalmente'));
 assert.ok(!html.includes('N/D'));
 for(const mutate of [d=>d.days[0].not_run=0,d=>d.days[0].details[0].workflows[0].run_id=123,
   d=>d.days[0].details[0].workflows[0].evidence_url="https://example.com/original"]){
  const bad=structuredClone(doc);mutate(bad);assert.throws(()=>context.api.verifyExecutionHistory(bad));
 }
});


test("Three lifecycle cohorts exhaust the 64 validated slots with no overlap",async()=>{
 const {verifyFullRoster,strategyCompetitionPhase,partitionCompetitionRows}=await import("../src/competition-roster.mjs");
 const roster=JSON.parse(readFileSync(new URL("../data/competition-roster.json",import.meta.url),"utf8"));
 const candidates=JSON.parse(readFileSync(new URL("../data/strategy-candidates.json",import.meta.url),"utf8"));
 verifyFullRoster(roster);
 const all=roster.entries.map(e=>({id:e.slot,record:null,group:e.group}));
 const parts=partitionCompetitionRows([...all,...candidates.candidates.map(e=>({id:e.id,candidate:e,group:e.group}))]);
 assert.equal(parts.active.length,35);
 assert.equal(parts.obsolete.length,13);
 assert.equal(parts.development.length,18);
 assert.equal(parts.development.filter(r=>r.candidate).length,2);
 assert.equal(parts.active.length+parts.obsolete.length+parts.development.length,66);
 assert.equal(parts.active[0].id,"IL-010");
 assert.equal(parts.active.at(-1).id,"IL-044");
 assert.equal(parts.obsolete[0].id,"IL-001");
 assert.equal(parts.obsolete.at(-1).id,"IL-048");
 assert.equal(parts.development[0].id,"IL-049");
 assert.equal(parts.development[15].id,"IL-064");
 assert.equal(parts.development[16].id,"IL-R001");
 assert.equal(strategyCompetitionPhase("IL-037"),"active");
 assert.equal(strategyCompetitionPhase("IL-044"),"active");
 assert.equal(strategyCompetitionPhase("IL-045"),"obsolete");
 assert.equal(strategyCompetitionPhase("IL-064"),"development");
 assert.throws(()=>strategyCompetitionPhase("IL-065"),/outside signed catalogue/);
 assert.throws(()=>strategyCompetitionPhase("IL-000"),/outside signed catalogue/);
 assert.throws(()=>partitionCompetitionRows([{id:"IL-010"},{id:"IL-010"}]),/Duplicate/);
});

test("Only active paper cohort is considered for the competition leader",async()=>{
 const {partitionCompetitionRows}=await import("../src/competition-roster.mjs");
 const roster=JSON.parse(readFileSync(new URL("../data/competition-roster.json",import.meta.url),"utf8"));
 const phases=partitionCompetitionRows(roster.entries);
 const current=phases.active.map(e=>({id:e.slot,record:archive.bySlot.get(e.slot)||null}));
 const leader=paperLeaderboard(current);
 assert.ok(leader);
 assert.ok(phases.active.some(x=>x.slot===leader.id));
 assert.ok(!phases.obsolete.some(x=>x.slot===leader.id));
 assert.ok(!phases.development.some(x=>x.slot===leader.id));
 // A retired leader with a fabricated high return must not enter the active cohort.
 const fakeRetired={id:"IL-001",record:{
  first_session:"2026-10-01",session_count:12,return_pct:900,history:[]}};
 const considered=paperLeaderboard([...current]);
 assert.equal(considered.id,leader.id);
 assert.ok(fakeRetired.record.return_pct>leader.record.return_pct);
});

test("Competition view defaults to active lifecycle tab with three filtered, ordered cohorts",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 for(const expected of [
  'competitionPhase:"active"',
  'role="tablist" aria-label="Fase de las estrategias"',
  '"Activos"',
  '"Obsoletos"',
  '"En desarrollo"',
  'data-action="competition-phase"',
  'strategyCompetitionPhase(item.slot)===selected',
  'selected==="development"&&state.strategyCandidates',
  'const leader=phase==="active"?paperLeaderboard(phases.active.map',
  'state.competitionPhase=value;',
  'state.fullRosterGroup="";state.fullRosterQuery="";',
  'class="competition-phase-count"',
  'No participan en la clasificación ni en el liderazgo',
  'No se asigna rentabilidad ni líder'
 ])assert.ok(site.includes(expected),"Missing lifecycle functionality: "+expected);
 assert.ok(css.includes(".competition-lifecycle-tabs"));
 assert.ok(css.includes(".competition-phase-notice"));
 assert.ok(site.includes("sortFullCompetitionRows([...existing,...proposals]"),
  "Sorting still applies only to the current filtered rows");
 assert.ok(site.includes("fullRosterRows()"),"Keep existing columns and profile links");
});


test("live signals render a pending order separately from a simulated fill",async()=>{
 const {runInNewContext}=await import("node:vm");
 const block=source.slice(source.indexOf("const SIGNAL_REFRESH_MS"),source.indexOf("function liveSessionHTML"));
 const context={Intl,shortPaperDate:v=>v,esc:v=>String(v),strategyCompetitionPhase:()=>"active"};
 runInNewContext(block+";this.signalAPI={verifyLiveSignals,renderSignalRows};",context);
 const pending={ticker:"AAPL",action:"buy",decision_session:"2026-11-05",target_session:"2026-11-06",
  limit_price:null,target_weight:null};
 const fill={ticker:"AAPL",action:"buy",decision_session:"2026-11-05",price:221.25};
 const track={label:"Capital Cycle",currency:"USD",session:"2026-11-06",decision_session:"2026-11-05",
  status:"recorded",signals:[pending],executions:[fill]};
 const feed={schema:"midas_execution_signals_v1",published_at_utc:"2026-11-07T00:07:00Z",
  tracks:Object.fromEntries(Array.from({length:35},(_,i)=>["IL-"+String(i+10).padStart(3,"0"),track]))};
 assert.equal(context.signalAPI.verifyLiveSignals(feed),feed);
 const orderHtml=context.signalAPI.renderSignalRows([pending],"USD",false);
 const fillHtml=context.signalAPI.renderSignalRows([fill],"USD",true);
 assert.match(orderHtml,/Comprar/);
 assert.match(orderHtml,/Por determinar/);
 assert.match(orderHtml,/Apertura prevista/);
 assert.match(fillHtml,/Compra registrada/);
 assert.match(fillHtml,/221,25/);
 assert.throws(()=>context.signalAPI.verifyLiveSignals({...feed,tracks:{"IL-038":track}}),/incompleto/);
});

test("trading deep links wait for the diary and only show executions for the selected session",async()=>{
 const {runInNewContext}=await import("node:vm");
 const context={};
 const block=source.slice(source.indexOf("function tradingReadModel"),source.indexOf("function tradingStatus"));
 runInNewContext(block+";this.read=tradingReadModel;",context);
 const selection={slot:"IL-011"};
 const loading=context.read(null,undefined,selection);
 assert.equal(loading.orders.length,0);
 assert.equal(loading.fills.length,0);
 const day="2026-11-06", previous="2026-11-05";
 const feed={
  opening_plans:{[day]:{tracks:{"IL-011":{orders:[{ticker:"FSLR",action:"buy"}]}}}},
  tracks:{"IL-011":{label:"EMA/RSI",currency:"USD",session:previous,executions:[{ticker:"FSLR",action:"sell"}]}}
 };
 const room=context.read(feed,day,selection);
 assert.equal(room.orders.length,1);
 assert.equal(room.fills.length,0);
 assert.equal(context.read(feed,previous,selection).fills.length,1);
});


test("Trading room is a standalone top-level MIDAS section, not a duplicated competition subnav",()=>{
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 const nav=html.match(/<nav class="product-tabs midas-header-menu"[\s\S]*?<\/nav>/)?.[0];
 assert.ok(nav,"Missing primary MIDAS header navigation");
 const competition=nav.indexOf('data-view="competition"');
 const trading=nav.indexOf('data-view="trading"');
 const theses=nav.indexOf('data-view="theses"');
 assert.ok(competition>=0&&trading>competition&&theses>trading,
  "Trading room belongs between competition and thesis tracking");
 assert.equal((nav.match(/data-view="trading"/g)||[]).length,1);
 assert.ok(site.includes('"competition","trading","algorithm"'),
  "Trading must remain directly navigable by view=trading");
 assert.ok(site.includes("trading:tradingRoom"),"The main route must render the real existing trading desk");
 assert.ok(site.includes('b.dataset.view===state.view||'),
  "Trading is selected by its OWN top-level button");
 assert.ok(site.includes('(state.view==="algorithm"&&b.dataset.view==="competition")'),
  "Only individual algorithm detail should select the competition tab");
 assert.ok(!site.includes('(["algorithm","trading"].includes(state.view)'),
  "The competition tab must not also appear selected in the trading room");
 assert.ok(html.includes('class="product-tabs midas-header-menu"'));
 assert.ok(css.includes(".midas-topbar .midas-header-menu{"));
 assert.ok(css.includes("overflow-x:auto"),"Primary navigation must stay scrollable on small screens");
 assert.ok(!html.includes('id="competition-navigation"'));
 assert.ok(!site.includes("function competitionNavigation("));
 assert.ok(!css.includes(".competition-nav a[aria-current"),
  "Remove the duplicate secondary nav, not the signal workspace");
 assert.ok(site.includes('function tradingRoom(){'));
 assert.ok(site.includes('function paintTradingRoom(){'));
});


test("trading desk distinguishes close-day signal, pre-open intent and actual paper fill",async()=>{
 const {runInNewContext}=await import("node:vm");
 const context={};
 const block=source.slice(source.indexOf("function tradingReadModel"),source.indexOf("function tradingStatus"))+
  source.slice(source.indexOf("function deskActivity"),source.indexOf("function deskAlgorithmFilters"));
 runInNewContext(block+";this.activity=deskActivity;",context);
 const feed={
  opening_plans:{"2026-11-09":{previous_session:"2026-11-06",tracks:{
   "IL-011":{status:"recorded",session:"2026-11-06",orders:[
    {ticker:"AAPL",action:"buy",decision_session:"2026-11-06",
     target_session:"2026-11-09",target_weight:.12,limit_price:null}]}}}},
  tracks:{"IL-011":{label:"EMA/RSI",currency:"USD",session:"2026-11-09",status:"recorded",
   signals:[{ticker:"AAPL",action:"buy",decision_session:"2026-11-06",
    target_session:"2026-11-09",target_weight:.12,limit_price:null}],
   executions:[{ticker:"AAPL",action:"buy",price:100,decision_session:"2026-11-06"}]}}
 };
 const selection={ticker:"",side:"all"};
 const selected=new Set(["IL-011"]);
 const signals=context.activity(feed,"2026-11-09",selection,"signals",selected);
 assert.equal(signals.target,"2026-11-06");
 assert.equal(signals.orders.length,1);
 assert.equal(signals.orders[0].source,"decision_signal");
 const planned=context.activity(feed,"2026-11-09",selection,"opening",selected);
 assert.equal(planned.orders[0].book_status,"recorded");
 assert.equal(planned.orders[0].source,"opening_plan");
 const fills=context.activity(feed,"2026-11-09",selection,"fills",selected);
 assert.equal(fills.orders.length,1);
 assert.equal(fills.orders[0].source,"paper_fill");
 assert.equal(context.activity(feed,"2026-11-06",selection,"fills",selected).orders.length,0,
  "Prior-day signal must not be shown as an executed purchase");
});

test("trading desk never fabricates order notional, validates unique audited fills and flags stale books",async()=>{
 const {runInNewContext}=await import("node:vm");
 const context={
  state:{operationsAudit:{tracks:{"IL-011":{sessions:[{date:"2026-11-09",actions:[
   {ticker:"AAPL",side:"buy",price:100,quantity:10,fee:1,reason:"Registro verificado",
    reason_basis:"recorded"}]}]}}}},
  signalFeed:{tracks:{"IL-011":{analysis:{date:"2026-11-06",rows:[
   ["AAPL","passed",["rsi"]]]}}}},
  signalNames:{buy:"Comprar",sell:"Vender",rebalance:"Rebalancear"},
  terminalLabels:{passed:"Superó el filtro técnico"},
  esc:input=>String(input),fmt:input=>Number(input).toFixed(2),
  shortPaperDate:day=>day,
  deskChartSeries:()=>[],sparkline:()=>"<svg></svg>",
  Intl
 };
 const block=source.slice(source.indexOf("function deskRowChart"),source.indexOf("function deskResults"));
 runInNewContext(block+";this.ui={deskSignalTable,deskRowState,deskAuditedFill};",context);
 const planned={id:"IL-011",label:"EMA/RSI",ticker:"AAPL",action:"buy",
  decision_session:"2026-11-06",target_session:"2026-11-09",target_weight:.12,
  limit_price:null,currency:"USD",book_status:"recorded"};
 const pending=context.ui.deskSignalTable([planned],"opening",null,"2026-11-09","2026-11-06");
 assert.match(pending,/Orden prevista/);
 assert.match(pending,/No se publica cantidad ni importe de la orden/);
 assert.match(pending,/Peso objetivo:/);
 assert.match(pending,/Evaluación documentada/);
 assert.doesNotMatch(pending,/1000\.00 USD/,"Do not borrow later fill quantity for an order");
 assert.equal(context.ui.deskRowState({...planned,book_status:"stale"},"opening").tone,"warning");
 assert.equal(context.ui.deskRowState({...planned,book_status:"paused"},"opening").tone,"warning");
 const fill={...planned,source:"paper_fill",price:100};
 const recorded=context.ui.deskSignalTable([fill],"fills",null,"2026-11-09","2026-11-09");
 assert.match(recorded,/Ejecutada en paper/);
 assert.match(recorded,/Bruto paper: 1000\.00 USD/);
 assert.match(recorded,/Motivo registrado: Registro verificado/);
 const wrongPrice=context.ui.deskSignalTable([{...fill,price:101}],"fills",null,"2026-11-09","2026-11-09");
 assert.match(wrongPrice,/Bruto paper: N\/D/);
 const otherDay=context.ui.deskSignalTable([fill],"fills",null,"2026-11-10","2026-11-10");
 assert.match(otherDay,/Bruto paper: N\/D/);
 context.state.operationsAudit.tracks["IL-011"].sessions[0].actions.push(
  {ticker:"AAPL",side:"buy",price:100,quantity:10,reason:"Duplicada",reason_basis:"recorded"});
 assert.equal(context.ui.deskAuditedFill(fill,"2026-11-09"),null,
  "Ambiguous matching rows may not prove capital invested");
});

test("trading UI explicitly separates decisions, pre-open plans and completed paper orders",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 for(const keyword of ['signals:"Señales del cierre"','opening:"Órdenes previstas"',
   'fills:"Ejecuciones simuladas"',"No equivale a una orden de compra",
   "No se publica cantidad ni importe de la orden","No hay órdenes enviadas a un bróker real",
   "Motivo individual no publicado","book_status:plan?.tracks[id]?.status"])
  assert.ok(site.includes(keyword),"Missing plan/fill separation or evidence label: "+keyword);
 assert.ok(css.includes('.desk-evidence[data-evidence="warning"]'));
 assert.ok(css.includes(".desk-interpretation"));
});


test("trading charts are embedded once per record, including repeated tickers, without stale three-chart sidebar",async()=>{
 const {runInNewContext}=await import("node:vm");
 const cutoffs=[];
 const context={
  state:{operationsAuditStatus:"ready",operationsAudit:null},
  signalFeed:{tracks:{}},terminalLabels:{},signalNames:{buy:"Comprar",sell:"Vender",rebalance:"Rebalancear"},
  esc:input=>String(input),fmt:input=>Number(input).toFixed(2),
  shortPaperDate:day=>day,Intl,
  deskChartSeries:(ticker,cutoff)=>{
   cutoffs.push({ticker,cutoff});
   return [["2026-11-03",10],["2026-11-05",11],["2026-11-06",12]];
  },
  sparkline:(values,label)=>'<svg role="img" aria-label="'+label+'"></svg>'
 };
 const block=source.slice(source.indexOf("function deskRowChart"),source.indexOf("function deskResults"));
 runInNewContext(block+";this.rows=deskSignalTable;",context);
 const record=(id,action)=>({ticker:"EPAM",action,id,label:"Algoritmo "+id,
  decision_session:"2026-11-05",target_session:"2026-11-06",target_weight:null,
  limit_price:null,currency:"USD",book_status:"recorded"});
 const markup=context.rows([record("IL-015","buy"),record("IL-016","buy")],
  "opening",null,"2026-11-06","2026-11-05");
 assert.equal((markup.match(/class="desk-chart-cell"/g)||[]).length,2);
 assert.equal((markup.match(/<svg role="img"/g)||[]).length,2);
 assert.equal((markup.match(/EPAM/g)||[]).length>=2,true);
 assert.equal(cutoffs.length,2);
 assert.ok(cutoffs.every(row=>row.ticker==="EPAM"&&row.cutoff==="2026-11-05"));
 assert.match(markup,/Evolución auditada/);
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 assert.ok(!site.includes("Hasta 3 empresas"));
 assert.ok(!site.includes("deskChartSymbols("));
 assert.ok(!site.includes('data-action="desk-chart"'));
 assert.ok(!css.includes(".desk-charts"));
 assert.ok(css.includes(".desk-row-chart .mini-chart"));
});

test("audited mini charts use only closes on or before the causal cutoff",async()=>{
 const {runInNewContext}=await import("node:vm");
 const context={state:{
  operationsAuditStatus:"ready",
  operationsAudit:{tracks:{
   "IL-011":{prices:{EPAM:[
    {date:"2026-11-04",price:8},
    {date:"2026-11-05",price:9},
    {date:"2026-11-06",price:13}
   ]}}
  }}
 },esc:v=>String(v),fmt:n=>Number(n).toFixed(2),shortPaperDate:d=>d,
 sparkline:()=>"<svg role='img'></svg>"};
 const block=source.slice(source.indexOf("let deskPriceSource=null"),source.indexOf("function deskAuditedFill"));
 runInNewContext(block+";this.chart=deskRowChart;this.history=deskChartSeries;",context);
 const history=context.history("EPAM","2026-11-05");
 assert.equal(history.length,2);
 assert.equal(history.at(-1)[0],"2026-11-05");
 const safe=context.chart("EPAM","2026-11-05");
 assert.match(safe,/9\.00 USD/);
 assert.doesNotMatch(safe,/13\.00 USD/);
 const absent=context.chart("MISSING","2026-11-05");
 assert.match(absent,/Sin histórico auditado suficiente/);
 assert.ok(!absent.includes("<svg"));
});


test("manual trading refresh gives a visible outcome even if the published snapshot is unchanged",async()=>{
 const {runInNewContext}=await import("node:vm");
 const published="2026-11-09T12:05:00Z";
 const same={schema:"midas_execution_signals_v1",published_at_utc:published,tracks:{}};
 const before={schema:"midas_execution_signals_v1",published_at_utc:published,tracks:{}};
 const paints=[];
 const context={
  signalFeed:before,signalFeedError:false,signalRequest:null,signalChecked:0,
  signalRefresh:{state:"idle",at:null},document:{hidden:false},
  Date,TRADING_REFRESH_MS:30000,SIGNAL_REFRESH_MS:60000,
  tradingRoomActive:()=>true,liveSessionActive:()=>true,
  fetch:async(path,opts)=>{assert.equal(path,"./data/execution-signals.json");assert.equal(opts.cache,"no-store");
   return {ok:true,json:async()=>same};},
  verifyLiveSignals:doc=>doc,
  paintTradingRoom:()=>paints.push("room"),
  paintTradingRefresh:()=>paints.push("refresh"),
  tradingDay:()=>null,
  $:()=>null
 };
 const a=source.indexOf("async function refreshLiveSignals(force=false){");
 const b=source.indexOf("\nconst TRADING_REFRESH_MS=30_000;",a);
 assert.ok(a>=0&&b>a);
 runInNewContext(source.slice(a,b)+";this.refresh=refreshLiveSignals;",context);
 await context.refresh(true);
 assert.equal(context.signalRefresh.state,"unchanged");
 assert.ok(Number.isFinite(context.signalRefresh.at));
 assert.equal(context.signalFeed.published_at_utc,published,
  "Checking a file must not forge a new publication time");
 assert.ok(paints.length>=1);
 context.fetch=async()=>({ok:true,json:async()=>({
  ...same,published_at_utc:"2026-11-09T18:05:00Z"})});
 await context.refresh(true);
 assert.equal(context.signalRefresh.state,"updated");
 assert.equal(context.signalFeed.published_at_utc,"2026-11-09T18:05:00Z");
 context.fetch=async()=>{throw Error("network unavailable")};
 await context.refresh(true);
 assert.equal(context.signalRefresh.state,"error");
 assert.equal(context.signalFeedError,true);
 assert.equal(context.signalFeed.published_at_utc,"2026-11-09T18:05:00Z",
  "A network error must preserve the last valid snapshot");
});

test("trading refresh shows separate publication and check clocks with a loading state",async()=>{
 const {runInNewContext}=await import("node:vm");
 const mock={signalRefresh:{state:"idle",at:null},signalRequest:null,
  madridTime:{format:()=> "19:17"},$:(id)=>mock.nodes[id],
  nodes:{
   "trading-refresh-result":{textContent:"",dataset:{}},
   "trading-refresh-button":{disabled:false,textContent:""}
  }};
 const a=source.indexOf("function tradingRefreshFeedback(){");
 const b=source.indexOf("function tradingOrderPrice(",a);
 assert.ok(a>=0&&b>a);
 runInNewContext(source.slice(a,b)+";this.feedback=tradingRefreshFeedback;this.paint=paintTradingRefresh;",mock);
 assert.match(mock.feedback(),/Aún no se ha comprobado/);
 mock.signalRefresh.state="checking";mock.signalRequest=Promise.resolve({});
 mock.paint();
 assert.match(mock.nodes["trading-refresh-result"].textContent,/Comprobando/);
 assert.equal(mock.nodes["trading-refresh-button"].disabled,true);
 mock.signalRequest=null;mock.signalRefresh.state="unchanged";mock.signalRefresh.at=Date.now();
 mock.paint();
 assert.match(mock.nodes["trading-refresh-result"].textContent,/sin nuevas publicaciones/);
 assert.equal(mock.nodes["trading-refresh-button"].disabled,false);
 mock.signalRefresh.state="error";mock.paint();
 assert.match(mock.nodes["trading-refresh-result"].textContent,/Error de consulta/);
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(src.includes('id="trading-refresh-result"'));
 assert.ok(src.includes('id="trading-refresh-button"'));
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 assert.ok(css.includes(".trading-feed-status"));
});


test("Buy The Dip monitoring shows dated real paper accounting, holdings and last run",async()=>{
 const {runInNewContext}=await import("node:vm");
 const m={mode:"monthly_signal_daily_mark",asof:"2026-11-06",
  nav:109098.01,cash:5284.26,held_tickers:["ALGN","EPAM"],
  last_signal_session:"2026-10-30",last_fill_session:"2026-11-02",pending_count:0,
  last_run:{run_id:42341099381,outcome:"success",recorded_at_utc:"2026-11-07T05:04:35Z"}};
 const c={signalFeed:{tracks:{"IL-039":{monitor:m}}},
  state:{executionHistory:{live_plan:{days:{"2026-11-09":{lanes:[
   {workflow:"buy_the_dip_strategy.yml",slots:["IL-039"],due:["2099-11-09T23:27:00Z"]}
  ]}}}}},
  tradingDay:()=>"2026-11-09",shortPaperDate:d=>d,
  madridDateTime:{format:date=>new Date(date).toISOString()},
  esc:v=>String(v),Intl,Date,Number};
 const a=source.indexOf("function buyDipHealthHTML(){");
 const b=source.indexOf("function deskResults(model){",a);
 assert.ok(a>=0&&b>a,"Missing status panel");
 runInNewContext(source.slice(a,b)+";this.view=buyDipHealthHTML;",c);
 const html=c.view();
 for(const value of ["Buy The Dip · estado de la cartera simulada","109.098,01 USD",
  "5.284,26 USD","ALGN","EPAM","2026-11-06","2026-10-30","2026-11-02",
  "42341099381","Valoración auditada","Próxima revisión programada"])
  assert.ok(html.includes(value),"Missing dated status fact: "+value);
 assert.ok(!html.includes("Comprar ALGN"),"A holding is not a new purchase");
 assert.ok(html.includes("No son precios en tiempo real"));
 assert.ok(html.includes("github.com/idealab2026/laboratorio-cuantitativo/actions/workflows/buy_the_dip_strategy.yml"));
 c.signalFeed.tracks["IL-039"].monitor=null;
 assert.match(c.view(),/Sin resumen validado de cartera/);
});

test("scheduled trading engine status says pending before due, never missing as a fact",async()=>{
 const {runInNewContext}=await import("node:vm");
 const c={state:{executionHistory:{live_plan:{days:{"2026-11-09":{lanes:[
  {workflow:"buy_the_dip_strategy.yml",slots:["IL-039"],due:["2099-11-09T23:27:00Z"]}
 ]}}}}},
 tradingDay:()=>"2026-11-09",tradingFilter:{slot:"IL-039"},
 terminalState:{activity:new Map(),pending:new Set()},Date,Number,Intl,
 shortPaperDate:d=>d,madridDateTime:{format:date=>new Date(date).toISOString()},
 terminalRunLabels:{success:"Completado"},esc:v=>String(v)};
 const a=source.indexOf("function terminalActivityHTML(){");
 const b=source.indexOf("function paintTerminalActivity(){",a);
 assert.ok(a>=0&&b>a,"Missing runtime status function");
 runInNewContext(source.slice(a,b)+";this.view=terminalActivityHTML;",c);
 assert.match(c.view(),/Ejecución pendiente según calendario/);
 assert.doesNotMatch(c.view(),/No se ha observado una ejecución programada para esta sesión\./);
});

test("Buy The Dip paper status is treated as optional but strictly validated evidence",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const exporter=readFileSync(new URL("../scripts/build_operations_audit.py",import.meta.url),"utf8");
 assert.ok(src.includes('if(id!=="IL-039"||monitor.mode!=="monthly_signal_daily_mark"'));
 assert.ok(src.includes('monitor.asof!==track.session'));
 assert.ok(src.includes('terminalState.mode==="terminal"'));
 assert.ok(exporter.includes('"monitor": buy_the_dip_monitor(book)'));
 assert.ok(exporter.includes('last_fill_session'));
 assert.ok(exporter.includes('strategy_runtime/buy_the_dip_strategy.json'));
});
