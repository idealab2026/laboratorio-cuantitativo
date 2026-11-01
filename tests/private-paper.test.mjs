import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {parseLocalPaperResults,parseLocalPaperCurves,summarizePrivatePaper}
 from "../src/private-paper.mjs";

const R=["ID institucional","Algoritmo","Familia","Resultado","Estado original",
"Divisa","Primera sesión","Última sesión","Capital inicial paper","NAV último",
"Rentabilidad acumulada (%)","Cambio último día (%)","Sesiones registradas",
"Posiciones abiertas","Órdenes pendientes","Drawdown máximo (%)","Actualización del extracto",
"Tipo de datos"];
const C=["ID institucional","Sesión","NAV del cierre","Capital inicial","Rentabilidad acumulada (%)",
 "Divisa","Tipo de contabilización"];
const csv=r=>r.map(a=>a.map(v=>'"'+String(v??"").replaceAll('"','""')+'"').join(",")).join("\r\n");
function fixture(){
 const results=[R],curves=[C];
 for(let i=1;i<=64;i++){
  const id="IL-"+String(i).padStart(3,"0"),valid=i<=31,days=i===31?17:10;
  const dates=Array.from({length:days},(_,n)=>"2026-10-"+String(n+1).padStart(2,"0"));
  const lastNav=valid?100000+100*i+days:undefined;
  const ret=valid?(lastNav/100000-1)*100:undefined;
  results.push([id,"Modelo "+i,"Grupo de prueba "+(i%4),
    valid?"PAPER REGISTRADO · CORTE HISTÓRICO":"SIN HISTÓRICO COMPARABLE",
    valid?"demo_con_diario":"sin_ejecucion_comparable",
    valid?"USD":"",valid?dates[0]:"",valid?dates.at(-1):"",
    valid?100000:"",valid?lastNav:"",valid?ret:"",valid?"0":"",
    valid?days:0,valid?1:"",valid?0:"",valid?"-2":"",
    "2026-08-18T12:00:00Z","PAPER NO REAL"]);
  if(valid)for(let j=0;j<days;j++){
   const nav=j===days-1?lastNav:100000+i+j;
   curves.push([id,dates[j],nav,100000,(nav/100000-1)*100,"USD","PAPER"]);
  }
 }
 return {results,curves};
}
test("Verify 64 originals, 31 dated paper diaries and 317 sample NAV rows",()=>{
 const raw=fixture();
 const results=parseLocalPaperResults(csv(raw.results));
 assert.equal(results.size,64);
 assert.equal(results.get("IL-048").pct,null);
 assert.equal(results.get("IL-031").sessions,17);
 const curves=parseLocalPaperCurves(csv(raw.curves),results);
 const summary=summarizePrivatePaper(results,curves);
 assert.deepEqual(summary,{algorithms:64,withNav:31,pending:33,
   curveObservations:317,latest:"2026-10-17"});
 assert.equal(curves.get("IL-031").at(-1).nav,103117);
});
test("Refuse unknown ID, duplicate ID, invented P/L, and inconsistent NAV",()=>{
 let x=fixture();
 x.results[1][0]="IL-999";
 assert.throws(()=>parseLocalPaperResults(csv(x.results)),/Identificador/);
 x=fixture();x.results[2][0]=x.results[1][0];
 assert.throws(()=>parseLocalPaperResults(csv(x.results)),/Identificador/);
 x=fixture();x.results[49][10]=0;
 assert.throws(()=>parseLocalPaperResults(csv(x.results)),/sin diario/i);
 x=fixture();x.results[3][9]=1;
 assert.throws(()=>parseLocalPaperResults(csv(x.results)),/inconsistentes/i);
});
test("Reject incomplete curves, future gap in chronological order, and NAV mismatch",()=>{
 const x=fixture(),results=parseLocalPaperResults(csv(x.results));
 assert.throws(()=>parseLocalPaperCurves(csv(x.curves.slice(0,-1)),results),/Sesiones incompletas/);
 const duplicate=structuredClone(x.curves);duplicate[2][1]=duplicate[1][1];
 assert.throws(()=>parseLocalPaperCurves(csv(duplicate),results),/fuera de orden/);
 const corrupted=structuredClone(x.curves);corrupted.at(-1)[2]=1;
 assert.throws(()=>parseLocalPaperCurves(csv(corrupted),results),/no coincide/);
});
test("Handle localized Spanish decimals and decimal comma, not scientific notation",()=>{
 const x=fixture();
 x.results[1][9]="100.110,00";
 x.results[1][10]="0,11";
 const r=parseLocalPaperResults(csv(x.results));
 assert.equal(r.get("IL-001").nav,100110);
 const rounded=fixture();
 rounded.results[1][9]="100.110,00";
 rounded.results[1][10]="0,11";
 assert.equal(parseLocalPaperResults(csv(rounded.results)).get("IL-001").nav,100110);
 const invalid=fixture();invalid.results[1][9]="1e50";
 assert.throws(()=>parseLocalPaperResults(csv(invalid.results)),/Cifra inválida/);
});
test("Isolate private viewer: no upload/network/storage and strict CSP",()=>{
 for(const path of ["../src/private-paper.mjs","../src/private-paper-view.mjs"]){
  const content=readFileSync(new URL(path,import.meta.url),"utf8");
  assert.ok(!/fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|indexedDB|WebSocket/.test(content));
 }
 const html=readFileSync(new URL("../private-paper.html",import.meta.url),"utf8");
 assert.match(html,/connect-src 'none'/);
 assert.match(html,/src="\.\/src\/private-paper-view\.mjs"/);
 assert.ok(!/static\.cloudflareinsights|data-cf-beacon|https?:\/\/docs\.google/.test(html));
});
