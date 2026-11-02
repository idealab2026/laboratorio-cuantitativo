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
 assert.ok(code.includes('id="cagr-file"'));
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

test("Public package excludes historical thesis fingerprints and rejects their reintroduction",async()=>{
 const {verifyPublicTheses,orderedThesisRows,publicThesisCsv}=await import("../src/public-theses.mjs");
 const doc=JSON.parse(readFileSync(new URL("../data/public-theses.json",import.meta.url),"utf8"));
 assert.deepEqual(verifyPublicTheses(doc),{count:0,withCagr:0,withPrice:0});
 assert.deepEqual(doc.records,[]);
 assert.throws(()=>verifyPublicTheses({...doc,data_class:"author_approved_public_research_snapshot"}));
 assert.throws(()=>verifyPublicTheses({...doc,records:[{ticker:"EXAMPLE",baseCagr:1.234}]}));
 const rows=[{issuer:{ticker:"EXA",company:"Example A",market:"TEST"}}];
 const csv=publicThesisCsv(rows,new Map(),new Map());
 assert.equal(csv.length,2);
 assert.equal(csv[1][3],"N/D");
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.match(site,/archivo privado/);
 assert.doesNotMatch(site,/25 fichas y nueve CAGR/);
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
