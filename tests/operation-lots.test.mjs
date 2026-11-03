import test from "node:test";
import assert from "node:assert/strict";
import {buildOperationLots,sortOperationLots} from "../src/operation-lots.mjs";
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
