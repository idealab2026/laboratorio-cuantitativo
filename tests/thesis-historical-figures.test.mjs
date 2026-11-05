import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {renderThesisReport} from "../src/thesis-report.mjs";
import {sourceFigureAudit,isHistoricalFigure,figureKey} from "../src/thesis-historical-figures.mjs";

const report=JSON.parse(readFileSync(new URL("../data/thesis-reports.json",import.meta.url),"utf8"));
const theses=JSON.parse(readFileSync(new URL("../data/public-theses.json",import.meta.url),"utf8"));
const byTicker=new Map(theses.records.map(x=>[x.ticker,x]));
const expected={ADBE:5,MSFT:2,META:4,PLTR:7,CAT:3};

test("Every historic caption in every approved full thesis has a first-class figure artifact",()=>{
 let total=0,rendered=0,unavailable=0;
 for(const doc of report.reports){
  const ticker=doc.ticker;
  assert.equal(doc.publication_gate,"approved");
  const audit=sourceFigureAudit(ticker,doc.source_text);
  assert.equal(audit.found,expected[ticker],ticker);
  assert.equal(audit.complete,true,ticker+" missing="+audit.missing.join(","));
  total+=audit.found;
  const html=renderThesisReport(byTicker.get(ticker),doc);
  const markers=[...html.matchAll(/<figure class="thesis-restored-figure(?: is-unavailable)?"/g)];
  assert.equal(markers.length,audit.found,ticker);
  const live=(html.match(/class="thesis-restored-svg"/g)||[]).length;
  const absent=(html.match(/class="thesis-restored-figure is-unavailable"/g)||[]).length;
  assert.equal(live+absent,audit.found,ticker);
  assert.ok(!html.includes("NaN")&&!html.includes("Infinity"),ticker);
  assert.ok(!html.includes("La figura original se cita aquí, pero no se reconstruye"),ticker);
  assert.match(html,/Datos y procedencia:/);
  rendered+=live;unavailable+=absent;
 }
 assert.equal(total,21);
 assert.equal(rendered,19);
 assert.equal(unavailable,2); // PLTR: price/revenue time series and annual NI/EPS not in public source.
});

test("All 26 thesis pages share layout without phantom historical figure references",()=>{
 for(const row of theses.records){
  const full=report.reports.find(x=>x.ticker===row.ticker)||null;
  const html=renderThesisReport(row,full);
  assert.equal((html.match(/class="thesis-report-section"/g)||[]).length,9,row.ticker);
  if(!full)assert.equal((html.match(/class="thesis-restored-figure/g)||[]).length,0,row.ticker);
 }
});

test("Figure recognizer includes Adobe GRAPH labels, CAT labels without dots and Palantir 4B",()=>{
 assert.ok(isHistoricalFigure("GRÁFICA PRINCIPAL · PRECIO Y FUNDAMENTALES"));
 assert.ok(isHistoricalFigure("GRÁFICO A · INGRESOS"));
 assert.ok(isHistoricalFigure("Figura 1 Ventas y margen industrial"));
 assert.ok(isHistoricalFigure("Figura 4B. Acciones diluidas"));
 assert.equal(figureKey("ADBE","GRÁFICA PRINCIPAL · 2016=100"),"MAIN");
 assert.equal(figureKey("CAT","Figura 1 Ventas y margen industrial"),"1");
 assert.equal(figureKey("PLTR","Figura 4B. Acciones diluidas"),"4B");
 assert.equal(figureKey("MSFT","Figura 1. EV/FCF IDC"),"1");
});

test("Figures cannot claim a complete annual series from sparse disclosed endpoints",()=>{
 const html=renderThesisReport(byTicker.get("ADBE"),report.reports.find(x=>x.ticker==="ADBE"));
 assert.match(html,/No son observaciones anuales/);
 assert.match(html,/No es una serie anual homogénea/);
 const pltr=renderThesisReport(byTicker.get("PLTR"),report.reports.find(x=>x.ticker==="PLTR"));
 assert.match(pltr,/faltan datos de origen/);
 assert.match(pltr,/No constan cotizaciones e ingresos anuales/);
 assert.match(pltr,/No existe en el corpus público de la tesis una serie trimestral de RPO y NDR/);
 const msft=renderThesisReport(byTicker.get("MSFT"),report.reports.find(x=>x.ticker==="MSFT"));
 assert.match(msft,/No se dibuja una falsa serie/);
 assert.doesNotMatch(msft,/figura histórica sin fuente/);
});
