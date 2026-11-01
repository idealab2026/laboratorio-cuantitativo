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
 const d=h+"\nMSFT,Microsoft,2026-10-29,\"−16,50%\",\"−0,90%\",\"+13,74%\",VALORADA"+
 "\nPLTR,Palantir,2026-10-12,,, ,PENDIENTE";
 const map=parseLocalCagr2031(d,new Set(["MSFT","PLTR"]));
 assert.equal(map.get("MSFT").base,-.9);
 assert.equal(map.get("MSFT").bull,13.74);
 assert.equal(map.get("PLTR").base,null);
 assert.throws(()=>parseLocalCagr2031(d,new Set(["MSFT"])));
 assert.throws(()=>parseLocalCagr2031(h+"\nMSFT,Microsoft,2026-10-29,10,15,25,A\nMSFT,Microsoft,2026-10-29,10,15,25,B",new Set(["MSFT"])));
});
test("Public site never hardcodes canonical private CAGR values",()=>{
 const code=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(code.includes('id="cagr-file"'));
 assert.ok(code.includes("parseLocalCagr2031"));
 assert.ok(!code.includes("−16,50%"));
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

test("Published historical research uses only author-approved public issuer extracts",async()=>{
 const {verifyPublicTheses,orderedThesisRows,publicThesisCsv}=await import("../src/public-theses.mjs");
 const doc=JSON.parse(readFileSync(new URL("../data/public-theses.json",import.meta.url),"utf8"));
 const stats=verifyPublicTheses(doc);
 assert.deepEqual(stats,{count:25,withCagr:9,withPrice:7});
 const map=new Map(doc.records.map(r=>[r.ticker,r]));
 assert.equal(map.get("ADBE").baseCagr,17.26);
 assert.equal(map.get("META").baseTarget,585.72);
 assert.equal(map.get("MSFT").baseCagr,-.9);
 assert.equal(map.get("AMZN").baseCagr,null);
 const ordered=orderedThesisRows([{issuer:{ticker:"MSFT"}},{issuer:{ticker:"ADBE"}},{issuer:{ticker:"META"}}],map,new Map(),"base",false);
 assert.deepEqual(ordered.map(x=>x.issuer.ticker),["ADBE","MSFT","META"]);
 assert.equal(publicThesisCsv(ordered,map,new Map()).length,4);
 assert.throws(()=>verifyPublicTheses({...doc,records:doc.records.map((r,i)=>i? r:{...r,summary:"https://example.org/private"})}));
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.match(site,/fetch\("\.\/data\/public-theses\.json"/);
 assert.match(site,/publicThesisTableRows/);
 const wf=readFileSync(new URL("../.github/workflows/pages.yml",import.meta.url),"utf8");
 assert.ok(wf.includes("data/public-theses.json"));
 assert.ok(!JSON.stringify(doc).includes("docs.google.com"));
});
