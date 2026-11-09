/* MIDAS · Recover semantic structure from approved source_text.
   All financial cells below are transcribed from the original source, not inferred. */
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const val=x=>String(x??"").trim();
const num=x=>/^[+−\-±()]?[\d.,]+\s*(?:%|USD|BUSD|MUSD|B|M|×|x)?\)?$/iu.test(val(x));
const layouts=[
 ["ADBE","Concepto|Bear|Base|Bull","Archivo v1.2 · LEGACY, no valoración vigente",5,15,"numbers"],
 ["ADBE","Escenario|EV/FCF IDC|Target FY2031|CAGR 5a|P15 entrada","Escenarios canónicos FY2031 · v1.3.4",3,3,"numbers"],
 ["META","Proyección/escenario|Bear C|Base B|Bull A","Escenarios económicos FY2031",5,16,"numbers"],
 ["META","Puente FY2031 Base · BUSD|Importe","Puente de caja FY2031 · Base",7,15,"numbers"],
 ["META","Sensibilidad Base|Resultado FY2031","Sensibilidades económicas Base",5,12,"numbers"],
 ["META","Ruta de invalidación|Cambio adversarial|Precio FY2031","Rutas de invalidación",3,8,"risk"],
 ["META","Indicador tras nuevos resultados|Por qué importa / vínculo con modelo","Indicadores de seguimiento",5,12,"prose"],
 ["META","Estado/modelo|Base FY2031|CAGR precio|Interpretación","Thesis Delta · histórica frente a canónica",3,8,"history"]
];
function table(title,heads,rows){
 return '<div class="thesis-source-table-wrap thesis-source-semantic-table"><table class="thesis-source-table">'+
 '<caption>'+esc(title)+'</caption><thead><tr>'+heads.map(h=>'<th scope="col">'+esc(h)+'</th>').join("")+'</tr></thead><tbody>'+
 rows.map(row=>'<tr>'+row.map((x,i)=>i?'<td>'+esc(x)+'</td>':'<th scope="row">'+esc(x)+'</th>').join("")+'</tr>').join("")+'</tbody></table></div>';
}
function matrix(lines,i,ticker){
 for(const [issuer,header,title,min,max,kind] of layouts){
  if(ticker!==issuer)continue;
  const heads=header.split("|"),w=heads.length;
  if(!heads.every((h,k)=>val(lines[i+k])===h))continue;
  const rows=[];let j=i+w;
  while(j+w<=lines.length&&rows.length<max){
   const cells=lines.slice(j,j+w).map(val),others=cells.slice(1);
   if(cells.some(x=>!x)||cells[0].length>105||others.some(x=>x.length>190))break;
   const ok=kind==="numbers"?others.every(num):
    kind==="risk"?/USD/.test(others[1]):
    kind==="prose"?others[0].length>12:
    num(others[0])&&/%/.test(others[1])&&others[2].length>5;
   if(!ok)break;rows.push(cells);j+=w;
  }
  if(rows.length>=min)return {next:j,kind:"matrix",rows:rows.length,html:table(title,heads,rows)};
 }
 return null;
}
function pltrConclusion(lines,i,ticker){
 if(ticker!=="PLTR"||val(lines[i])!=="Calidad del negocio")return null;
 const labels=["Calidad del negocio","Calidad de la acción al precio de referencia","Target Base","CAGR Base","P15","Postura MIDAS","Principal razón por la que podríamos estar equivocados"];
 const rows=[];let j=i;
 for(const label of labels){
  while(j<lines.length&&!val(lines[j]))j++;
  if(val(lines[j])!==label)return null;
  j++;while(j<lines.length&&!val(lines[j]))j++;
  const t=val(lines[j]);if(!t||t.length>2000)return null;
  rows.push([label,t]);j++;
 }
 return {next:j,kind:"definition",html:'<dl class="thesis-source-verdict-grid">'+
 rows.map(([a,b])=>'<div><dt>'+esc(a)+'</dt><dd>'+esc(b)+'</dd></div>').join("")+'</dl>'};
}
function metaRisks(lines,i,ticker){
 if(ticker!=="META"||val(lines[i])!=="Ocho riesgos que condicionan el valor")return null;
 const rows=lines.slice(i+1,i+9).map(val);
 if(rows.length!==8||!rows.every((x,k)=>x.startsWith((k+1)+". ")))return null;
 return {next:i+9,kind:"risks",html:'<section class="thesis-source-risk-set"><h4>Ocho riesgos que condicionan el valor</h4><ol>'+
 rows.map(t=>{const m=t.match(/^\d+\.\s+(.+?)\s{2,}(.+)$/u);
 return '<li><strong>'+esc(m?.[1]||t.replace(/^\d+\.\s*/,""))+'</strong>'+(m?'<p>'+esc(m[2])+'</p>':"")+'</li>';}).join("")+'</ol></section>'};
}
function catRisks(lines,i,ticker){
 if(ticker!=="CAT"||val(lines[i])!=="Riesgo Valoración cualitativa Señal y respuesta")return null;
 let j=i+1;while(j<lines.length&&j<i+35&&!/^Los compromisos también pueden consumir liquidez:/iu.test(val(lines[j])))j++;
 if(j===lines.length||j>=i+35)return null;
 const body=lines.slice(i+1,j).map(val).filter(Boolean).join(" ");
 const labels=["Conversión de backlog","Ciclo y canal","Capacidad e inversión","Precio y múltiplo","Crédito y financiación","Tarifas y ejecución","Tecnología y competencia"];
 const positions=labels.map(x=>body.indexOf(x));
 if(positions.some((v,k)=>v<0||(k&&v<=positions[k-1])))return null;
 return {next:j,kind:"risks",html:'<section class="thesis-source-risk-set"><h4>Riesgos y señales de invalidación</h4><div class="thesis-source-risk-cards">'+
 labels.map((label,k)=>'<article><h5>'+esc(label)+'</h5><p>'+esc(val(body.slice(positions[k]+label.length,positions[k+1])))+'</p></article>').join("")+
 '</div><small>Transcripción de la tabla del documento original, con celdas partidas entre líneas.</small></section>'};
}
function adobeAuditedSeries(lines,i,ticker){
 if(ticker!=="ADBE"||!val(lines[i]).startsWith("FY2021 · EV "))return null;
 const pattern=/^(FY202[1-5]) · EV ([\d.]+,\d+) MUSD · FCF IDC ([\d.]+,\d+) MUSD · EV\/FCF IDC (\d+,\d+×)\.$/u;
 const rows=[];
 for(const year of ["FY2021","FY2022","FY2023","FY2024","FY2025"]){
  const match=val(lines[i+rows.length]).match(pattern);
  if(match?.[1]!==year)return null;
  rows.push(match.slice(1));
 }
 return {next:i+rows.length,kind:"matrix",rows:rows.length,html:table(
  "Serie FY2021–FY2025 auditada · QA-09",["Ejercicio","EV (MUSD)","FCF IDC (MUSD)","EV/FCF IDC"],rows)};
}
export const semanticBlock=(lines,i,ticker)=>matrix(lines,i,ticker)||adobeAuditedSeries(lines,i,ticker)||pltrConclusion(lines,i,ticker)||metaRisks(lines,i,ticker)||catRisks(lines,i,ticker);
const exact={
 META:["Publicidad como motor de caja","Opcionalidad, no flujo asegurado","Reality Labs y capacidad de reinversión","IDC: referencia histórica, no target automático","Por qué el valor terminal domina","Fuentes y trazabilidad principal"],
 PLTR:["U.S. Commercial","U.S. Government","Escenarios FY2031","Umbrales de precio desde el Target Base"],
 CAT:["Calidad financiera y ciclo industrial","Conversión de beneficios en caja","Management y asignación de capital","Valoración IDC y estructura financiera","Escenarios y control de reinversión","Riesgos y señales que cambiarían la tesis"],
 ADBE:["FUENTES PRINCIPALES Y WORKPAPERS","INTERPRETACIÓN PARA EL COMITÉ"]
};
export function semanticHeading(line,ticker){
 const t=val(line);if(!t||t.length>140)return 0;
 if(/^\d{1,2}[A-Z]?(?:\.\d+)?[.)]\s+\S/iu.test(t))return 3;
 if(t.length<115&&/^[A-ZÁÉÍÓÚÑ0-9\s·:—–/\-()]+$/u.test(t)&&t.split(/\s+/).length<=13&&!/\bUSD\b/.test(t))return 3;
 if((exact[ticker]||[]).includes(t))return 4;
 return 0;
}
export const runningHeader=(text,ticker)=>ticker==="CAT"&&/^Análisis 21 octubre 2026 \| Publicación 22 octubre 2026 \| Investigación privadaMIDAS \| CAT \| Investment Research$/.test(val(text));
const emphasis=/^(PUBLICACIÓN v[\d.]+|OMISIÓN MATERIAL CORREGIDA|INCENTIVOS 2026|BASE ÚNICO ECONÓMICO|BASE PRUDENTE[^:]{0,70}|BEAR CONDICIONADO[^:]{0,70}|BULL CONDICIONADO[^:]{0,70}|FÓRMULAS DE CONTROL[^:]{0,70}|DECISIÓN ECONÓMICA AUTORIZADA[^:]{0,75}|THESIS DELTA[^:]{0,55}|ESTADO FORMAL|CONCLUSIÓN PARA COMITÉ|Juicio para el Comité|Fuente[s]?|Riesgos prioritarios a monitorizar|Próximo punto de control|LÍMITES Y GOBIERNO|REPRODUCIBILIDAD \/ EVIDENCIA)\s*:\s*(.+)$/iu;
export function semanticParagraph(source){
 const t=val(source),m=t.match(emphasis);
 if(m)return '<p class="thesis-source-paragraph thesis-source-labelled"><strong>'+esc(m[1])+':</strong> '+esc(m[2])+'</p>';
 if(t.includes("Referencia externa omitida en edición pública")&&t.length<210)return '<p class="thesis-source-reference">'+esc(t)+'</p>';
 return '<p class="thesis-source-paragraph">'+esc(t)+'</p>';
}
