import test from "node:test";
import assert from "node:assert/strict";
import {artificialMethodBars,methodCatalog} from "../src/paper-methods.mjs";
import {advancePaperCampaign,campaignRanking,validatePanel,artificialCampaignComparison} from "../src/paper-ledger.mjs";

const config=()=>({schema:1,currency:"USD",capital:100000,feeBps:10,
 slippageBps:5,investFraction:.95,maxPositions:1,
 strategies:[{id:"M-HOLD",method:"hold",symbols:["SIM-A"]}]});
const bars=artificialMethodBars();
const panel=(n,source=bars)=>({source:"generated_research_ohlc_v1",
 synthetic:true,currency:"USD",asOf:source[n-1].session,
 bars:{"SIM-A":source.slice(0,n).map(x=>({...x,volume:1000,dividend:0,split:0}))}});

test("First closing signal only queues; next session executes at next open with costs",()=>{
 const first=advancePaperCampaign(config(),panel(80));
 const book=first.state.portfolios["M-HOLD"];
 assert.equal(book.events.filter(x=>x.type==="FILL").length,0);
 assert.equal(book.orders["SIM-A"].side,"BUY");
 const next=advancePaperCampaign(config(),panel(81),first.state);
 const fill=next.state.portfolios["M-HOLD"].events.find(x=>x.type==="FILL");
 assert.equal(fill.signalAt,bars[79].session);
 assert.equal(fill.date,bars[80].session);
 assert.ok(fill.price>bars[80].open);
 assert.ok(next.state.portfolios["M-HOLD"].feeTotal>0);
 assert.ok(next.state.portfolios["M-HOLD"].cash>=0);
 assert.equal(campaignRanking(config(),next.state)[0].status,"SYNTHETIC_ONLY");
});
test("Same session identical panel idempotent; past bar corrections and skipped sessions forbidden",()=>{
 const first=advancePaperCampaign(config(),panel(80));
 const again=advancePaperCampaign(config(),panel(80),first.state);
 assert.equal(again.changed,false);
 assert.deepEqual(again.state,first.state);
 assert.throws(()=>advancePaperCampaign(config(),panel(82),first.state),/Missing daily decisions/);
 const faulty=panel(81);
 faulty.bars["SIM-A"][20].close*=1.01;
 assert.throws(()=>advancePaperCampaign(config(),faulty,first.state),/Historical OHLC revised/);
 const altered=config();altered.feeBps=25;
 assert.throws(()=>advancePaperCampaign(altered,panel(81),first.state),/Changed campaign/);
});
test("Corporate action events book a synthetic split and dividend without commingling cash",()=>{
 let first=advancePaperCampaign(config(),panel(80)).state;
 first=advancePaperCampaign(config(),panel(81),first).state;
 const modified=panel(82);
 modified.bars["SIM-A"][81].split=2;
 modified.bars["SIM-A"][81].dividend=.5;
 // split-adjusted price is in a different unit; keep OHLC valid.
 const res=advancePaperCampaign(config(),modified,first).state.portfolios["M-HOLD"];
 assert.ok(res.events.some(x=>x.type==="SPLIT"));
 assert.ok(res.events.some(x=>x.type==="DIVIDEND"));
 assert.ok(res.dividendTotal>0);
});
test("All nine policies can keep isolated accounts in the same synthetic campaign",()=>{
 const cfg={...config(),strategies:methodCatalog.map((x,i)=>({
  id:"M-"+String(i+10),method:x.id,symbols:["SIM-A"]}))};
 const first=advancePaperCampaign(cfg,panel(80)).state;
 const next=advancePaperCampaign(cfg,panel(81),first).state;
 const ranked=campaignRanking(cfg,next);
 assert.equal(ranked.length,9);
 assert.ok(ranked.every(x=>x.lastSession===bars[80].session));
 assert.ok(ranked.every(x=>x.currency===undefined&&x.status==="SYNTHETIC_ONLY"));
 assert.notEqual(next.portfolios["M-10"],next.portfolios["M-11"]);
 const source=panel(80);source.synthetic=false;
 assert.throws(()=>validatePanel(source),/Only labelled synthetic/);
});

test("Distinct synthetic index and eight-asset equal-weight holdings have independent cash",()=>{
 const run=artificialCampaignComparison();
 assert.equal(run.class,"ARTIFICIAL_REPLAY_NOT_PROSPECTIVE");
 assert.equal(run.symbols.length,9);
 assert.equal(run.ranking.length,9);
 const benchmark=run.config.strategies.find(x=>x.method==="benchmark");
 const equal=run.config.strategies.find(x=>x.method==="hold");
 assert.deepEqual(benchmark.symbols,["SIM-I"]);
 assert.equal(equal.symbols.length,8);
 assert.ok(equal.symbols.every(x=>x!=="SIM-I"));
 const benchmarkBook=run.state.portfolios[benchmark.id];
 const equalBook=run.state.portfolios[equal.id];
 assert.equal(benchmarkBook.events.filter(e=>e.type==="FILL"&&e.side==="BUY").length,1);
 assert.equal(equalBook.events.filter(e=>e.type==="FILL"&&e.side==="BUY").length,8);
 assert.ok(Math.abs(equalBook.cash-5000)<.1);
 assert.ok(Math.abs(benchmarkBook.cash-5000)<.1);
 assert.ok(run.ranking.every(x=>Number.isFinite(x.returnPct)));
 assert.ok(run.ranking.every(x=>x.status==="SYNTHETIC_ONLY"));
});
