import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verify,signal,simulate,rank,valuation,thesisRank,absentQuote,cumulative,maxDrawdown,formatPct,syntheticBarsFromDemo,nextOpenPaper,verifyIssuerCatalog,evaluateIssuerScreen,competitionReadModel,publicIssuerReadModel,verifyOfficialFx,summarizeFxForecastLedger,verifySecFilings,verifyOfficialYield} from "../src/metrics.mjs";
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


test("Only SEC-verified issuers expose source identifiers",()=>{
 const issuers=data.issuerCatalog.issuers;
 const verified=issuers.filter(x=>x.secCik);
 assert.equal(verified.length,8);
 assert.ok(verified.every(x=>/^\d{10}$/.test(x.secCik)));
 const tampered=structuredClone(data.issuerCatalog);
 tampered.issuers[0].secCik="malicious/redirect";
 assert.throws(()=>verifyIssuerCatalog(tampered),/Invalid source registry/);
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(src.includes("www.sec.gov/edgar/browse/?CIK="));
 assert.ok(src.includes('rel="noopener noreferrer"'));
 assert.ok(src.includes("Exportar libro causal CSV"));
 assert.ok(src.includes("Ejecución paper en apertura siguiente"));
});


test("First issuer screen uses independently sourced dated EPS and last observed close",()=>{
 const s=data.issuerCatalog.publicScreens[0];
 assert.equal(s.ticker,"MSFT");
 assert.equal(s.status,"EXPLORATORY_NOT_RATIFIED");
 assert.equal(s.quote.closeDate,"2026-10-30");
 assert.equal(s.quote.close,521.91);
 assert.equal(s.metric.adjustedEpsFY2026,17.28);
 const v=evaluateIssuerScreen(s);
 assert.ok(Math.abs(v.scenarios.bear.target-484.72)<.02);
 assert.ok(Math.abs(v.scenarios.base.target-859.61)<.02);
 assert.ok(Math.abs(v.scenarios.bull.target-1344.10)<.02);
 assert.ok(Math.abs(v.buyPrice15-427.38)<.03);
 assert.ok(v.scenarios.bear.cagrPct<0);
 assert.ok(v.scenarios.base.cagrPct>0&&v.scenarios.base.cagrPct<15);
 assert.equal(verifyIssuerCatalog(data.issuerCatalog),true);
});
test("Unverified screen tampering cannot silently inject financial claims",()=>{
 for(const modify of [
  s=>s.quote.close=null,
  s=>s.quote.source="https://example.org/unsourced",
  s=>s.status="APPROVED",
  s=>s.assumptions.bull.terminalPe=100,
  s=>s.metric.adjustedEpsFY2026=-10
 ]){
  const altered=structuredClone(data.issuerCatalog);
  modify(altered.publicScreens[0]);
  assert.throws(()=>verifyIssuerCatalog(altered));
 }
});


test("Competition read-model contains same synthetic campaign count and is row-sortable",()=>{
 const rows=competitionReadModel(data);
 assert.equal(rows.length,23);
 assert.ok(rows.every(r=>r.experimentStatus==="SIMULACION_SINTETICA"));
 assert.ok(rows.every(r=>r.executionVerified===false&&r.marketDataVerified===false));
 assert.ok(rows.every(r=>r.sessions===48&&r.lastSession==="S48"));
 assert.ok(rows.every(r=>r.activeAssets.every(k=>Object.keys(data.market).includes(k))));
 for(let i=1;i<rows.length;i++)assert.ok(rows[i-1].returnPct>=rows[i].returnPct);
 assert.deepEqual(competitionReadModel(data,{sort:"name",ascending:true}).map(x=>x.name),
  [...rows].map(x=>x.name).sort((a,b)=>a.localeCompare(b,"es",{numeric:true,sensitivity:"base"})));
 assert.throws(()=>competitionReadModel(data,{sort:"secret"}),/Unsupported/);
});
test("Competition windows measure 5 and 21 comparable artificial sessions only",()=>{
 const row=competitionReadModel(data).find(r=>r.id==="P-01");
 const nav=row.nav;
 const calc=n=>100*(nav.at(-1)/nav.at(-1-n)-1);
 assert.ok(Math.abs(row.periodReturns.five-calc(5))<1e-9);
 assert.ok(Math.abs(row.periodReturns.twentyOne-calc(21))<1e-9);
 assert.equal(row.periodReturns.sixtyThree,null);
 assert.ok(Math.abs(row.dayReturnPct-calc(1))<1e-9);
 const shorter=structuredClone(data);
 shorter.dates=shorter.dates.slice(0,20);
 for(const k of Object.keys(shorter.market))shorter.market[k]=shorter.market[k].slice(0,20);
 const sample=competitionReadModel(shorter)[0];
 assert.equal(sample.periodReturns.twentyOne,null);
 assert.equal(sample.periodReturns.sixtyThree,null);
});
test("Public company sorting keeps unknown values last and returns only approved screen metrics",()=>{
 const rows=publicIssuerReadModel(data.issuerCatalog);
 assert.equal(rows.length,25);
 assert.equal(rows[0].issuer.ticker,"MSFT");
 assert.ok(rows[0].screen.scenarios.base.cagrPct>0);
 assert.ok(rows.slice(1).every(r=>r.screen===null));
 const ascending=publicIssuerReadModel(data.issuerCatalog,{sort:"base",ascending:true});
 assert.equal(ascending[0].issuer.ticker,"MSFT");
 assert.ok(ascending.slice(1).every(r=>r.screen===null));
 const negative=publicIssuerReadModel(data.issuerCatalog,{sort:"bear"});
 assert.equal(negative[0].issuer.ticker,"MSFT");
 assert.deepEqual(publicIssuerReadModel(data.issuerCatalog,{query:"Cloudflare"}).map(x=>x.issuer.ticker),["NET"]);
 assert.deepEqual(publicIssuerReadModel(data.issuerCatalog,{query:"not-a-company"}),[]);
 assert.throws(()=>publicIssuerReadModel(data.issuerCatalog,{sort:"personal_document"}),/Unsupported/);
});
test("Institutional UI offers row inspection, column sorting, historic isolation and honest source health",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 for(const text of ["data-competition-id","data-issuer-id","rank-column","issuer-column","openCompetitionRow","openIssuerRow","close-detail","function archive()","Sin histórico institucional importado","Sin alimentación real","Última sesión ficticia","Sin verificación operativa"]){
  assert.ok(src.includes(text),text);
 }
 for(const label of ["Competición de algoritmos","Seguimiento de tesis","Catálogo / histórico"]){
  assert.ok(html.includes(label),label);
 }
 assert.ok(css.includes(".interactive-table-row:focus-visible"));
 assert.ok(src.includes("periodReturns")); // Only synthetic NAV windows; no claim of actual trading sessions.
});


function exampleOfficialFx(){
 const observations=[];
 for(let t=Date.UTC(2026,9,1);t<=Date.UTC(2026,9,30);t+=86400000){
  const date=new Date(t);
  if(date.getUTCDay()>=1&&date.getUTCDay()<=5)
   observations.push({date:date.toISOString().slice(0,10),usd_per_eur:(1.12+observations.length/10000).toFixed(4)});
 }
 return {
  status:"verified_observations",data_class:"official_fx_reference_only",series:"D.USD.EUR.SP00.A",
  quote_currency:"USD",base_currency:"EUR",source:"European Central Bank (ECB statistics)",
  source_url:"https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=80&format=csvdata",
  source_sha256:"a".repeat(64),received_at_utc:"2026-10-31T14:00:00Z",latest_observation:"2026-10-30",
  count:observations.length,not_tradable:true,
  notice:"ECB reference rate: US dollars per one euro, NOT a transaction, bid/ask, open or close.",
  observations};
}
test("Official ECB observations retain dated provenance without implying executable prices",()=>{
 const doc=exampleOfficialFx(),result=verifyOfficialFx(doc,new Date("2026-10-31T15:00:00Z"));
 assert.equal(result.referenceOnly,true);
 assert.equal(result.ageDays,1);
 assert.equal(result.date,"2026-10-30");
 assert.equal(result.count,22);
 assert.ok(result.rate>=1.12);
});
test("Official FX validator rejects altered source, weekend, future values and stale provenance",()=>{
 const example=exampleOfficialFx();
 for(const modify of [
  x=>{x.source_url="https://fake.test/rates";},
  x=>{x.not_tradable=false;},
  x=>{x.count++;},
  x=>{x.observations[2].usd_per_eur="0.0001";},
  x=>{x.observations[2].date="2026-12-30";},
  x=>{x.observations[2].date="2026-10-03";},
  x=>{x.observations[2].date=x.observations[1].date;},
  x=>{x.received_at_utc="2027-01-01T00:00:00Z";},
 ]){
  const doc=structuredClone(example);modify(doc);
  assert.throws(()=>verifyOfficialFx(doc,new Date("2026-10-31T15:00:00Z")));
 }
});
test("ECB observatory is displayed separately from the preexisting synthetic strategy competition",()=>{
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(src.includes("function officialFxPanel()"));
 assert.ok(src.includes("loadOfficialFx()"));
 assert.ok(src.includes('fetch("./data/official-fx.json"'));
 assert.ok(src.includes("Esta serie NO alimenta todavía los 23 modelos paper"));
 assert.ok(src.includes("Sin alimentación real")); // Equity OHLC must remain clearly unavailable.
 const workflow=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(workflow.includes("cron: '25 18 * * 1-5'"));
 assert.ok(workflow.includes("refresh_ecb.py --validate"));
});


test("First actual issued signal is explicitly invalidated rather than scored",()=>{
 const ledger=JSON.parse(readFileSync(new URL("../data/fx-forecast-ledger.json",import.meta.url),"utf8"));
 const result=summarizeFxForecastLedger(ledger);
 assert.equal(result.issuedCount,1);
 assert.equal(result.validCount,0);
 assert.equal(result.invalidatedCount,1);
 assert.equal(result.resolvedCount,0);
 assert.equal(result.unresolvedCount,0);
 assert.ok(result.rows[0].invalidated);
 assert.equal(result.headHash,ledger.events.at(-1).hash);
});
test("Prospective forecast evaluation uses realized next reference, not paper P&L",()=>{
 const obj=JSON.parse(readFileSync(new URL("../data/fx-forecast-ledger.json",import.meta.url),"utf8"));
 obj.events=[]; // Deliberately isolated mathematical fixture; never alter the canonical record.
 const stamp="2026-10-31T15:10:00Z",a="a".repeat(64),b="b".repeat(64);
 obj.events.push({event_type:"issued",fixing_date:"2026-10-30",recorded_at_utc:stamp,
  observed_rate:"1.1500",predictions:{unchanged:"1.150000",momentum_1:"1.151000",reversal_1:"1.149000"},
  source_sha256:"d".repeat(64),previous_hash:"0".repeat(64),hash:a});
 obj.events.push({event_type:"resolved",fixing_date:"2026-10-30",realized_fixing_date:"2026-11-02",
  recorded_at_utc:"2026-11-02T18:00:00Z",realized_rate:"1.1505",signal_hash:a,
  absolute_errors:{unchanged:"0.000500",momentum_1:"0.000500",reversal_1:"0.001500"},
  source_sha256:"c".repeat(64),previous_hash:a,hash:b});
 let stats=summarizeFxForecastLedger(obj);
 assert.equal(stats.issuedCount,1);
 assert.equal(stats.resolvedCount,1);
 assert.equal(stats.unresolvedCount,0);
 assert.equal(stats.invalidatedCount,0);
 assert.ok(Math.abs(stats.modelMAE.reversal_1-.0015)<1e-12);
 assert.equal(stats.headHash,b);
 obj.events[1].previous_hash="f".repeat(64);
 assert.throws(()=>summarizeFxForecastLedger(obj),/lineage/);
});
test("Official independent forecast journal is scheduled and available as an audited static artifact",()=>{
 const yaml=readFileSync(new URL("../.github/workflows/fx-ledger.yml",import.meta.url),"utf8");
 const pages=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(yaml.includes("contents: write"));
 assert.ok(yaml.includes("cron: '40 17 * * 1-5'"));
 assert.ok(yaml.includes("Record audited prospective ECB fixing signal"));
 assert.ok(yaml.includes("PYTHONDONTWRITEBYTECODE"));
 assert.ok(pages.includes("cp data/demo.json data/fx-forecast-ledger.json data/sec-filings.json data/competition-roster.json dist/data/"));
 assert.ok(site.includes("function prospectiveForecastPanel()"));
 assert.ok(site.includes('fetch("./data/fx-forecast-ledger.json"'));
 assert.ok(site.includes("No son operaciones financieras"));
});


test("A reversed-rate signal cannot be scored without immutable invalidation",()=>{
 const fixture=JSON.parse(readFileSync(new URL("../data/fx-forecast-ledger.json",import.meta.url),"utf8"));
 const clone=structuredClone(fixture);
 clone.events.pop();
 assert.throws(()=>summarizeFxForecastLedger(clone),/explicitly invalidated/);
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(site.includes("ANULADA · error de fórmula"));
 assert.ok(site.includes("summary.invalidatedCount"));
});


test("Public SEC catalog is source-checked whether pending or successfully collected",()=>{
 const doc=JSON.parse(readFileSync(new URL("../data/sec-filings.json",import.meta.url),"utf8"));
 const result=verifySecFilings(doc,data.issuerCatalog);
 if(doc.status==="not_collected"){
  assert.equal(result.status,"not_collected");
  assert.equal(result.count,0);
  assert.equal(result.byTicker.size,0);
 }else{
  assert.equal(result.status,"verified_filings");
  assert.equal(result.byTicker.size,8);
  assert.ok(result.count>=16);
 }
});
test("Issuer source display cannot accept foreign links or fictitious document metadata",()=>{
 const issuerData=data.issuerCatalog;
 const doc=JSON.parse(readFileSync(new URL("../data/sec-filings.json",import.meta.url),"utf8"));
 const tickerSet=issuerData.issuers.filter(i=>i.secCik);
 const records=tickerSet.map(i=>{
  const accession=i.secCik+"-26-000001",document="report.htm";
  const path="https://www.sec.gov/Archives/edgar/data/"+Number(i.secCik)+"/"+accession.replaceAll("-","")+"/"+document;
  const filing={form:"10-K",accession,filed:"2026-08-01",report_date:"2026-06-30",primary_document:document,url:path};
  const quarter={...filing,form:"10-Q",accession:i.secCik+"-26-000002",
   filed:"2026-10-30",report_date:"2026-09-30",
   url:"https://www.sec.gov/Archives/edgar/data/"+Number(i.secCik)+"/"+(i.secCik+"-26-000002").replaceAll("-","")+"/"+document};
  return {ticker:i.ticker,cik:i.secCik,sec_name:i.company,source_url:"https://data.sec.gov/submissions/CIK"+i.secCik+".json",
   source_sha256:"a".repeat(64),retrieved_at_utc:"2026-10-31T16:00:00Z",filings:[quarter,filing]};
 });
 const valid={...doc,status:"verified_filings",generated_at_utc:"2026-10-31T16:00:00Z",issuers:records};
 const result=verifySecFilings(valid,issuerData);
 assert.equal(result.byTicker.size,8);
 assert.equal(result.count,16);
 for(const modify of [
  v=>{v.issuers[0].filings[0].url="https://untrusted.example/false";},
  v=>{v.issuers[0].cik="0000000000";},
  v=>{v.issuers[0].filings[0].form="ANALYST";},
  v=>{v.issuers.pop();},
 ]){const altered=structuredClone(valid);modify(altered);assert.throws(()=>verifySecFilings(altered,issuerData));}
 const src=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(src.includes("function secSourcePanel("));
 assert.ok(src.includes('fetch("./data/sec-filings.json"'));
 assert.ok(src.includes("No se han auditado automáticamente las cifras contables"));
});


test("Verified ECB euro AAA 10Y observations cannot be confused with stock valuations",()=>{
 const values=[];
 for(let t=Date.UTC(2026,9,1);t<=Date.UTC(2026,9,30);t+=86400000){
  const day=new Date(t);
  if(day.getUTCDay()>=1&&day.getUTCDay()<=5)
   values.push({date:day.toISOString().slice(0,10),yield_pct:(3.1+values.length/100).toFixed(6)});
 }
 const doc={status:"verified_ecb_macro_observations",data_class:"official_aaa_euro_10y_spot_yield",
  series:"B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",source:"European Central Bank (ECB statistics)",
  source_url:"https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=60&format=csvdata",
  raw_sha256:"e".repeat(64),received_at_utc:"2026-10-31T16:00:00Z",
  latest_date:"2026-10-30",count:values.length,unit:"percent_per_annum",
  notice:"Euro area AAA government 10-year modelled spot yield, percent per annum, continuously compounded. Not a security quote, guaranteed risk-free rate, or automatic DCF assumption.",
  observations:values};
 const observed=verifyOfficialYield(doc,new Date("2026-10-31T16:05:00Z"));
 assert.equal(observed.ageDays,1);
 assert.equal(observed.date,"2026-10-30");
 assert.ok(observed.ratePct>3);
 for(const change of [
  x=>{x.unit="USD";},x=>{x.series="EXR";},x=>{x.count+=1;},
  x=>{x.observations[0].yield_pct="30.000000";},
  x=>{x.observations[0].date="2026-10-03";},
  x=>{x.raw_sha256="invalid";}
 ]){const bad=structuredClone(doc);change(bad);assert.throws(()=>verifyOfficialYield(bad,new Date("2026-10-31T16:05:00Z")));}
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(site.includes("function officialYieldPanel()"));
 assert.ok(site.includes("loadOfficialYield()"));
 assert.ok(site.includes("NO se introduce automáticamente"));
 const flow=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(flow.includes("refresh_ecb_yield.py --validate"));
});
