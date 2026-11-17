import test from "node:test";
import assert from "node:assert/strict";
import {buildOperationLots,sortOperationLots} from "../src/operation-lots.mjs";
import {buildSessionActionColumns,renderOperationsAudit,summarizeOperationsAudit,
 verifyOperationsAudit} from "../src/operations-audit.mjs";
const entry=(ticker,side,price,quantity,fee=null)=>({ticker,side,price,quantity,fee});
const track=(sessions,prices={},splits=[])=>({currency:"USD",sessions,prices,splits});

test("one buy with partial sell reconciles realized and marked-to-market P/L, including documented fees",()=>{
 const lots=buildOperationLots(track([
  {date:"2026-10-01",actions:[entry("ABT","buy",100,10,1)]},
  {date:"2026-10-02",actions:[entry("ABT","sell",115,4,1)]},
  {date:"2026-10-05",actions:[]}
 ],{ABT:[{date:"2026-10-05",price:120}]}));
 assert.equal(lots.length,1);
 const row=lots[0];
 assert.equal(row.action,"parcial");
 assert.equal(row.buyPrice,100);
 assert.equal(row.salePrice,115);
 assert.equal(row.invested,1001);
 assert.equal(row.shares,10);
 assert.equal(row.remainingShares,6);
 assert.equal(row.soldShares,4);
 assert.ok(Math.abs(row.pnl-178)<1e-8);
 assert.ok(Math.abs(row.returnPct-(178/1001*100))<1e-8);
 assert.equal(row.feeComplete,true);
 assert.equal(row.markDate,"2026-10-05");
});
test("closed lot has realized net P/L, never marks a market close as an execution",()=>{
 const rows=buildOperationLots(track([
  {date:"2026-10-01",actions:[entry("SPY","buy",100,5,1)]},
  {date:"2026-10-03",actions:[entry("SPY","sell",110,5,1)]}
 ],{SPY:[{date:"2026-10-03",price:120}]}));
 assert.equal(rows.length,1);
 assert.equal(rows[0].action,"cerrada");
 assert.equal(rows[0].salePrice,110);
 assert.equal(rows[0].markPrice,null);
 assert.ok(Math.abs(rows[0].pnl-48)<1e-8);
});
test("unknown buy cost or quotes does not fabricate trade P/L",()=>{
 const a=buildOperationLots(track([
  {date:"2026-10-01",actions:[entry("AAA","buy",null,3)]},
  {date:"2026-10-05",actions:[]}
 ]));
 assert.equal(a[0].pnl,null);
 assert.equal(a[0].returnPct,null);
 const b=buildOperationLots(track([{date:"2026-10-01",actions:[entry("BBB","buy",22,2)]}]));
 assert.equal(b[0].pnl,null);
 const c=buildOperationLots(track([{date:"2026-10-01",actions:[entry("CCC","sell",30,2)]}]));
 assert.equal(c[0].action,"sin_base");
 assert.equal(c[0].salePrice,30);
 assert.equal(c[0].pnl,null);
});
test("merger entitlement is not a sell, predecessor remains reported as a conversion without invented P/L",()=>{
 const rows=buildOperationLots(track([
  {date:"2026-10-15",actions:[entry("KVUE","buy",18.389189160346984,645.114733)]},
  {date:"2026-11-02",actions:[{ticker:"KVUE",side:"corporate_action",price:null,
    successor_ticker:"KMB",successor_quantity:94}]}
 ],{KVUE:[{date:"2026-10-30",price:19.31}]}));
 assert.equal(rows[0].action,"convertida");
 assert.equal(rows[0].convertedTo,"KMB");
 assert.equal(rows[0].pnl,null);
 assert.equal(rows[0].salePrice,null);
 assert.equal(rows[0].remainingShares,0);
});
test("stock split changes per-share basis and current shares but not purchased original shares or invested cash",()=>{
 const rows=buildOperationLots(track([
  {date:"2026-10-01",actions:[entry("XYZ","buy",100,10,0)]},
  {date:"2026-10-05",actions:[entry("XYZ","sell",55,10,0)]},
  {date:"2026-10-06",actions:[]}
 ],{XYZ:[{date:"2026-10-06",price:60}]},[
  {date:"2026-10-03",ticker:"XYZ",ratio:2}
 ]));
 assert.equal(rows[0].buyPrice,50);
 assert.equal(rows[0].shares,10);
 assert.equal(rows[0].splitFactor,2);
 assert.equal(rows[0].remainingShares,10);
 assert.equal(rows[0].invested,1000);
 assert.equal(rows[0].pnl,150);
});
test("unpriced sales are still counted as exits but cannot claim a P/L",()=>{
 const lots=buildOperationLots(track([
  {date:"2026-10-01",actions:[entry("AAA","buy",30,5)]},
  {date:"2026-10-02",actions:[entry("AAA","sell",null,5)]}
 ]));
 assert.equal(lots[0].action,"cerrada");
 assert.equal(lots[0].soldShares,5);
 assert.equal(lots[0].salePrice,null);
 assert.equal(lots[0].pnl,null);
});
test("retrospective weekly close preserves modeled sale without certifying realized P/L",()=>{
 const modeled={...entry("AAA","sell",104,5,0.8),
   price_basis:"historical_week_close_proxy"};
 const observed={...entry("BBB","sell",107,5,0.8),
   price_basis:"book_fill"};
 const rows=buildOperationLots(track([
  {date:"2026-11-10",actions:[entry("AAA","buy",100,5,0.5),
                              entry("BBB","buy",100,5,0.5)]},
  {date:"2026-11-13",actions:[modeled,observed]}
 ],{AAA:[{date:"2026-11-13",price:104}],
    BBB:[{date:"2026-11-13",price:107}]}));
 const a=rows.find(x=>x.ticker==="AAA"),b=rows.find(x=>x.ticker==="BBB");
 assert.equal(a.modelledSale,true);
 assert.equal(a.action,"cerrada");
 assert.equal(a.salePrice,104);
 assert.equal(a.soldShares,5);
 assert.equal(a.pnl,null,"No certified P/L from retrospective OHLC");
 assert.equal(a.returnPct,null);
 assert.equal(b.modelledSale,false);
 assert.ok(Number.isFinite(b.pnl));
 assert.ok(Number.isFinite(b.returnPct));
});
test("mixed modelled and observed partial sales keep FIFO quantities but no false P/L",()=>{
 const rows=buildOperationLots(track([
  {date:"2026-11-09",actions:[entry("AAA","buy",100,10,1)]},
  {date:"2026-11-12",actions:[entry("AAA","sell",105,4,0.4)]},
  {date:"2026-11-13",actions:[{...entry("AAA","sell",106,2,0.2),
      price_basis:"historical_week_close_proxy"}]},
  {date:"2026-11-16",actions:[]}
 ],{AAA:[{date:"2026-11-16",price:110}]}));
 assert.equal(rows[0].remainingShares,4);
 assert.equal(rows[0].soldShares,6);
 assert.equal(rows[0].modelledSale,true);
 assert.equal(rows[0].pnl,null);
});

test("sorting defaults to open first, then recent, and places unmeasurable last for metric sorts",()=>{
 const t=track([
  {date:"2026-10-01",actions:[entry("AAA","buy",10,1)]},
  {date:"2026-10-02",actions:[entry("BBB","buy",20,1)]},
  {date:"2026-10-03",actions:[entry("AAA","sell",15,1)]},
  {date:"2026-10-04",actions:[]}
 ],{BBB:[{date:"2026-10-04",price:22}]});
 const rows=buildOperationLots(t);
 assert.deepEqual(sortOperationLots(rows).map(r=>r.ticker),["BBB","AAA"]);
 assert.deepEqual(sortOperationLots(rows,"pnl",true).map(r=>r.ticker),["AAA","BBB"]);
});

test("public audit never counts simulated Friday OHLC as a verified execution",()=>{
 const source="weekly_ml_daily_state/ledger.json";
 const make=(actions)=>({date:"2026-11-13",actions});
 const buy={ticker:"AAA",side:"buy",price:100,quantity:3,fee:0,
  reason:"Compra documentada",reason_basis:"recorded",evidence:source,
  signal_date:null,price_basis:"book_fill"};
 const sell={ticker:"AAA",side:"sell",price:108,quantity:3,fee:0,
  reason:"Cierre OHLC no observado",reason_basis:"recorded",evidence:source,
  signal_date:null,price_basis:"historical_week_close_proxy"};
 const blank=()=>({status:"no_executed_actions_documented",
  source_path:null,source_sha256:null,currency:"USD",sessions:[],prices:{},
  coverage:{executions:0,priced_executions:0,unpriced_executions:0,
   corporate_conversions:0,modelled_week_close_sales:0,
   ledger_actions_excluding_week_close_proxy:0}});
 const tracks=Object.fromEntries(Array.from({length:64},(_,i)=>
  ["IL-"+String(i+1).padStart(3,"0"),blank()]));
 tracks["IL-023"]={...blank(),status:"partial_executions_documented",
  source_path:source,sessions:[make([buy,sell])],
  coverage:{executions:2,priced_executions:2,unpriced_executions:0,
   corporate_conversions:0,modelled_week_close_sales:1,
   ledger_actions_excluding_week_close_proxy:1}};
 const doc={schema:"midas_operations_audit_v1",
  purpose:"read_only_paper_decision_evidence",asof:"2026-11-13",tracks};
 assert.equal(verifyOperationsAudit(doc).count,64);
 const report=summarizeOperationsAudit(doc);
 assert.equal(report.executions,1);
 assert.equal(report.modelledSales,1);
 assert.equal(report.totalLedgerActions,2);
 assert.equal(report.latestTrade,"2026-11-13");
 assert.deepEqual(buildSessionActionColumns(tracks["IL-023"])[0].sells,[]);
 assert.deepEqual(buildSessionActionColumns(tracks["IL-023"])[0].modelledSells,["AAA"]);
 const html=renderOperationsAudit(doc,"IL-023");
 assert.match(html,/VENTA SIMULADA · OHLC/);
 assert.match(html,/NO observadas/);
 assert.match(html,/audit-modelled-dot/);
 assert.match(html,/P\/L no certificable/);
 assert.doesNotMatch(html,/VENTA · CERRADA/);
 tracks["IL-023"].coverage.modelled_week_close_sales=0;
 assert.throws(()=>verifyOperationsAudit(doc),/Conteo de cierres OHLC simulados/);
});
