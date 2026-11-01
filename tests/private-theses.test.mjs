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

test("CAGR local table ranking and local export respect the visible historic data",()=>{
 const site=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.match(site,/function issuerReadRows\(\)/);
 assert.match(site,/const local=state\.localCagr\.get\(i\.ticker\)/);
 assert.match(site,/return \["bear","base","bull"\]\.includes\(sort\)\?local\[sort\]:null/);
 assert.match(site,/issuerReadRows\(\)\.map/);
 assert.match(site,/midas-exportacion-local-privada\.csv/);
 assert.match(site,/local\?\(local\.base\?\?"N\/D"\)/);
});
test("Import surface excludes external telemetry and uses an origin-constrained CSP",()=>{
 const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
 assert.match(html,/script-src 'self'/);
 assert.match(html,/connect-src 'self'/);
 assert.ok(!html.includes("static.cloudflareinsights.com"));
 assert.ok(!html.includes("data-cf-beacon"));
});
