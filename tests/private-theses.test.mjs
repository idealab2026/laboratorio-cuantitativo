import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {parseInstitutionalLocalArchive} from "../src/private-theses.mjs";

const allowed=new Set(["ZZZ","YYY","XXX"]);
const headers=["Ticker","Empresa","Última revisión","Estado documental recuperado",
 "Horizonte","CAGR Bear (%)","CAGR Base (%)","CAGR Bull (%)",
 "Escenario Bear original","Escenario Base original","Escenario Bull original"];
const row=(ticker="ZZZ",date="2026-10-29")=>[
 ticker,"Empresa simulada",date,"COMPLETA CON RESERVAS","FY2031",
 "-12,25%","+7,50%","+24,80%",
 "modelo histórico","no confundir con precio spot","escenario condicionado"];
const csv=rows=>[headers,...rows].map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(",")).join("\r\n");

test("Institutional local archive can be inspected locally but never becomes public data",()=>{
 const rows=parseInstitutionalLocalArchive(csv([row(),row("YYY","2026-10-28")]),allowed);
 assert.equal(rows.size,2);
 assert.equal(rows.get("ZZZ").base,7.5);
 assert.equal(rows.get("ZZZ").bear,-12.25);
 assert.equal(rows.get("ZZZ").bull,24.8);
 assert.equal(rows.get("YYY").date,"2026-10-28");
 assert.equal(Object.keys(rows.get("ZZZ")).sort().join(","),
              "base,bear,bull,date,horizon,status,ticker");
 const reader=readFileSync(new URL("../src/private-theses.mjs",import.meta.url),"utf8");
 assert.ok(!/fetch\s*\(|localStorage|sessionStorage|indexedDB|XMLHttpRequest|navigator\.sendBeacon/.test(reader));
});

test("Only issuer-matched, nonduplicated, time-stamped percentages are accepted",()=>{
 assert.throws(()=>parseInstitutionalLocalArchive(csv([row("FAKE!")]),allowed));
 assert.throws(()=>parseInstitutionalLocalArchive(csv([row(),row()]),allowed));
 assert.throws(()=>parseInstitutionalLocalArchive(csv([row("ZZZ","2026-99-99")]),allowed));
 const bad=row();bad[6]="1.02e99%";
 assert.throws(()=>parseInstitutionalLocalArchive(csv([bad]),allowed));
 assert.throws(()=>parseInstitutionalLocalArchive(csv([]),allowed));
});

test("Semicolon separated exported European decimal percentages are readable",()=>{
 const lines=[headers,row()];
 const data=lines.map(r=>r.join(";")).join("\n");
 const out=parseInstitutionalLocalArchive(data,allowed);
 assert.equal(out.get("ZZZ").base,7.5);
 assert.equal(out.get("ZZZ").bull,24.8);
});

test("The local archive viewer never ships private records or sends uploads",()=>{
 const html=readFileSync(new URL("../private-theses.html",import.meta.url),"utf8");
 const js=readFileSync(new URL("../src/private-theses-view.mjs",import.meta.url),"utf8");
 assert.ok(html.includes('id="private-file"'));
 assert.ok(html.includes("private-theses-view.mjs"));
 assert.ok(js.includes("parseInstitutionalLocalArchive"));
 assert.ok(js.includes("file.text()"));
 assert.ok(js.includes("replaceChildren"));
 assert.ok(!/fetch\s*\(|localStorage|sessionStorage|indexedDB|XMLHttpRequest|navigator\.sendBeacon/.test(js));
});

test("CAGR2031 private Sheet export overlays only historical numeric scenarios",async()=>{
 const {parseLocalCagr2031}=await import("../src/private-theses.mjs");
 const h="ticker,empresa,fecha_estudio,cagr_bear_2031,cagr_base_2031,cagr_bull_2031,estado";
 const d=h+"\nEXA,Example A,2026-10-29,\"−12,25%\",\"+7,50%\",\"+24,80%\",VALORADA"+
 "\nEXB,Example B,2026-10-12,,, ,PENDIENTE";
 const map=parseLocalCagr2031(d,new Set(["EXA","EXB"]));
 assert.equal(map.get("EXA").base,7.5);
 assert.equal(map.get("EXA").bull,24.8);
 assert.equal(map.get("EXB").base,null);
 assert.throws(()=>parseLocalCagr2031(d,new Set(["EXA"])));
 assert.throws(()=>parseLocalCagr2031(h+"\nEXA,Example A,2026-10-29,10,15,25,A\nEXA,Example A,2026-10-29,10,15,25,B",new Set(["EXA"])));
});
test("Public site never hardcodes canonical private CAGR values",()=>{
 const code=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(!code.includes('id="cagr-file"'),"El comparador CSV está oculto de la vista pública");
 assert.ok(code.includes("parseLocalCagr2031"));
 assert.ok(!code.includes("−12,25%"));
});

test("Published issuer data and optional local override coexist",()=>{
 const source=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(source.includes("function issuerReadRows()"));
 assert.ok(source.includes("publicThesisTableRows"));
 assert.ok(source.includes("publicThesisCsv"));
});
test("Import surface excludes external telemetry and uses an origin-constrained CSP",()=>{
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 assert.match(html,/script-src 'self'/);
 assert.match(html,/connect-src 'self'/);
 assert.ok(!html.includes("static.cloudflareinsights.com"));
 assert.ok(!html.includes("data-cf-beacon"));
});

test("Reviewed historical research is rendered without inventing absent values or accepting private links",async()=>{
 const {verifyPublicTheses,publicResearchRows,publicThesisCsv,publicThesisTableRows}=await import("../src/public-theses.mjs");
 const doc=JSON.parse(readFileSync(new URL("../data/public-theses.json",import.meta.url),"utf8"));
 assert.deepEqual(verifyPublicTheses(doc),{count:25,withCagr:9,withPrice:7});
 const records=new Map(doc.records.map(r=>[r.ticker,r])),rows=publicResearchRows([],records);
 assert.equal(rows.length,25);assert.equal(publicThesisCsv(rows,records,new Map()).length,26);
 assert.equal((publicThesisTableRows(rows,records,new Map(),"MSFT").match(/<tr /g)||[]).length,25);
 assert.equal(publicResearchRows([],records,{query:"Caterpillar"})[0].issuer.ticker,"CAT");
 for(const edit of [r=>{r.summary="https://invalid.example"},r=>{r.account="secret"}]){const bad=structuredClone(doc);edit(bad.records[0]);assert.throws(()=>verifyPublicTheses(bad));}
 assert.throws(()=>verifyPublicTheses({...doc,records:[...doc.records,doc.records[0]]}));
 const pending=doc.records.find(r=>r.baseCagr===null);const row=publicThesisCsv([{issuer:{ticker:pending.ticker},screen:{scenarios:{base:{cagrPct:99}}}}],records,new Map())[1];assert.equal(row[9],"N/D");
});


test("The public issuer table and CSV keep independently evaluated screens when the historic publication is empty",async()=>{
 const {publicIssuerReadModel}=await import("../src/metrics.mjs");
 const {publicThesisTableRows,publicThesisCsv,orderedThesisRows}=await import("../src/public-theses.mjs");
 const data=JSON.parse(readFileSync(new URL("../data/demo.json",import.meta.url),"utf8"));
 const rows=publicIssuerReadModel(data.issuerCatalog),s=rows.find(r=>r.screen).screen;
 const csv=publicThesisCsv(rows,new Map(),new Map());
 const valued=csv.find(row=>row[0]==="MSFT"),pending=csv.find(row=>row[0]==="RKLB");
 assert.equal(valued[3],s.quote.close);
 assert.equal(valued[4],s.quote.closeDate);
 assert.equal(valued[9],s.scenarios.base.cagrPct);
 assert.equal(valued[10],s.buyPrice15);
 assert.equal(valued[12],"Screening exploratorio");
 assert.equal(pending[3],"N/D");
 const html=publicThesisTableRows(rows,new Map(),new Map(),"MSFT");
 assert.ok(html.includes("2026-10-30"));
 assert.ok(html.includes("Screening exploratorio"));
 for(const ascending of [true,false]){
  assert.equal(orderedThesisRows([...rows],new Map(),new Map(),"base",ascending)[0].issuer.ticker,"MSFT");
 }
 const local=new Map([["MSFT",{bear:null,base:4,bull:6,date:"2020-01-01"}]]);
 const historical=publicThesisCsv(rows,new Map(),local).find(row=>row[0]==="MSFT");
 assert.equal(historical[9],4);
 assert.equal(historical[8],"N/D");
 assert.equal(historical[3],"N/D");
 assert.equal(historical[10],"N/D");
 assert.equal(historical[12],"Archivo local");
});


test("The served module URLs change with the exact issuer-rendering code",async()=>{
 const {createHash}=await import("node:crypto");
 const digest=path=>createHash("sha256").update(readFileSync(new URL(path,import.meta.url))).digest("hex").slice(0,12);
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(html.includes('src="./src/site.mjs?v='+digest("../src/site.mjs")+'"'));
 assert.ok(site.includes('"./public-theses.mjs?v='+digest("../src/public-theses.mjs")+'"'));
});

test("Thesis tracking never embeds a company fiche and supports independent ticker navigation",async()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 const from=site.indexOf("function theses(){"),to=site.indexOf("function thesisView(){",from);
 assert.ok(from>=0&&to>from);
 const tracking=site.slice(from,to);
 assert.ok(tracking.includes("issuerTableRows()"));
 assert.ok(!tracking.includes("issuerDetail("));
 assert.ok(!tracking.includes('id="issuer-ficha"'));
 assert.ok(!tracking.includes("Ficha de tesis / empresa"));
 const detail=site.slice(to,site.indexOf("function officialFxPanel(){",to));
 assert.ok(detail.includes("issuerDetail(requested)"));
 assert.ok(detail.includes('new URLSearchParams(location.search).get("ticker")'));
 assert.ok(site.includes('window.open(url,"_blank","noopener,noreferrer")'));
 assert.ok(site.includes('thesis:thesisView'));
 const {publicThesisTableRows}=await import("../src/public-theses.mjs");
 const records=new Map([["MSFT",{ticker:"MSFT",company:"Microsoft",market:"NASDAQ",theme:"Software",currency:"USD",thesisStatus:"Revisada",valuationStatus:"Revisada",studyDate:"2026-10-13"}]]);
 const html=publicThesisTableRows([{issuer:{ticker:"MSFT",company:"Microsoft",market:"NASDAQ",currency:"USD",sector:"Software"},screen:null}],records,new Map(),null);
 assert.ok(html.includes('href="./index.html?view=thesis&amp;ticker=MSFT"'));
 assert.ok(html.includes('target="_blank" rel="noopener noreferrer"'));
 assert.ok(!html.includes('data-action="issuer-select"'));
});


test("Last-close feed refuses unlicensed or future stock quotes and preserves thesis historical prices",async()=>{
 const {verifyPublicCloseFeed,publicThesisTableRows}=await import("../src/public-theses.mjs");
 const allowed=new Set(["MSFT"]);
 const now=Date.parse("2026-11-05T16:00:00Z");
 const stub=JSON.parse(readFileSync(new URL("../data/public-closes.json",import.meta.url),"utf8"));
 const pending=verifyPublicCloseFeed(stub,allowed,now);
 assert.equal(pending.status,"not_configured");
 assert.equal(pending.quotes.size,0);
 const source={name:"Licensed provider",url:"https://example.org/reference",display_rights:"confirmed_public_redistribution"};
 const base={schema:"midas.public_closes.v1",status:"verified",source,collected_at:"2026-11-05T15:00:00Z",
  quotes:[{ticker:"MSFT",session:"2026-11-04",close:543.21,currency:"USD"}]};
 const accepted=verifyPublicCloseFeed(base,allowed,now);
 assert.equal(accepted.quotes.get("MSFT").close,543.21);
 for(const bad of [
  {...base,source:{...source,display_rights:"personal_only"}},
  {...base,quotes:[{ticker:"MSFT",session:"2026-11-06",close:543.21,currency:"USD"}]},
  {...base,quotes:[{ticker:"FAKE",session:"2026-11-04",close:543.21,currency:"USD"}]},
  {...base,quotes:[{ticker:"MSFT",session:"2026-11-04",close:0,currency:"USD"}]},
  {...stub,quotes:base.quotes}
 ])assert.throws(()=>verifyPublicCloseFeed(bad,allowed,now));
 const record={ticker:"MSFT",company:"Microsoft",market:"NASDAQ",currency:"USD",theme:"Software",
  recordedPrice:526.30,priceDate:"2026-10-07",referencePrice:526.30,baseCagr:-.9};
 const rows=[{issuer:{ticker:"MSFT",company:"Microsoft",market:"NASDAQ",currency:"USD",sector:"Software"},screen:null}];
 const records=new Map([["MSFT",record]]);
 const absent=publicThesisTableRows(rows,records,new Map(),null);
 assert.match(absent,/Sin cierre público verificado/);
 assert.doesNotMatch(absent,/526,30/);
 const verified=publicThesisTableRows(rows,records,new Map(),null,accepted.quotes);
 assert.match(verified,/543,21/);
 assert.match(verified,/Cierre 2026-11-04/);
 assert.doesNotMatch(verified,/526,30/);
 const css=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
 assert.match(css,/\.thesis-public-table table\{table-layout:fixed/);
 assert.match(css,/\.thesis-public-table td:last-child \.smallbtn\{display:inline-flex/);
 assert.match(css,/\.thesis-public-table \.thesis-earnings\{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis/);
});
