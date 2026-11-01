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
