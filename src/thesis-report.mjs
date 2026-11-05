import {renderCanonicalSource,renderExplanatoryCharts,renderFocusList} from "./thesis-insights.mjs?v=bcbecb4d97ea";
import {renderFinancialSankey} from "./financial-sankey.mjs";
/* IDEA LAB / MIDAS — one editorial renderer for every public investment thesis.
   Immutable source: data/public-theses.json. Canonical prose is only shown when
   data/thesis-reports.json passed its public redaction/approval contract. */
const h=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const valid=x=>typeof x==="number"&&Number.isFinite(x);
const fmt=(n,d=2)=>valid(n)?new Intl.NumberFormat("es-ES",{minimumFractionDigits:d,maximumFractionDigits:d}).format(n):"N/D";
const money=(n,c)=>valid(n)?fmt(n)+" "+h(c||"USD"):"N/D";
const pct=n=>valid(n)?(n>0?"+":"")+fmt(n)+" %":"N/D";
const tickerPattern=/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/;
const SECTIONS=[["summary","Resumen para el comité"],["business","Negocio y ventajas competitivas"],["financial","Mapa financiero oficial · Sankey"],["drivers","Hipótesis y catalizadores"],["valuation","Valoración y escenarios"],["risks","Riesgos e invalidación"],["monitoring","Seguimiento documental"],["original","Investigación íntegra"],["conclusion","Conclusión de inversión"]];
const sec=(id,title,body)=>'<section class="thesis-report-section" id="report-'+id+'"><h2>'+h(title)+'</h2>'+body+'</section>';
function paragraphs(value){
 const text=String(value??"").trim();
 if(!text)return '<p class="thesis-report-muted">Aún no documentado en el expediente publicado.</p>';
 return text.split(/\n\s*\n/).filter(Boolean).map(p=>'<p>'+h(p).replace(/\n/g,'<span class="thesis-line-break"></span>')+'</p>').join("");
}
function sourceBody(source){return renderCanonicalSource(source);}
function stat(title,value,detail){
 return '<div class="thesis-stat"><span>'+h(title)+'</span><strong>'+value+'</strong>'+(detail?'<small>'+h(detail)+'</small>':'')+'</div>';
}
function scenarioPlot(record){
 const points=[["Bajista",record.bearTarget,record.bearCagr,"#a35a69"],["Central",record.baseTarget,record.baseCagr,"#183c67"],["Alcista",record.bullTarget,record.bullCagr,"#2b887e"]];
 const amounts=points.filter(p=>valid(p[1])&&p[1]>=0).map(p=>p[1]);
 if(!amounts.length)return '<p class="thesis-report-muted">No existen objetivos verificables.</p>';
 const max=Math.max(...amounts,valid(record.referencePrice)?record.referencePrice:0,1)*1.13;
 const origin=120,width=680;
 let out='<svg class="thesis-scenarios-chart" viewBox="0 0 990 295" role="img" aria-label="Comparación de escenarios de precio objetivo y CAGR en cinco años">';
 points.forEach(([name,price,cagr,color],index)=>{
  const y=30+index*78;
  out+='<text x="12" y="'+(y+22)+'" class="chart-label">'+name+'</text>';
  if(valid(price)&&price>=0){
   const length=Math.max(2,Math.round(price/max*width));
   out+='<rect x="'+origin+'" y="'+y+'" width="'+length+'" height="28" rx="5" fill="'+color+'"></rect>';
   out+='<text class="chart-value" x="'+Math.min(origin+length+9,820)+'" y="'+(y+21)+'">'+h(fmt(price))+' · '+h(pct(cagr))+'</text>';
  }else out+='<text class="chart-value" x="'+origin+'" y="'+(y+22)+'">N/D</text>';
 });
 if(valid(record.referencePrice)&&record.referencePrice>=0){
  const x=origin+Math.round(record.referencePrice/max*width);
  out+='<line x1="'+x+'" x2="'+x+'" y1="16" y2="253" stroke="#bd9146" stroke-dasharray="6 5" stroke-width="2"></line>';
  out+='<text class="chart-reference" x="'+Math.min(x+6,550)+'" y="278">Referencia histórica: '+h(money(record.referencePrice,record.currency))+'</text>';
 }
 return out+'</svg>';
}
function entries(record){
 if(!valid(record.baseTarget))return '<p class="thesis-report-muted">Sin objetivo central publicado.</p>';
 const rates=[.10,.12,.15,.20];
 return '<table class="thesis-report-table"><thead><tr><th>Rentabilidad anual</th><th>Precio máximo teórico</th><th>Naturaleza</th></tr></thead><tbody>'+
 rates.map(r=>{
 const fromRecord=r===.15&&valid(record.priceFor15);
 const value=fromRecord?record.priceFor15:record.baseTarget/Math.pow(1+r,5);
 return '<tr><td>'+fmt(r*100,0)+' %</td><td>'+money(value,record.currency)+'</td><td>'+(fromRecord?'Umbral documentado':'Derivado matemático; no estimación aprobada')+'</td></tr>';
 }).join("")+'</tbody></table>';
}
export function verifyFullReports(doc,allowed){
 if(!doc||doc.schema!=="midas_canonical_web_reports_v1"||!Array.isArray(doc.reports)||doc.reports.length>25)throw Error("Catálogo de informes íntegros inválido");
 const out=new Map();
 for(const r of doc.reports){
  if(!r||!tickerPattern.test(r.ticker||"")||out.has(r.ticker)||!allowed.has(r.ticker)||r.publication_gate!=="approved"||
     typeof r.source_text!=="string"||r.source_text.length<500||r.source_text.length>180000||
     /https?:\/\/|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\bpersonal_[a-z0-9_]+/i.test(r.source_text))throw Error("Informe no aprobado o no redactado: "+(r?.ticker||"?"));
  out.set(r.ticker,r);
 }
 return out;
}
export function renderThesisReport(record,full=null,financial=null,financialPeriod=null){
 if(!record||!tickerPattern.test(record.ticker||""))return '<p class="thesis-report-muted">No existe informe para el ticker solicitado.</p>';
 const approved=full?.publication_gate==="approved"&&typeof full?.source_text==="string"&&full.source_text.length>500;
 const status=approved?"INFORME EJECUTIVO · EDICIÓN WEB ÍNTEGRA":"FICHA DOCUMENTAL · INFORME ÍNTEGRO NO PUBLICADO";
 const nav=SECTIONS.map(([id,name])=>'<a href="#report-'+id+'">'+h(name)+'</a>').join("");
 const chart=scenarioPlot(record);
 const boxes=[["Bajista",record.bearTarget,record.bearCagr],["Central",record.baseTarget,record.baseCagr],["Alcista",record.bullTarget,record.bullCagr]].map(([title,value,cagr])=>stat(title,money(value,record.currency),pct(cagr))).join("");
 const cover='<header class="thesis-report-cover"><div class="thesis-report-topline"><div><span class="thesis-report-brand">IDEA LAB / MIDAS</span><span class="thesis-report-mark">INVESTMENT RESEARCH · FY2031</span></div><div class="thesis-report-actions"><a class="thesis-report-back" href="./index.html?view=theses">← Seguimiento</a><a class="thesis-report-pdf" href="./reports/'+encodeURIComponent(record.ticker)+'.pdf" target="_blank" rel="noopener noreferrer">Ver PDF ↗</a></div></div>'+
 '<p class="thesis-report-kicker">'+h(record.market||"Mercado no acreditado")+' · '+h(record.theme||"Investigación fundamental")+'</p>'+
 '<h1>'+h(record.company||record.ticker)+' <em>'+h(record.ticker)+'</em></h1>'+
 '<p class="thesis-report-subhead">'+h(status)+' · '+h(full?.version||"Expediente histórico")+' · Corte '+h(full?.document_date||record.studyDate||"N/D")+'</p></header>';
 const snapshot='<div class="thesis-report-kpis">'+
 stat("Dictamen",h(full?.verdict||record.thesisStatus||"Por revisar"))+
 stat("Precio de referencia",money(record.referencePrice,record.currency),record.priceDate||record.studyDate)+
 stat("Objetivo central FY2031",money(record.baseTarget,record.currency))+
 stat("CAGR central",pct(record.baseCagr))+
 stat("Entrada para 15 % anual",money(record.priceFor15,record.currency))+
 stat("Última revisión",h(record.lastReview||"N/D"))+
 '</div><div class="thesis-report-lead">'+paragraphs(record.summary)+'</div>';
 const valuation='<h3>Comparación de objetivos a 2031</h3><div class="thesis-report-chartbox">'+chart+'</div><div class="thesis-report-casecards">'+boxes+'</div><h3>Lectura visual de la valoración</h3>'+renderExplanatoryCharts(record)+'<h3>Umbrales de entrada: horizonte de cinco años</h3>'+entries(record)+'<p class="thesis-report-muted">El umbral P15 procede del expediente histórico cuando está disponible. Los demás se calculan solo por capitalización compuesta a partir del objetivo central; no sustituyen el modelo de valoración original.</p>';
 const conclusion='<p><strong>Estado documental:</strong> '+h(record.thesisStatus||"Pendiente")+'</p><p><strong>Estado de valoración:</strong> '+h(record.valuationStatus||"Pendiente")+'</p><p class="thesis-report-muted">Escenarios históricos del estudio '+h(record.studyDate||"sin fecha")+'. No son cotizaciones actuales ni resultados obtenidos; no constituye asesoramiento personalizado.</p>';
 return '<article class="thesis-report" data-thesis="'+h(record.ticker)+'">'+cover+'<nav class="thesis-report-nav" aria-label="Apartados del informe">'+nav+'</nav>'+
 sec("summary","Resumen para el comité",snapshot)+
 sec("business","Negocio y ventajas competitivas",paragraphs(full?.business||record.summary))+
 sec("financial","Mapa financiero oficial · Sankey",renderFinancialSankey(financial,financialPeriod))+
 sec("drivers","Hipótesis y catalizadores",renderFocusList(full?.drivers||record.drivers,"Catalizadores documentados"))+
 sec("valuation","Valoración y escenarios",valuation)+
 sec("risks","Riesgos e invalidación",renderFocusList(full?.risks||record.risks,"Riesgos documentados"))+
 sec("monitoring","Resultados y seguimiento",paragraphs(record.earningsRecord||"Resultados pendientes"))+
 sec("original",approved?"Informe original · edición web estructurada":"Estado de documentación",'<p class="thesis-source-intro">Contenido íntegro conservado del expediente canónico, con tablas y jerarquía editorial adaptadas para lectura en pantalla. Los gráficos explicativos anteriores se calculan exclusivamente a partir de los escenarios documentados; las figuras históricas sin serie tabular se conservan como referencia.</p>'+sourceBody(approved?full.source_text:null))+
 sec("conclusion","Conclusión de inversión",conclusion)+
 '<footer class="thesis-report-footer">IDEA LAB · MIDAS · Fuente: tesis histórica documentada · Edición pública · No es asesoramiento financiero</footer></article>';
}
