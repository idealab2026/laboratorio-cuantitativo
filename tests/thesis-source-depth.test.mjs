import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {renderCanonicalSource} from "../src/thesis-insights.mjs";
import {semanticBlock,semanticHeading} from "../src/thesis-source-structure.mjs";
const published=JSON.parse(readFileSync(new URL("../data/thesis-reports.json",import.meta.url),"utf8"));
const full=new Map(published.reports.map(d=>[d.ticker,d]));
const record=ticker=>({ticker});
const html=ticker=>renderCanonicalSource(full.get(ticker).source_text,record(ticker));

test("Full-report editorial quality is checked at the end, not just on the first page",()=>{
 assert.deepEqual([...full.keys()].sort(),["ADBE","CAT","META","MSFT","PLTR"]);
 for(const ticker of full.keys()){
  const source=full.get(ticker).source_text;
  const output=html(ticker);
  assert.ok(output.length>source.length*.74,ticker+" appears truncated");
  assert.doesNotMatch(output,/NaN|Infinity|undefined/);
  assert.match(output,/class="thesis-source-heading"/);
  assert.match(output,/class="thesis-source-paragraph"/);
  assert.match(output,/class="thesis-source-body"/);
 }
});
test("ADBE late historical archive and approved target matrices remain distinct tables",()=>{
 const output=html("ADBE");
 assert.match(output,/7A\. ARCHIVO DE LA REVISIÓN IA v1\.2/);
 assert.match(output,/7B\. ESCENARIOS FY2031 v1\.3\.4/);
 assert.match(output,/7C\. SERIE FY2021–FY2025 REEXPRESADA/);
 assert.match(output,/Archivo v1\.2 · LEGACY, no valoración vigente/);
 assert.match(output,/Escenarios canónicos FY2031 · v1\.3\.4/);
 assert.match(output,/<td>386,86 USD<\/td>/);
 assert.match(output,/<td>534,36 USD<\/td>/);
 assert.match(output,/<td>265,67 USD<\/td>/);
 assert.match(output,/FUENTES PRINCIPALES Y WORKPAPERS/);
});
test("META late source matrices are converted into 6 legible tables with original values",()=>{
 const output=html("META");
 assert.equal((output.match(/thesis-source-semantic-table/g)||[]).length,6);
 assert.match(output,/Escenarios económicos FY2031/);
 assert.match(output,/Puente de caja FY2031/);
 assert.match(output,/Sensibilidades económicas Base/);
 assert.match(output,/Rutas de invalidación/);
 assert.match(output,/Indicadores de seguimiento/);
 assert.match(output,/Thesis Delta · histórica frente a canónica/);
 assert.match(output,/<td>−141,01<\/td>/);
 assert.match(output,/<td>1.250,24 USD<\/td>/);
 assert.match(output,/<td>−44,36%<\/td>/);
 assert.match(output,/class="thesis-source-risk-set"/);
 assert.equal((output.match(/<li><strong>/g)||[]).length,8);
 assert.match(output,/<h4 class="thesis-source-subheading">Por qué el valor terminal domina<\/h4>/);
 assert.match(output,/Fuentes y trazabilidad principal/);
});
test("PLTR final investment conclusion becomes a seven-factor executive grid",()=>{
 const output=html("PLTR");
 assert.match(output,/class="thesis-source-verdict-grid"/);
 assert.equal((output.match(/<dt>/g)||[]).length,7);
 assert.match(output,/<dt>Calidad del negocio<\/dt>/);
 assert.match(output,/<dt>Postura MIDAS<\/dt>/);
 assert.match(output,/62,52 USD/);
 assert.match(output,/Principal razón por la que podríamos estar equivocados/);
 assert.match(output,/FUENTES PRIMARIAS Y TRAZABILIDAD/);
});
test("CAT retains chapter subheads and converts late risk table to seven distinct cards",()=>{
 const output=html("CAT");
 assert.match(output,/<h4 class="thesis-source-subheading">Conversión de beneficios en caja<\/h4>/);
 assert.match(output,/<h4 class="thesis-source-subheading">Riesgos y señales que cambiarían la tesis<\/h4>/);
 assert.match(output,/class="thesis-source-risk-cards"/);
 assert.equal((output.match(/thesis-source-risk-cards[\s\S]*?<\/div>/g)||[]).length,1);
 assert.equal((output.match(/<article><h5>/g)||[]).length,7);
 assert.match(output,/Tecnología y competencia/);
});
test("MSFT heading hierarchy reaches section 10, while approving no fabricated values",()=>{
 const output=html("MSFT");
 assert.match(output,/<h3 class="thesis-source-heading">10\. Fuentes primarias y workpapers separados<\/h3>/);
 assert.match(output,/503,14 USD/);
 assert.match(output,/thesis-source-reference/);
 assert.equal(semanticHeading("7A. ARCHIVO DE LA REVISIÓN IA v1.2","ADBE"),3);
 assert.equal(semanticHeading("Por qué el valor terminal domina","META"),4);
 assert.equal(semanticHeading("La valorización no es una serie anual completa.","META"),0);
});
test("No part of the source matrix is reconstructed when a required cell is missing",()=>{
 const broken=["Proyección/escenario","Bear C","Base B","Bull A","Ingresos FY2031 · BUSD","488,61","","580,62"];
 assert.equal(semanticBlock(broken,0,"META"),null);
});
