import test from "node:test";
import assert from "node:assert/strict";
import {methodCatalog,signalAtClose,artificialMethodBars,signalResearchSummary} from "../src/paper-methods.mjs";

test("Nine independent paper policies produce reproducible artificial close-only signals",()=>{
 const report=signalResearchSummary();
 assert.equal(methodCatalog.length,9);
 assert.equal(report.methods.length,9);
 assert.equal(report.sessions,130);
 assert.equal(report.source,"generated_no_market_data");
 assert.equal(report.status,"ARTIFICIAL_SIGNALS_NO_EXECUTION");
 assert.ok(report.methods.every(x=>x.recentBuy+x.recentSell+x.recentHold===30));
 assert.ok(report.methods.every(x=>["BUY","SELL","HOLD"].includes(x.currentSignal)));
 assert.deepEqual(report,signalResearchSummary());
});
test("Signals ignore all future bars, without knowing the next session opening",()=>{
 const bars=artificialMethodBars();
 for(const m of methodCatalog){
  const prefix=bars.slice(0,120),first=signalAtClose(m.id,prefix);
  const next=bars.slice(0,121);
  next[120]={...next[120],open:1e10,close:1e10,high:1e10,low:1e10};
  assert.equal(first,signalAtClose(m.id,next.slice(0,120)),m.id);
 }
});
test("Input contracts reject unknown policy and invalid closing observations",()=>{
 const bars=artificialMethodBars();
 assert.throws(()=>signalAtClose("unapproved-model",bars),/Unrecognized/);
 assert.throws(()=>signalAtClose("hold",[{close:NaN}]),/Invalid/);
 const sample=bars.slice(0,15);
 assert.equal(signalAtClose("breakout55",sample),"HOLD");
 assert.equal(signalAtClose("macd",sample),"HOLD");
 assert.equal(signalAtClose("emaRsi",sample),"HOLD");
});
test("Public research UI maintains distinct ported-method diagnostics and no execution claims",async()=>{
 const {readFileSync}=await import("node:fs");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(site.includes('function ported(){'));
 assert.ok(site.includes('const pages={overview,competition,synthetic:syntheticCompetition,algorithms,theses,monitoring,archive,ported'));
 assert.ok(site.includes("Carteras en replay artificial"));
 assert.ok(site.includes("Solo regla · sin órdenes"));
 assert.ok(site.includes("paperAccountingView()"));
 assert.ok(site.includes("paper-select"));
});
