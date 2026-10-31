import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {parseInstitutionalLocalArchive} from "../src/private-theses.mjs";

const allowed=new Set(["MSFT","META","NET"]);
const headers=["Ticker","Empresa","Última revisión","Estado documental recuperado",
 "Horizonte","CAGR Bear (%)","CAGR Base (%)","CAGR Bull (%)",
 "Escenario Bear original","Escenario Base original","Escenario Bull original"];
const row=(ticker="MSFT",date="2026-10-29")=>[
 ticker,"Microsoft",date,"COMPLETA CON RESERVAS","FY2031",
 "-16,50%","-0,90%","+13,74%",
 "modelo histórico","no confundir con precio spot","escenario condicionado"];
const csv=rows=>[headers,...rows].map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(",")).join("\r\n");

test("Personal numeric archive can be inspected locally but never becomes public data",()=>{
 const rows=parseInstitutionalLocalArchive(csv([row(),row("META","2026-10-28")]),allowed);
 assert.equal(rows.size,2);
 assert.equal(rows.get("MSFT").base,-.90);
 assert.equal(rows.get("MSFT").bear,-16.50);
 assert.equal(rows.get("MSFT").bull,13.74);
 assert.equal(rows.get("META").date,"2026-10-28");
 assert.equal(Object.keys(rows.get("MSFT")).sort().join(","),
              "base,bear,bull,date,horizon,status,ticker");
 const reader=readFileSync(new URL("../src/private-theses.mjs",import.meta.url),"utf8");
 assert.ok(!/fetch\s*\(|localStorage|sessionStorage|indexedDB|XMLHttpRequest|navigator\.sendBeacon/.test(reader));
});

test("Only issuer-matched, nonduplicated, time-stamped percentages are accepted",()=>{
 assert.throws(()=>parseInstitutionalLocalArchive(csv([row("FAKE")]),allowed));
 assert.throws(()=>parseInstitutionalLocalArchive(csv([row(),row()]),allowed));
 assert.throws(()=>parseInstitutionalLocalArchive(csv([row("MSFT","2026-99-99")]),allowed));
 const bad=row();bad[6]="1.02e99%";
 assert.throws(()=>parseInstitutionalLocalArchive(csv([bad]),allowed));
 assert.throws(()=>parseInstitutionalLocalArchive(csv([]),allowed));
});

test("Semicolon separated exported European decimal percentages are readable",()=>{
 const lines=[headers,row()];
 const data=lines.map(r=>r.join(";")).join("\n");
 const out=parseInstitutionalLocalArchive(data,allowed);
 assert.equal(out.get("MSFT").base,-.9);
 assert.equal(out.get("MSFT").bull,13.74);
});

test("Frontend keeps any uploaded archive separate from public issuer validation",()=>{
 const source=readFileSync(new URL("../src/site.mjs",import.meta.url),"utf8");
 assert.ok(source.includes("parseInstitutionalLocalArchive"));
 assert.ok(source.includes("theses-private-import"));
 assert.ok(source.includes("privateTheses:null"));
 assert.ok(source.includes("state.privateTheses=null"));
 assert.ok(source.includes("Archivo privado · histórico"));
});
