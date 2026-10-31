import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verify,signal,simulate,rank,valuation,thesisRank,absentQuote,cumulative,maxDrawdown,formatPct,syntheticBarsFromDemo,nextOpenPaper} from "../src/metrics.mjs";
const data=JSON.parse(readFileSync(new URL("../data/demo.json",import.meta.url),"utf8"));
test("The independent public universe is strictly synthetic",()=>{
 assert.equal(verify(data),true);
 assert.equal(data.meta.data_class,"synthetic");
 assert.equal(Object.keys(data.market).length,3);
 assert.equal(data.dates.length,48);
 assert.equal(data.strategies.length,23);
 assert.equal(data.theses.length,6);
});
test("Tampered source or missing price is rejected",()=>{
 assert.throws(()=>verify({...data,meta:{...data.meta,data_class:"private"}}));
 const corrupt=structuredClone(data);
 corrupt.market["SIM-B"][4]=null;
 assert.throws(()=>verify(corrupt));
 assert.equal(absentQuote(null,.5).executed,false);
 assert.equal(absentQuote(99,.5).executed,true);
});
test("Ranking simulates every method with finite positions and risk",()=>{
 const all=rank(data);
 assert.equal(all.length,23);
 for(const s of all){
  assert.equal(s.nav.length,48);
  assert.ok(s.nav.every(x=>Number.isFinite(x)&&x>0));
  assert.ok(Number.isFinite(s.returnPct)&&Number.isFinite(s.drawdownPct));
  assert.ok(Number.isFinite(s.fees)&&s.fees>=0);
  assert.ok(s.orders.every(x=>x.status==="SIMULATED"));
  assert.ok(s.weights.every(x=>Number.isFinite(x)&&x>=0));
  assert.ok(s.weights.reduce((a,b)=>a+b,0)<=1.000001);
  assert.ok(Math.abs(cumulative(s.nav)-s.returnPct)<1e-9);
 }
});
test("Signals cannot depend on later observations",()=>{
 const s=data.strategies.find(x=>x.mode==="trend");
 const baseline=simulate(data,s);
 const alternative=structuredClone(data);
 alternative.market["SIM-A"][47]=12345;
 const changed=simulate(alternative,s);
 assert.deepEqual(baseline.points.slice(0,-1),changed.points.slice(0,-1));
 assert.deepEqual(signal("rank",data.market,12),signal("rank",alternative.market,12));
});
test("Orders, liquidity and fees are internally coherent",()=>{
 const s=simulate(data,"P-01");
 assert.ok(s.orders.length>0);
 assert.ok(s.fees>0);
 assert.equal(simulate(data,"P-08").orders.length,0);
 assert.equal(simulate(data,"P-08").returnPct,0);
 assert.equal(simulate(data,"P-08").fees,0);
 assert.ok(Math.abs(maxDrawdown([100,110,88])-20)<1e-9);
});
test("Local manual paper weights are validated",()=>{
 const sample=structuredClone(data);
 sample.strategies.push({id:"P-24",name:"Local",group:"Local",mode:"manual",manualWeights:[.2,.3,.1],rule:"Manual",cost_bps:10});
 assert.equal(verify(sample),true);
 const result=simulate(sample,"P-24");
 assert.ok(result.orders.length>0);
 const bad=structuredClone(sample);
 bad.strategies.at(-1).manualWeights=[.7,.7,.7];
 assert.throws(()=>simulate(bad,"P-24"));
});
test("Thesis methods compute scenarios, ranks and filtered results",()=>{
 const t=valuation(data.theses[0]);
 assert.ok(t.valuation.bear.fair>0);
 assert.ok(t.valuation.bull.fair>t.valuation.bear.fair);
 assert.ok(Number.isFinite(t.central));
 assert.equal(thesisRank(data).length,6);
 assert.equal(thesisRank(data,"central","desc","Tecnología").length,1);
 assert.match(formatPct(0.47),/%/);
});
test("Navigation exposes all institutional functional sections",()=>{
 const js=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 for(const v of ["overview","competition","algorithms","theses","monitoring","method"])assert.ok(js.includes(v));
 assert.ok(html.includes('src="./src/site.mjs"'));
 assert.ok(js.includes("paper-form"));
 assert.ok(js.includes("journal-select"));
});


test("Next-open paper signals precede fills and cash remains collateralized",()=>{
 const bars=syntheticBarsFromDemo(data);
 const p=nextOpenPaper(bars,{rule:"equal",feeBps:10,slippageBps:5});
 assert.equal(p.status,"PAPER_SYNTHETIC_NEXT_OPEN");
 assert.equal(p.points.length,48);
 assert.ok(p.orders.length>0);
 assert.ok(p.orders.every(o=>o.status==="PAPER_NEXT_OPEN"));
 for(const order of p.orders){
  const signalIndex=data.dates.indexOf(order.signalAt);
  const fillIndex=data.dates.indexOf(order.fillAt);
  assert.equal(fillIndex,signalIndex+1);
  assert.equal(order.openPrice,bars.find(b=>b.symbol===order.symbol).bars[fillIndex].open);
  assert.ok(order.fillPrice>0&&order.fee>=0&&order.slippage>=0);
 }
 assert.ok(p.points.every(x=>x.cash>=0&&Number.isFinite(x.equity)&&x.equity>0));
 assert.ok(p.shares.every(x=>x>=0));
 assert.ok(p.fees>0&&p.slippage>0);
});
test("Next-open ledger rejects absent candles, missing open and inconsistent calendar",()=>{
 const valid=syntheticBarsFromDemo(data);
 for(const modify of [
  x=>x[0].bars[10].open=null,
  x=>x[0].bars[3].high=x[0].bars[3].low/2,
  x=>x[1].bars[10].session="OTHER",
  x=>x[1].bars.pop()
 ]){
  const bad=structuredClone(valid);
  modify(bad);
  assert.throws(()=>nextOpenPaper(bad,{rule:"trend"}));
 }
 assert.throws(()=>nextOpenPaper(valid,{feeBps:-1}));
 assert.throws(()=>nextOpenPaper(valid,{slippageBps:50}));
});
test("Changing a later close cannot change prior fills or equity",()=>{
 const original=syntheticBarsFromDemo(data);
 const modified=structuredClone(original);
 const last=modified[0].bars.at(-1);
 last.close*=1.18;
 last.high=Math.max(last.high,last.close)*1.01;
 const a=nextOpenPaper(original,{rule:"trend"});
 const b=nextOpenPaper(modified,{rule:"trend"});
 assert.deepEqual(a.orders,b.orders);
 assert.deepEqual(a.points.slice(0,-1),b.points.slice(0,-1));
 assert.notEqual(a.points.at(-1).equity,b.points.at(-1).equity);
});
test("Cash policy creates no fills and independent ledger does not overwrite old simulator",()=>{
 const bars=syntheticBarsFromDemo(data);
 const paper=nextOpenPaper(bars,{rule:"cash"});
 assert.equal(paper.orders.length,0);
 assert.equal(paper.returnPct,0);
 assert.equal(paper.points.at(-1).cash,data.meta.initialCapital);
 const legacy=simulate(data,"P-01");
 assert.ok(legacy.orders.every(o=>o.status==="SIMULATED"));
});
