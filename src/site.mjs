import {verifyOriginalPaper} from "./original-paper.mjs?v=b4ab52ea9863";
import {algorithmTheory,paperLeaderboard} from "./algorithm-detail.mjs";
import {glossaryGroups,searchGlossary,verifyGlossary} from "./glossary.mjs";
import {verifyOperationsAudit,renderOperationsAudit} from "./operations-audit.mjs?v=3bea2af851c0";
import {parseLocalPaperResults,parseLocalPaperCurves,summarizePrivatePaper} from "./private-paper.mjs?v=4baff08a2202";
import {signalResearchSummary,methodCatalog} from "./paper-methods.mjs";
import {parseLocalCagr2031} from "./private-theses.mjs";
import {verifyPublicTheses,publicResearchRows,orderedThesisRows,publicThesisTableRows,publicThesisDetail,publicThesisCsv} from "./public-theses.mjs?v=24b9692353a2";
import {artificialCampaignComparison} from "./paper-ledger.mjs";
import {verifyFullRoster,filterRoster,technicalStage,technicalCoverage,verifyStrategyCandidates,filterStrategyCandidates,FULL_SORT_KEYS,sortFullCompetitionRows} from "./competition-roster.mjs";
import {verifyPaperFeed} from "./paper-feed.mjs";
import {verify,simulate,rank,valuation,thesisRank,formatPct,money,finite,verifyIssuerCatalog,filterIssuers,syntheticBarsFromDemo,nextOpenPaper,evaluateIssuerScreen,competitionReadModel,publicIssuerReadModel,verifyOfficialFx,summarizeFxForecastLedger,verifySecFilings,verifyOfficialYield} from "./metrics.mjs";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>finite(n)?new Intl.NumberFormat("es-ES",{maximumFractionDigits:2}).format(n):"N/D";
const state={data:null,universe:null,fx:null,fxCheck:null,fxStatus:"pending",forecastLedger:null,forecastSummary:null,forecastStatus:"pending",secStatus:"pending",secRead:null,secCatalog:null,yieldDoc:null,yieldCheck:null,yieldStatus:"pending",view:"competition",strategy:"P-01",group:"",sort:"returnPct",asc:false,detailOpen:false,thesis:"T-01",query:"",thesisSort:"central",issuerMode:"catalog",issuerQuery:"",issuerSort:"base",issuerAsc:false,issuerTicker:"MSFT",paperDetail:"M-10",originalPaper:null,originalPaperStatus:"pending",historicalPaper:null,historicalCurves:null,historicalPaperStatus:"pending",fullRoster:null,fullRosterStatus:"pending",strategyCandidates:null,strategyCandidatesStatus:"pending",fullRosterGroup:"",fullRosterQuery:"",fullRosterSort:"return",fullRosterAsc:false,algorithmId:null,operationsAudit:null,operationsAuditStatus:"pending",auditTicker:null,auditTab:"sessions",auditSort:"recent",auditDesc:true,institutionalFeedStatus:"pending",paperFeed:null,paperFeedRead:null,localCagr:new Map(),localCagrError:"",publicTheses:new Map(),publicThesesMetadata:null};
const viewNames=["competition","algorithm","algorithms","theses","monitoring","method","glossary","archive","ported","full","synthetic"];
const button=(label,action,value,cls="smallbtn")=>'<button type="button" class="'+cls+'" data-action="'+esc(action)+'" data-value="'+esc(value)+'">'+esc(label)+'</button>';
const head=(label,title,body)=>'<div class="section-heading"><div><span class="kicker">'+esc(label)+'</span><h2>'+esc(title)+'</h2><p class="section-context">'+esc(body)+'</p></div></div>';
const card=(html)=>'<article class="panel">'+html+'</article>';
const disclaimer=(body)=>'<div class="research-note">'+esc(body)+'</div>';
const all=()=>state.data.strategies;
const active=()=>simulate(state.data,state.strategy);
const groups=()=>[...new Set(all().map(s=>s.group))];
const causalLedger=()=>nextOpenPaper(syntheticBarsFromDemo(state.data),{rule:"trend",feeBps:10,slippageBps:5,lookback:4});
const tone=(n)=>finite(n)?n>0?"perf-positive":n<0?"perf-negative":"perf-flat":"perf-neutral";
const pctText=(n)=>'<span class="performance '+tone(n)+'">'+esc(formatPct(n))+'</span>';
function sparkline(nav,label="Evolución con precios artificiales"){
 if(!Array.isArray(nav)||nav.length<2||nav.some(n=>!finite(n)))return "N/D";
 const lo=Math.min(...nav),hi=Math.max(...nav),span=Math.max(hi-lo,.01);
 const points=nav.map((n,i)=>(3+i*110/(nav.length-1)).toFixed(1)+","+(27-(n-lo)*23/span).toFixed(1)).join(" ");
 return '<svg class="mini-chart '+tone(nav.at(-1)-nav[0])+'" viewBox="0 0 116 32" width="116" height="32" role="img" aria-label="'+esc(label)+'"><polyline points="'+points+'" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"/></svg>';
}
const metric=(label,value)=>'<div class="metric"><strong>'+esc(value)+'</strong><small>'+esc(label)+'</small></div>';
const family=(g)=>({"Clásicas":"Equiponderación, tendencia, reversión, menor variabilidad y control en efectivo.","Aprendizaje semanal":"Proxies de métodos supervisados; no se han entrenado modelos reales.","Predicción temporal":"Modelos temporales de referencia; no se ha ejecutado TimesFM.","Capital Cycle":"Ciclo de inversión y disciplina de valoración con supuestos observables.","Buy The Dip":"Escalonamiento de exposición tras caídas, con reserva de liquidez.","Modelos experimentales":"Multicriterio, parámetros fijos y filtro de estrés."})[g]||"Prototipo de estrategia paper.";
function syntheticCompetition(){
 const rows=competitionReadModel(state.data,{sort:state.sort,ascending:state.asc,group:state.group});
 const headers=[["name","Algoritmo"],["group","Bloque"],["activity","Actividad actual"],["assets","Activos"],["returnPct","Rent. acum."],["sessions","Sesiones"],["lastSession","Última sesión"],["drawdownPct","DD máx."]];
 const headcells=headers.map(([key,title])=>'<th scope="col" aria-sort="'+(state.sort===key?(state.asc?"ascending":"descending"):"none")+'"><button type="button" class="table-sort" data-action="rank-column" data-value="'+key+'" title="Ordenar por '+esc(title)+'">'+esc(title)+' <span aria-hidden="true">'+(state.sort===key?(state.asc?"↑":"↓"):"↕")+'</span></button></th>').join("");
 if(state.detailOpen){
  const selected=rows.find(r=>r.id===state.strategy)||competitionReadModel(state.data).find(r=>r.id===state.strategy);
  if(!selected){state.detailOpen=false;return syntheticCompetition();}
  return button("← Volver a la competición","close-detail","","outline-btn")+
   head("DETALLE · "+selected.id,selected.name,"Ficha ampliada con actividad, riesgo, exposición, retornos por período y evolución. Los datos siguen siendo ficticios.")+
   disclaimer("La rentabilidad es sintética. Las sesiones no representan fechas bursátiles y los fills heredados son ilustrativos; no corresponden a la contabilidad causal next-open.")+
   detail(selected);
 }
 const original=state.data.meta;
 return head("COMPETICIÓN PAPER","Comportamiento de los algoritmos","Una fila por método y una ficha accesible pulsando su nombre o la fila. Las estrategias comparten las mismas 48 sesiones ficticias; no existen campañas públicas prospectivas comparables.")+
 '<div class="source-health-strip" aria-label="Integridad y operación institucional">'+
 '<div><span class="label">Fuente OHLC</span><strong>Sin alimentación real</strong><small>3 activos sintéticos · sin capturas de mercado</small></div>'+
 '<div><span class="label">Estado de ejecución</span><strong>Solo navegador</strong><small>Sin diario persistido ni planificación paper institucional</small></div>'+
 '<div><span class="label">Cierre real verificado</span><strong>N/D</strong><small>Última sesión ficticia: '+esc(state.data.dates.at(-1))+' · generación '+esc(original.asof)+'</small></div>'+
 '</div>'+
 disclaimer("Estas 23 estrategias son prototipos: la clasificación es retrospectiva sobre datos inventados, no un resultado forward, un histórico validado ni una señal de compra.")+
 '<div class="filters"><label>Familia<select id="group-select"><option value="">Todas</option>'+groups().map(g=>'<option value="'+esc(g)+'" '+(state.group===g?"selected":"")+'>'+esc(g)+'</option>').join("")+'</select></label>'+
 '<label>Ordenar<select id="rank-select">'+headers.map(([k,n])=>'<option value="'+k+'" '+(state.sort===k?"selected":"")+'>'+esc(n)+'</option>').join("")+'</select></label>'+
 button(state.asc?"↑ Ascendente":"↓ Descendente","direction","","outline-btn")+button("Exportar CSV","export","ranking","outline-btn")+
 '</div><p class="table-note">'+rows.length+' métodos · Pulsa las cabeceras para ordenar. Valores ausentes siempre al final. Ficha por fila mediante ratón o teclado.</p>'+
 '<div class="table-scroll table-compact"><table class="competition-parity-table"><thead><tr>'+headcells+'<th scope="col">Curva</th></tr></thead><tbody>'+
 rows.map(r=>{
  const assets=r.activeAssets.length?'<span class="asset-chipset">'+r.activeAssets.map(x=>'<b>'+esc(x)+'</b>').join("")+'</span>':'<span class="perf-neutral">Efectivo</span>';
  return '<tr class="interactive-table-row '+(r.id===state.strategy?"is-selected":"")+'" data-competition-id="'+esc(r.id)+'" tabindex="0" aria-label="Abrir la ficha del algoritmo '+esc(r.name)+'">'+
   '<td><strong>'+esc(r.name)+'</strong><small class="smallline">'+esc(r.id)+' · Simulación sin validar</small></td>'+
   '<td>'+esc(r.group)+'</td><td><strong>'+esc(r.activity)+'</strong><small class="smallline">Sin operativa real</small></td>'+
   '<td>'+assets+'</td><td class="number">'+pctText(r.returnPct)+'</td><td class="number">'+r.sessions+'</td>'+
   '<td>'+esc(r.lastSession)+'<small class="smallline">No es fecha real</small></td>'+
   '<td class="number">'+esc(fmt(r.drawdownPct))+' %</td><td>'+sparkline(r.nav)+'</td></tr>';
 }).join("")+'</tbody></table></div>'+
 '<p class="table-note">Verde: positivo · rojo: negativo · gris: sin variación o sin datos. No se oculta ningún modelo por ausencia de órdenes, pero tampoco se interpretan las órdenes simuladas como compras ejecutadas.</p>'+
 button("Ver historial y versiones","navigate","archive","outline-btn")+
 button("Comprobar libro causal","navigate","monitoring","outline-btn");
}
function competition(){return full();}

function detail(s){
 const proxy=["linear","direction","crossrank","perceptron","memory","ensemble","weekly","daily","genetic"].includes(s.mode);
 const r=s.periodReturns||{};
 const last=s.points.at(-1);
 const act=s.activeAssets||Object.keys(state.data.market).filter((k,i)=>s.weights[i]>0.005);
 const sourceState=proxy?"Modelo proxy no entrenado":"Regla de demostración";
 return '<div class="strategy-detail"><article class="panel">'+
 '<div class="panel-top"><div><span class="label">'+esc(s.group)+' · '+esc(s.id)+'</span><h3>'+esc(s.name)+'</h3></div><span class="chip">PAPER · SOLO SINTÉTICO</span></div>'+
 '<p>'+esc(s.rule)+'</p>'+
 '<div class="metric-strip">'+
 metric("Rentabilidad acumulada",formatPct(s.returnPct))+
 metric("Última sesión",formatPct(s.dayReturnPct))+
 metric("Máximo drawdown",fmt(s.drawdownPct)+" %")+
 metric("Volatilidad anualizada",fmt(s.volatilityPct)+" %")+
 metric("Sharpe (rf=0)",fmt(s.sharpe))+
 metric("Número de sesiones",String(s.sessions))+
 metric("Último cierre ficticio",esc(s.lastSession||state.data.dates.at(-1)))+
 metric("Patrimonio ficticio",money(last.equity))+
 '</div>'+
 '<h3 class="minor-heading">Retornos por ventana homogénea, solo sintéticos</h3>'+
 '<div class="metric-strip">'+metric("5 sesiones",formatPct(r.five))+metric("21 sesiones",formatPct(r.twentyOne))+metric("63 sesiones",formatPct(r.sixtyThree))+metric("Ejecución forward","Sin verificar")+'</div>'+
 '<div class="chart-hdr"><strong>Curva completa · NAV base 100</strong><small>'+esc(String(s.sessions))+' sesiones · no hay datos de mercado</small></div>'+
 '<svg id="nav-chart" viewBox="0 0 760 290" role="img" aria-label="Curva del patrimonio sintético"></svg>'+
 '<p class="small-note">'+esc(sourceState)+'. La cifra de la última sesión es una variación sintética entre dos marcas, no una rentabilidad bursátil diaria registrada.</p>'+
 (proxy?disclaimer("Este método usa una función proxy. Su nombre no demuestra que LightGBM, LSTM, TimesFM u otro modelo externo se haya entrenado o ejecutado."):"")+
 '</article><aside class="panel">'+
 '<span class="label">ACTIVIDAD Y POSICIONES · SINTÉTICAS</span><h3>'+esc(s.name)+'</h3>'+
 '<div class="metric-strip aside-metrics">'+metric("Actividad actual",s.orders.length+" órdenes")+metric("Activos expuestos",String(act.length))+metric("Efectivo",fmt(Math.max(0,s.cash)*100)+" %")+metric("Costes",money(s.fees))+'</div>'+
 '<h3 class="minor-heading">Posiciones al último cierre</h3>'+
 (act.length?Object.keys(state.data.market).map((k,i)=>'<div class="bar-label"><span>'+esc(k)+'</span><strong>'+esc(fmt(s.weights[i]*100))+' %</strong></div><div class="exposure-bar"><i style="width:'+Math.max(0,Math.min(100,s.weights[i]*100))+'%"></i></div>').join(""):'<p>Sin exposición a instrumentos; cartera ficticia en efectivo.</p>')+
 '<h3 class="minor-heading">Procedencia y ejecución</h3><p class="small-note">Versión: escenario inventado. Última sesión '+esc(state.data.dates.at(-1))+'. Sin hash de fuente bursátil, orden de broker, registro persistente ni ejecución programada. El motor anterior usa cierres previos como referencia de fill.</p>'+
 button("Abrir diario sintético","journal",s.id,"outline-btn")+
 button("Exportar NAV","export","nav","outline-btn")+
 button("Volver a la tabla","close-detail","","outline-btn")+'</aside></div>';
}
function algorithms(){
 return head("CATÁLOGO DE MÉTODOS","Algoritmos y familias","Reglas reconstruidas para la versión institucional, sin códigos, pesos entrenados ni configuraciones personales.")+
 '<div class="family-grid">'+groups().map(g=>card('<div class="panel-top"><h3>'+esc(g)+'</h3><span class="chip">'+all().filter(s=>s.group===g).length+' algoritmos</span></div><p>'+esc(family(g))+'</p><ul class="algorithm-list">'+all().filter(s=>s.group===g).map(s=>'<li><span>'+esc(s.name)+'</span>'+button("Ficha","select",s.id,"text-btn")+'</li>').join("")+'</ul>')).join("")+'</div>'+
 head("CREAR ESTRATEGIA","Prueba tu propia asignación","Puedes añadir una cartera hipotética en esta sesión. No se guarda en ninguna base de datos.")+
 '<form id="paper-form" class="panel local-form"><div class="form-grid"><label>Nombre<input name="name" maxlength="70" placeholder="Estrategia experimental" required></label>'+
 Object.keys(state.data.market).map(k=>'<label>'+esc(k)+' (%)<input name="'+esc(k)+'" type="number" min="0" max="100" step="1" value="25" required></label>').join("")+
 '<label>Coste en puntos básicos<input name="cost" type="number" min="0" max="100" value="10" required></label></div><p>Suma máxima: 100 % de exposición. El resto es efectivo ficticio.</p><button class="btn" type="submit">Simular cartera local</button><div id="paper-feedback" role="status"></div></form>'+
 disclaimer("Los proxies de regresión, ranking y series temporales no son modelos LightGBM, LSTM o TimesFM efectivamente entrenados. Su incorporación científica requiere nuevas fuentes y pruebas fuera de muestra.");
}
function thesisTableRows(){
 return thesisRank(state.data,state.thesisSort,"desc",state.query).map(t=>'<tr class="'+(state.thesis===t.id?"is-selected":"")+'"><td><strong>'+esc(t.company)+'</strong><small class="smallline">'+esc(t.sector)+'</small></td><td>'+esc(t.method)+'</td><td>'+esc(t.status)+'</td><td class="number">'+money(t.price)+'</td><td class="number">'+money(t.valuation.base.fair)+'</td><td class="number">'+formatPct(t.central)+'</td><td class="number">'+formatPct(t.discountPct)+'</td><td>'+button("Analizar","thesis",t.id)+'</td></tr>').join("");
}
function thesisDetail(t){
 return card('<div class="panel-top"><div><span class="label">'+esc(t.id)+' · '+esc(t.method)+'</span><h3>'+esc(t.company)+'</h3></div><span class="chip">'+esc(t.status)+'</span></div><p>'+esc(t.thesis)+'</p>'+
 '<div class="metric-strip">'+metric("Precio hipotético",money(t.price))+metric("Entrada ficticia",money(t.entry))+metric("CAGR base",formatPct(t.central))+metric("Rentabilidad requerida",fmt(t.requiredReturn)+" %")+'</div>'+
 '<h3 class="minor-heading">Escenarios a cinco periodos ficticios</h3><div class="scenario-grid">'+["bear","base","bull"].map((k,i)=>'<div class="scenario-tile"><span class="label">'+["Bajista","Central","Alcista"][i]+'</span><strong>'+money(t.valuation[k].fair)+'</strong><span>CAGR '+formatPct(t.valuation[k].compound)+'</span><p>Crecimiento '+fmt(t.growth[k])+' % · Múltiplo '+fmt(t.multiples[k])+'×</p></div>').join("")+'</div>'+
 '<div class="section-grid three"><div><h3>Refutación</h3><p>'+esc(t.counter)+'</p></div><div><h3>Catalizadores</h3><p>'+esc(t.catalysts)+'</p></div><div><h3>Origen de los supuestos</h3><p>'+esc(t.evidence)+'</p></div></div>');
}
function syntheticTheses(){
 const t=valuation(state.data.theses.find(x=>x.id===state.thesis)||state.data.theses[0]);
 return button("← Volver a las empresas","issuer-mode","catalog","outline-btn")+head("TESIS DEMOSTRATIVAS","Hipótesis, escenarios y valoraciones","Cada tesis cuenta con condiciones de refutación, escenarios, supuestos y método. Se trata de entidades y cifras inventadas.")+
 '<div class="filters"><label>Buscar<input id="thesis-query" type="search" placeholder="Entidad o sector" value="'+esc(state.query)+'"></label><label>Ordenar<select id="thesis-sort">'+[["central","CAGR base"],["discountPct","Descuento"],["company","Nombre"],["price","Precio"]].map(([k,v])=>'<option value="'+esc(k)+'" '+(k===state.thesisSort?"selected":"")+'>'+esc(v)+'</option>').join("")+'</select></label>'+button("Exportar CSV","export","theses","outline-btn")+'</div>'+
 '<div class="table-scroll"><table><thead><tr><th>Entidad</th><th>Método</th><th>Estado</th><th class="number">Precio</th><th class="number">Valor base</th><th class="number">CAGR</th><th class="number">Descuento</th><th>Ficha</th></tr></thead><tbody id="thesis-rows">'+thesisTableRows()+'</tbody></table></div>'+
 head("ANÁLISIS","Ficha de tesis","Comparación de supuestos y criterios falsables.")+thesisDetail(t)+
 disclaimer("Ninguna ficha procede de una watchlist personal, trabajo académico o firma de análisis externa.");
}

const independentScreen=(ticker)=>{
 const s=state.universe.publicScreens?.find(x=>x.ticker===ticker);
 return s?evaluateIssuerScreen(s):null;
};
function secSourcePanel(ticker){
 const issuer=state.universe.issuers.find(x=>x.ticker===ticker);
 if(!issuer?.secCik)return '<p class="small-note">No existe todavía una identidad SEC confirmada para esta entidad.</p>';
 const official='<a href="https://www.sec.gov/edgar/browse/?CIK='+esc(issuer.secCik)+'" target="_blank" rel="noopener noreferrer">Consultar EDGAR oficial</a>';
 const found=state.secRead?.byTicker.get(ticker);
 if(!found)return '<div class="research-note">El índice institucional de documentos SEC está '+(state.secStatus==="pending"?"cargando": "sin datos verificados")+'. En la prueba de GitHub Actions del 31/10/2026, la API de la SEC rechazó el colector con HTTP 403. Las consultas programadas permanecen suspendidas hasta disponer de un contacto institucional supervisado y acceso autorizado. '+official+'. No se inventan formularios ni fechas de presentación.</div>';
 return '<section class="sec-official-panel"><div class="panel-top"><h3>Documentación SEC · '+esc(ticker)+'</h3><span class="chip">Fuente oficial · '+esc(state.secRead.generatedAt.slice(0,10))+'</span></div>'+
 '<p>Registros EDGAR (10-K, 10-Q y 8-K) vinculados a sus documentos originales. No se han auditado automáticamente las cifras contables ni los supuestos de valoración. '+official+'.</p>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Formulario</th><th>Presentado</th><th>Ejercicio / período</th><th>Documento SEC</th></tr></thead><tbody>'+
 found.filings.map(item=>'<tr><td><strong>'+esc(item.form)+'</strong></td><td>'+esc(item.filed)+'</td><td>'+esc(item.report_date||"N/D")+'</td>'+
 '<td><a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">Abrir '+esc(item.accession)+'</a></td></tr>').join("")+'</tbody></table></div>'+
 '<p class="small-note">Origen y comprobación: <a href="'+esc(found.source_url)+'" target="_blank" rel="noopener noreferrer">SEC submissions JSON</a> · SHA-256 <code>'+esc(found.source_sha256)+'</code>. Archivo <a href="./data/sec-filings.json" target="_blank" rel="noopener noreferrer">institucional de metadatos</a>.</p></section>';
}

function issuerReadRows(){
 const rows=publicResearchRows(publicIssuerReadModel(state.universe),state.publicTheses,{query:state.issuerQuery,sort:state.issuerSort,ascending:state.issuerAsc});
 return orderedThesisRows(rows,state.publicTheses,state.localCagr,state.issuerSort,state.issuerAsc);
}
function researchIssuerCount(){return new Set([...state.universe.issuers.map(x=>x.ticker),...state.publicTheses.keys()]).size;}
function issuerTableRows(){
 return publicThesisTableRows(issuerReadRows(),state.publicTheses,state.localCagr,state.issuerTicker);
}

function issuerDetail(){
 const publicRecord=state.publicTheses.get(state.issuerTicker);
 if(publicRecord)return publicThesisDetail(publicRecord,state.localCagr.get(state.issuerTicker));
 const i=state.universe.issuers.find(x=>x.ticker===state.issuerTicker)||state.universe.issuers[0];
 const s=independentScreen(i.ticker);
 const local=state.localCagr.get(i.ticker);
 const source=i.secCik?'<p>Expediente regulatorio SEC: <a href="https://www.sec.gov/edgar/browse/?CIK='+esc(i.secCik)+'" target="_blank" rel="noopener noreferrer">10-K, 10-Q y 8-K oficiales</a>. Los enlaces no prueban por sí solos las hipótesis financieras.</p>':'<p>Identificador de expediente regulatorio pendiente de contrastar.</p>';
 const base=card('<div class="panel-top"><div><span class="label">'+esc(i.ticker)+' · '+esc(i.market)+'</span><h3>'+esc(i.company)+'</h3></div><span class="status-chip">'+(local?"CAGR histórico local":s?"Screening exploratorio":"Pendiente de validación")+'</span></div><p>'+esc(i.sector)+'</p>'+
 '<div class="metric-strip">'+metric("Precio documentado",local?"N/D · no sincronizado":s?fmt(s.quote.close)+" USD · "+s.quote.closeDate:"N/D")+metric("CAGR central",local?(local.base===null?"N/D":formatPct(local.base)):s?formatPct(s.scenarios.base.cagrPct):"N/D")+metric("Precio 15 % anual",local?"N/D":s?fmt(s.buyPrice15)+" USD":"N/D")+metric("Próximos resultados","N/D")+'</div>'+
 '<h3 class="minor-heading">Fuentes oficiales</h3>'+source+secSourcePanel(i.ticker)+
 '<h3 class="minor-heading">Control de publicación</h3><p>La identidad corporativa no constituye una tesis aprobada. Los valores disponibles son escenarios exploratorios, no precio objetivo recomendado ni recomendación de inversión. No se traslada ningún expediente privado.</p>');
 if(local)return base+card('<h3>CAGR históricos importados · no publicados</h3><div class="metric-strip">'+metric("Bear",local.bear===null?"N/D":formatPct(local.bear))+metric("Central",local.base===null?"N/D":formatPct(local.base))+metric("Bull",local.bull===null?"N/D":formatPct(local.bull))+'</div><p>Fecha de estudio: '+esc(local.date||"sin fecha")+' · Estado de archivo: '+esc(local.status)+'. Estas cifras no son rentabilidades realizadas ni cotizaciones vigentes. Datos cargados únicamente en este navegador.</p>');
 if(!s)return base;
 const scenarios=["bear","base","bull"].map((key,index)=>{
  const v=s.scenarios[key];
  return '<div class="scenario-tile"><span class="label">'+["Bajista","Central","Alcista"][index]+'</span><strong>'+esc(fmt(v.target))+' USD</strong><span class="performance '+tone(v.cagrPct)+'">CAGR '+esc(formatPct(v.cagrPct))+'</span><p>EPS +'+esc(fmt(v.growthPct))+' % anual · PER terminal '+esc(fmt(v.terminalPe))+'×</p></div>';
 }).join("");
 return base+
 head("MODELO INDEPENDIENTE · SCREENING","Sensibilidad EPS–PER a cinco años","Supuestos hipotéticos explícitos, no una valoración DCF completa ni una actualización del informe histórico.")+
 card('<div class="metric-strip">'+metric("EPS ajustado FY2026",fmt(s.metric.adjustedEpsFY2026)+" USD")+metric("Cierre 30/10/2026",fmt(s.quote.close)+" USD")+metric("Crecimiento Azure FY27 Q1",fmt(s.catalyst.azureGrowthYoyPct)+" % interanual")+metric("Ingresos FY27 Q1",fmt(s.catalyst.q1FY2027RevenueBillion)+" miles MUSD")+'</div>'+
 '<div class="scenario-grid">'+scenarios+'</div>'+
 '<p><strong>Fórmula:</strong> precio 2031 = EPS ajustado FY2026 × (1 + crecimiento anual supuesto)^5 × PER terminal supuesto. CAGR = (precio 2031 / cierre de referencia)^(1/5) − 1. Entrada para obtener 15 % anual = precio central 2031 / (1,15)^5.</p>'+
 '<p><strong>Limitaciones:</strong> '+esc(s.limitations)+'</p>'+
 '<p class="small-note">Documentos públicos: <a href="'+esc(s.metric.source)+'" target="_blank" rel="noopener noreferrer">informe anual FY2026</a> · <a href="'+esc(s.catalyst.source)+'" target="_blank" rel="noopener noreferrer">resultados FY27 Q1</a> · <a href="'+esc(s.quote.source)+'" target="_blank" rel="noopener noreferrer">cierre bursátil histórico de 30/10/2026</a>. No hay cotización en tiempo real ni sincronización automática.</p>');
}

function theses(){
 if(state.issuerMode==="demo")return syntheticTheses();
 const columns=[["ticker","Ticker"],["company","Nombre empresa"],["market","Mercado"],["price","Precio registrado / fecha"],
 ["bull","Bull 5a"],["bear","Bear 5a"],["base","Central 5a"],["entry","Precio 15 %"],
 ["target","Objetivo 5a"],["earnings","Resultados (registro)"],["report","Ficha pública"]];
 const headers=columns.map(([key,label])=>'<th scope="col" aria-sort="'+(state.issuerSort===key?(state.issuerAsc?"ascending":"descending"):"none")+'"><button class="table-sort" type="button" data-action="issuer-column" data-value="'+key+'" aria-label="Ordenar por '+esc(label)+'">'+esc(label)+' <span aria-hidden="true">'+(state.issuerSort===key?(state.issuerAsc?"↑":"↓"):"↕")+'</span></button></th>').join("");
 const found=issuerReadRows().length;
 const screens=state.universe.publicScreens?.length||0;
 const secExpected=state.universe.issuers.filter(i=>i.secCik).length;
 const indexed=state.secRead?.byTicker.size||0;
 return head("TESIS · SEGUIMIENTO PÚBLICO","Investigación de empresas","Tesis, hipótesis y escenarios históricos de Idea Lab. Cada ficha conserva las fechas y cifras de su estudio; no son cotizaciones actuales ni rentabilidades obtenidas.")+
 '<div class="source-health-strip"><div><span class="label">Empresas analizadas</span><strong>'+state.publicTheses.size+' tesis</strong><small>Expedientes históricos publicados</small></div>'+
 '<div><span class="label">Modelos exploratorios</span><strong>'+screens+' modelos</strong><small>Escenarios independientes; no tesis aprobadas</small></div>'+
 '<div><span class="label">Corte documental</span><strong>'+esc(state.publicThesesMetadata?.published_as_of||"N/D")+'</strong><small>Los datos no se recalculan en tiempo real</small></div></div>'+
 disclaimer("N/D indica que el expediente no contiene esa cifra. Los escenarios históricos se conservan con su fecha y sus reservas; el modelo exploratorio independiente se identifica por separado.")+
 '<p class="table-note">Metadatos SEC contrastados: '+indexed+' de '+secExpected+' emisores con identidad SEC contrastada. Los demás expedientes conservan sus pendientes.</p>'+
 '<details class="panel"><summary>Comparar con un CSV local (solo durante esta sesión)</summary><label><strong>CSV local de CAGR2031</strong><input id="cagr-file" type="file" accept=".csv,text/csv"></label><p class="small-note">Lectura temporal y local del archivo, sin envíos al servidor ni alteración de los datos públicos.</p><p role="status">'+(state.localCagrError?esc(state.localCagrError):state.localCagr.size?state.localCagr.size+" registros locales cargados":"Sin CSV adicional")+'</p>'+
 (state.localCagr.size?button("Descartar CAGR locales","issuer-local-clear","","outline-btn"):"")+'</details>'+
 '<div class="filters"><label>Buscar ticker o empresa<input id="issuer-query" type="search" autocomplete="off" placeholder="Ej.: MSFT o Microsoft" value="'+esc(state.issuerQuery)+'"></label>'+
 '<label>Ordenar<select id="issuer-sort">'+columns.map(([k,n])=>'<option value="'+k+'" '+(k===state.issuerSort?"selected":"")+'>'+esc(n)+'</option>').join("")+'</select></label>'+
 button(state.issuerAsc?"↑ Ascendente":"↓ Descendente","issuer-direction","","outline-btn")+
 button("Exportar CSV","export","issuers","outline-btn")+
 button("Tesis ficticias · demo","issuer-mode","demo","outline-btn")+'</div>'+
 '<p id="issuer-visible-count" class="table-note" aria-live="polite">'+found+' de '+researchIssuerCount()+' empresas · CAGR central (2031) descendente; sin cifras al final.</p>'+
 '<div class="table-scroll table-compact thesis-public-table"><table><thead><tr>'+headers+'</tr></thead><tbody id="issuer-rows">'+issuerTableRows()+'</tbody></table></div>'+
 '<p id="issuer-empty" class="table-note" '+(found?'hidden':'')+'>No hay empresas coincidentes.</p>'+
 head("ANÁLISIS","Ficha de tesis / empresa","Cada expediente público documenta qué fuentes y supuestos están acreditados y cuáles faltan.")+
 '<div id="issuer-ficha">'+issuerDetail()+'</div>'+
 disclaimer("Las fichas públicas muestran hipótesis, riesgos y cifras fechadas. Los documentos originales no se abren sin verificar previamente su contenido y permisos.");
}

function officialFxPanel(){
 const source="https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=80&format=csvdata";
 const intro=head("FUENTE PRIMARIA · BCE","EUR/USD · referencia oficial diaria","Primera serie institucional adquirida mediante API del Banco Central Europeo. Un fixing informativo no es una cotización ejecutable, ni valida las estrategias con acciones.");
 if(state.fxStatus!=="ok"||!state.fx||!state.fxCheck)
  return intro+card('<div class="panel-top"><h3>Estado de la serie: '+esc(state.fxStatus==="pending"?"Comprobando fuente":"No disponible o no validada")+'</h3><span class="status-chip">Sin observaciones verificadas</span></div>'+
  '<p>El gráfico y la tabla de datos reales permanecen bloqueados hasta que exista una captura oficial publicada con fecha, dimensiones y hash correctos. No se sustituyen por números simulados.</p>')+
  '<p class="table-note">Origen esperado: <a href="'+source+'" target="_blank" rel="noopener noreferrer">BCE · serie D.USD.EUR.SP00.A</a>. Última publicación institucional no certificada en esta carga.</p>';
 const d=state.fx, v=state.fxCheck, history=d.observations;
 const latest=history.at(-1),previous=history.length>1?history.at(-2):null;
 const change=previous?100*(Number(latest.usd_per_eur)/Number(previous.usd_per_eur)-1):null;
 const stale=v.ageDays>4;
 return intro+
 '<div class="source-health-strip">'+
 '<div><span class="label">Última referencia oficial</span><strong>'+esc(latest.usd_per_eur)+' USD/EUR</strong><small>Fecha de referencia: '+esc(v.date)+'</small></div>'+
 '<div><span class="label">Cobertura aceptada</span><strong>'+v.count+' observaciones</strong><small>ECB EXR · clase referencia diaria</small></div>'+
 '<div><span class="label">Disponibilidad</span><strong class="'+(stale?"perf-negative":"perf-positive")+'">'+(stale?"Fuente desactualizada":"Origen validado")+'</strong><small>Recibida '+esc(v.receivedAt)+' · hace '+v.ageDays+' días</small></div>'+
 '</div>'+
 disclaimer("SOURCE: ECB statistics · Los tipos de cambio de referencia no son precios ejecutables ni implican la posibilidad de operar sin diferencial o comisiones. Esta serie NO alimenta todavía los 23 modelos paper de acciones.")+
 '<div class="metric-strip spaced">'+metric("Último cambio entre fixings",formatPct(change))+
 metric("Primera fecha de muestra",history[0].date)+
 metric("Instrumento", "EUR/USD · 1 EUR en USD")+
 metric("Trazabilidad","SHA-256 publicado")+'</div>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Fecha BCE</th><th class="number">USD por 1 EUR</th><th>Clase</th></tr></thead><tbody>'+
 history.slice(-12).reverse().map(row=>'<tr><td>'+esc(row.date)+'</td><td class="number">'+esc(row.usd_per_eur)+'</td><td>Referencia oficial · no transable</td></tr>').join("")+'</tbody></table></div>'+
 '<p class="table-note">Huella SHA-256 de la respuesta oficial: <code>'+esc(d.source_sha256)+'</code>. <a href="'+source+'" target="_blank" rel="noopener noreferrer">Consultar fuente BCE</a> · <a href="./data/official-fx.json" target="_blank" rel="noopener noreferrer">Ver dataset publicado</a>. Reutilización de estadísticas públicas con atribución al BCE.</p>';
}
function officialYieldPanel(){
 const title=head("TIPOS DE INTERÉS · BCE","Curva AAA de deuda soberana a 10 años","Rentabilidad spot modelizada, nominal y compuesta continuamente para deuda soberana AAA de la zona euro. Referencia de investigación macroeconómica, no bono concreto ni tasa para valorar automáticamente acciones.");
 const uri="https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=60&format=csvdata";
 if(state.yieldStatus!=="ok"||!state.yieldCheck||!state.yieldDoc)
  return title+card('<h3>Serie no disponible o pendiente de validación</h3><p>No se muestra ninguna rentabilidad 10Y inventada. <a href="'+uri+'" target="_blank" rel="noopener noreferrer">Comprobar la fuente oficial del BCE</a>.</p>');
 const checked=state.yieldCheck,values=state.yieldDoc.observations,stale=checked.ageDays>4;
 return title+
 '<div class="source-health-strip"><div><span class="label">Tipo spot · AAA · 10 años</span><strong>'+esc(checked.ratePct.toFixed(3))+' % anual</strong><small>Fecha BCE: '+esc(checked.date)+'</small></div>'+
 '<div><span class="label">Número de observaciones</span><strong>'+checked.count+'</strong><small>Curva Svensson nominal</small></div>'+
 '<div><span class="label">Integridad</span><strong class="'+(stale?"perf-negative":"perf-positive")+'">'+(stale?"Desactualizada":"Origen comprobado")+'</strong><small>Recepción UTC: '+esc(checked.receivedAt)+'</small></div></div>'+
 disclaimer("La curva del BCE modeliza el rendimiento spot de emisores soberanos AAA. No equivale al rendimiento de un instrumento individual, no es tasa libre de riesgo garantizada y NO se introduce automáticamente en los descuentos de flujos, especialmente de empresas en USD.")+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Fecha</th><th class="number">Tipo spot 10Y</th><th>Medición</th></tr></thead><tbody>'+
 values.slice(-10).reverse().map(x=>'<tr><td>'+esc(x.date)+'</td><td class="number">'+esc(x.yield_pct)+' %</td><td>Modelo AAA euro · BCE</td></tr>').join("")+'</tbody></table></div>'+
 '<p class="table-note">Source: ECB statistics · <a href="'+uri+'" target="_blank" rel="noopener noreferrer">Fuente original BCE</a> · <a href="./data/official-eur-yield.json" target="_blank" rel="noopener noreferrer">Datos y hash público</a> · SHA-256 <code>'+esc(checked.sourceSha)+'</code>.</p>';
}

function prospectiveForecastPanel(){
 const title=head("EXPERIMENTO PROSPECTIVO · REFERENCIAS BCE","Registro independiente de señales","Previsiones sobre el próximo fixing oficial EUR/USD, emitidas después de recibir el dato actual. Se evalúan cuando llega la siguiente referencia, sin reconstruir pronósticos a posteriori.");
 if(state.forecastStatus!=="ok"||!state.forecastSummary)
  return title+card('<h3>'+esc(state.forecastStatus==="pending"?"Comprobando el diario de investigación":"Registro no disponible o no verificable")+'</h3><p>Las previsiones y las puntuaciones permanecen ocultas sin un registro público validado. No se reconstruyen sesiones pasadas ni se crean rentabilidades de inversión ficticias.</p>');
 const summary=state.forecastSummary,rows=summary.rows;
 if(!rows.length)
  return title+card('<h3>Pendiente de primera emisión programada</h3><p>El libro ya está versionado y vacío deliberadamente. La primera ejecución institucional registrará solo una previsión pendiente; la exactitud no puede calcularse hasta observar un fixing posterior. No existen resultados prospectivos históricos previos.</p>'+
   '<p class="small-note">Proceso independiente de lunes a viernes: <a href="https://github.com/idealab2026/laboratorio-cuantitativo/actions/workflows/fx-ledger.yml" target="_blank" rel="noopener noreferrer">consultar ejecuciones del diario institucional</a>.</p>');
 const errors=summary.modelMAE;
 const measure=key=>errors[key]===null?"N/D":errors[key].toFixed(6)+" USD/EUR";
 return title+
 '<div class="source-health-strip">'+
 '<div><span class="label">Señales emitidas</span><strong>'+summary.issuedCount+'</strong><small>Tras adquirir una referencia oficial</small></div>'+
 '<div><span class="label">Señales resueltas</span><strong>'+summary.resolvedCount+'</strong><small>Confirmadas con fixing posterior</small></div>'+
 '<div><span class="label">Pendientes</span><strong>'+summary.unresolvedCount+'</strong><small>Nunca se contabilizan como aciertos</small></div></div>'+
 (summary.invalidatedCount?disclaimer("Control de calidad: "+summary.invalidatedCount+" señal(es) anulada(s) por invertir el orden de las observaciones al calcular el primer pronóstico. Se conserva la evidencia original y la invalidación; no se puntúa."):"")+
 disclaimer("Fuente: ECB statistics. Estadísticas de pronóstico en unidades USD/EUR; MAE no mide rentabilidad, riesgo, ejecución ni alfa. El hash de eventos se valida en CI y se ancla al historial institucional de Git.")+
 '<div class="metric-strip spaced">'+metric("MAE · Sin cambio",measure("unchanged"))+
 metric("MAE · Momentum 1",measure("momentum_1"))+metric("MAE · Reversión 1",measure("reversal_1"))+
 metric("Horizonte", "Siguiente fixing oficial")+metric("Anuladas",String(summary.invalidatedCount))+'</div>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Emisión: fecha fixing</th><th>Registrado UTC</th><th class="number">Referencia inicial</th><th class="number">Sin cambio</th><th class="number">Momentum</th><th class="number">Reversión</th><th>Evaluación</th><th class="number">Referencia posterior</th></tr></thead><tbody>'+
 rows.slice(-20).reverse().map(row=>{
  const i=row.issued,o=row.settled,invalid=row.invalidated;
  return '<tr><td>'+esc(i.fixing_date)+'</td><td>'+esc(i.recorded_at_utc)+'</td><td class="number">'+esc(i.observed_rate)+'</td>'+
   '<td class="number">'+esc(i.predictions.unchanged)+'</td><td class="number">'+esc(i.predictions.momentum_1)+'</td><td class="number">'+esc(i.predictions.reversal_1)+'</td>'+
   '<td>'+esc(invalid?"ANULADA · error de fórmula":o?"Evaluado · "+o.realized_fixing_date:"Pendiente · sin resultado")+'</td><td class="number">'+esc(o?o.realized_rate:"N/D")+'</td></tr>';
 }).join("")+'</tbody></table></div>'+
 '<p class="table-note">Registro completo: <a href="./data/fx-forecast-ledger.json" target="_blank" rel="noopener noreferrer">JSON de eventos y hashes</a>. No son operaciones financieras y no se incorporan a la clasificación de las 23 estrategias.</p>';
}

function monitoring(){
 return head("OPERACIÓN PAPER","Ejecución y estado de los diarios","El motor original se traslada conservando sus reglas, capital virtual y libros. La actualización programada se verifica mediante sus ejecuciones y registros de mercado.")+
 card('<h3>Fuente de los diarios</h3><p>'+(state.originalPaper?"Archivo del motor disponible · "+state.originalPaper.count+" diarios · último cierre "+esc(state.originalPaper.latest):"Comprobando el registro público del motor.")+'</p><a href="https://github.com/idealab2026/laboratorio-cuantitativo/actions" target="_blank" rel="noopener noreferrer">Ver ejecuciones de los motores</a>')+
 '<details class="panel"><summary>Herramientas didácticas con datos artificiales</summary>'+syntheticMonitoring()+'</details>';
}
function syntheticMonitoring(){
 const s=active(),audit=causalLedger();
 return officialYieldPanel()+officialFxPanel()+prospectiveForecastPanel()+head("SALUD OPERATIVA · DIARIO","Procedencia, ejecución y operaciones","Diferencia entre disponibilidad de fuentes, ejecución del motor y estado de cada diario. Sin fuente y persistencia institucional no se declara funcionamiento autónomo.")+
 '<div class="source-health-strip">'+
 '<div><span class="label">OHLC diario externo</span><strong>Yahoo / yfinance · workflow preparado</strong><small>Fuente original, 503 + SPY, captura y paper con código público. Ingesta condicionada a derechos de uso.</small></div>'+
 '<div><span class="label">Cobertura del universo real</span><strong>N/D</strong><small>Instrumentos del experimento: 3 activos ficticios; cotizaciones de mercado ausentes</small></div>'+
 '<div><span class="label">Salud de automatismos</span><strong>Paper bursátil no activado</strong><small>GitHub Actions verifica el runner. Sin autorización de la fuente no crea sesiones ni rentabilidades; las 23 estrategias siguen sintéticas.</small></div>'+
 '</div>'+
 disclaimer("Fuente original identificada: Yahoo Finance mediante yfinance, con universo congelado de 503 acciones y SPY aparte. El contrato está preparado para validación offline, pero la colección institucional, la publicación de cotizaciones, los snapshots diarios y el productor paper NO están habilitados. No existe todavía un registro de cotizaciones reales en IDEA LAB.")+
 '<div class="section-grid three">'+
 card('<span class="label">UNIVERSO DEMO</span><h3>3 activos artificiales</h3><p>La serie '+esc(state.data.dates[0])+'–'+esc(state.data.dates.at(-1))+' no equivale a un calendario de cotización. Origen: generador matemático.</p>')+
 card('<span class="label">ÓRDENES PAPER</span><h3>Sin persistencia</h3><p>Los libros se generan al abrir la página y no son prueba de una sesión automática ni de operaciones en mercado.</p>')+
 card('<span class="label">ÚLTIMA EVIDENCIA VERIFICADA</span><h3>No disponible</h3><p>No se informa de runs, cierres bursátiles ni actualización de carteras sin confirmar ambos registros.</p>')+'</div>'+
 head("OPERACIONES","Diario de órdenes simuladas","El libro de órdenes documenta compra o venta, unidades, referencia y coste por sesión.")+
 '<div class="filters"><label>Algoritmo<select id="journal-select">'+all().map(x=>'<option value="'+esc(x.id)+'" '+(x.id===state.strategy?"selected":"")+'>'+esc(x.name)+'</option>').join("")+'</select></label>'+button("Exportar diario CSV","export","journal","outline-btn")+'</div>'+
 '<div class="metric-strip spaced">'+metric("Órdenes",String(s.orders.length))+metric("Valor final",money(s.points.at(-1).equity))+metric("Costes",money(s.fees))+metric("Cobertura","100 %")+'</div>'+
 '<div class="table-scroll"><table><thead><tr><th>Sesión</th><th>Activo</th><th>Acción</th><th class="number">Referencia</th><th class="number">Unidades</th><th class="number">Nocional</th><th class="number">Coste</th><th>Tipo</th></tr></thead><tbody>'+s.orders.slice(-30).reverse().map(x=>'<tr><td>'+esc(x.session)+'</td><td>'+esc(x.symbol)+'</td><td>'+esc(x.action)+'</td><td class="number">'+money(x.referencePrice)+'</td><td class="number">'+fmt(x.units)+'</td><td class="number">'+money(x.notional)+'</td><td class="number">'+money(x.cost)+'</td><td>PAPER</td></tr>').join("")+'</tbody></table></div>'+
 disclaimer("Las órdenes del catálogo anterior valoran la ejecución al cierre previo: son ilustrativas y no deben utilizarse como backtest ejecutable.")+
 head("PROTOCOLO CAUSAL","Ejecución paper en apertura siguiente","Motor alternativo independiente: regla de tendencia con cierres anteriores, apertura posterior, posiciones, comisiones y deslizamiento. No reemplaza aún la competición.")+
 '<div class="metric-strip spaced">'+metric("Rendimiento sintético",formatPct(audit.returnPct))+metric("Órdenes next-open",String(audit.orders.length))+metric("Comisiones ficticias",money(audit.fees))+metric("Deslizamiento teórico",money(audit.slippage))+'</div>'+
 '<p class="table-note">Señal al cierre de la sesión previa; transacción a la apertura de la siguiente. Aperturas, máximos y mínimos DERIVADOS ARTIFICIALMENTE de datos ficticios. Sin datos de bolsa ni inferencia estadística.</p>'+
 '<div class="filters">'+button("Exportar libro causal CSV","export","next-open","outline-btn")+'</div>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Señal al cierre</th><th>Fill en apertura</th><th>Activo</th><th>Acción</th><th class="number">Apertura sintética</th><th class="number">Precio paper</th><th class="number">Unidades</th><th class="number">Comisión</th></tr></thead><tbody>'+audit.orders.slice(-15).reverse().map(o=>
 '<tr><td>'+esc(o.signalAt)+'</td><td>'+esc(o.fillAt)+'</td><td>'+esc(o.symbol)+'</td><td>'+esc(o.side)+'</td><td class="number">'+esc(fmt(o.openPrice))+'</td><td class="number">'+esc(fmt(o.fillPrice))+'</td><td class="number">'+esc(fmt(o.units))+'</td><td class="number">'+esc(fmt(o.fee))+'</td></tr>'
 ).join("")+'</tbody></table></div>'+
 disclaimer("Prototipo analítico next-open. No acredita precisión predictiva ni rentabilidad real; no hay broker, cotizaciones externas, motor de persistencia ni ejecución programada.");
}
let replayCache=null;
const replay=()=>replayCache||(replayCache=artificialCampaignComparison());
function paperAccountingView(){
 const run=replay(),rows=[...run.ranking].sort((a,b)=>b.returnPct-a.returnPct);
 const chosen=run.config.strategies.find(x=>x.id===state.paperDetail)||run.config.strategies[0];
 const book=run.state.portfolios[chosen.id];
 return head("CONTABILIDAD · EXPERIMENTO ARTIFICIAL","Nueve carteras paper aisladas","Señales al cierre y ejecución modelizada en la apertura posterior, con efectivo, comisiones, stops, objetivos y apuntes. Los datos han sido generados matemáticamente; la curva NO es una rentabilidad bursátil ni un diario prospectivo.")+
 '<div class="source-health-strip"><div><span class="label">Carteras independientes</span><strong>'+rows.length+'</strong><small>Capital inicial: 100.000 USD artificiales por cartera · 8 activos y un índice ficticios</small></div>'+
 '<div><span class="label">Sesiones de cálculo</span><strong>'+run.measuredSessions+'</strong><small>Las primeras 79 velas se usan exclusivamente como precalentamiento</small></div>'+
 '<div><span class="label">Capital real invertido</span><strong>0 USD</strong><small>Sin broker, sin órdenes bursátiles y sin registro externo</small></div></div>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Regla</th><th class="number">Capital simulado</th><th class="number">Rendimiento</th><th class="number">Drawdown</th><th class="number">Comisiones</th><th class="number">Fills</th><th class="number">Omisiones</th><th>Actividad</th><th>Ficha</th><th>Curva</th></tr></thead><tbody>'+
 rows.map(r=>'<tr><td><strong>'+esc(methodCatalog.find(x=>x.id===r.method)?.name||r.id)+'</strong></td>'+
 '<td class="number">'+esc(fmt(r.equity))+' USD</td><td class="number">'+pctText(r.returnPct)+'</td>'+
 '<td class="number">'+pctText(r.drawdownPct)+'</td><td class="number">'+esc(fmt(r.fees))+'</td><td class="number">'+r.fills+'</td><td class="number">'+r.missedDecisions+'</td>'+
 '<td>'+esc(r.active.join(", ")||"Sin posición")+(r.pending.length?" · Orden pendiente":"")+'</td><td>'+
 button("Ver diario","paper-select",r.id)+'</td><td>'+sparkline(run.state.portfolios[r.id].equity.map(x=>x.nav))+'</td></tr>').join("")+'</tbody></table></div>'+
 card('<h3>Diario artificial · '+esc(chosen.method)+'</h3>'+
 '<p>Órdenes contabilizadas: '+book.events.filter(x=>x.type==="FILL").length+'. Posiciones: '+Object.keys(book.holdings).length+
 '. Comisiones acumuladas: '+esc(fmt(book.feeTotal))+' USD. Los eventos se muestran para comprobar la causalidad, no como transacciones de bolsa.</p>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Sesión</th><th>Tipo</th><th>Activo</th><th>Origen señal</th><th class="number">Precio de fill</th><th class="number">Comisión</th></tr></thead><tbody>'+
 book.events.slice(-12).reverse().map(e=>'<tr><td>'+esc(e.date)+'</td><td>'+esc(e.type+(e.side?" · "+e.side:""))+'</td>'+
 '<td>'+esc(e.symbol)+'</td><td>'+esc(e.signalAt||"—")+'</td><td class="number">'+(e.price===undefined?"—":esc(fmt(e.price)))+
 '</td><td class="number">'+(e.fee===undefined?"—":esc(fmt(e.fee)))+'</td></tr>').join("")+'</tbody></table></div>')+
 disclaimer("ESTADO: reproducción artificial retroactiva para comprobar funcionamiento. No se importan ni sustituyen las posiciones, las estrategias de la clasificación principal ni el histórico privado.");
}
function ported(){
 const report=signalResearchSummary();
 return head("MOTOR DE SEÑALES · AISLADO","Nueve reglas reproducibles","Implementación institucional independiente de políticas técnicas observadas en el catálogo. Esta vista calcula señales con 130 velas enteramente artificiales. No representa operaciones, rendimiento prospectivo ni equivalencia certificada del motor anterior.")+
 '<div class="source-health-strip"><div><span class="label">Reglas verificables</span><strong>'+report.methods.length+'</strong><small>Al cierre, sin datos posteriores</small></div>'+
 '<div><span class="label">Sesiones artificiales</span><strong>'+report.sessions+'</strong><small>'+esc(report.first)+' a '+esc(report.last)+' · calendario generado</small></div>'+
 '<div><span class="label">Carteras en replay artificial</span><strong>9</strong><small>Contabilidad simulada; sin fuente real ni broker</small></div></div>'+
 disclaimer("La codificación de estas reglas técnicas ya puede revisarse y probarse en IDEA LAB. Aún NO se ha transferido el motor privado de ejecución, su historial, modelo entrenado ni cotización real; las 23 filas de la competición son otra simulación independiente.")+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Regla</th><th>Familia</th><th>Parámetros fijos</th><th>Última señal sintética</th><th class="number">Compras / 30</th><th class="number">Ventas / 30</th><th class="number">Mantener / 30</th><th>Operativa</th></tr></thead><tbody>'+
 report.methods.map(m=>'<tr><td><strong>'+esc(m.name)+'</strong><small class="smallline">'+esc(m.id)+'</small></td>'+
 '<td>'+esc(m.family)+'</td><td>'+esc(m.parameters)+'</td><td><strong>'+esc(m.currentSignal)+'</strong><small class="smallline">Simulación: '+esc(report.last)+'</small></td>'+
 '<td class="number">'+m.recentBuy+'</td><td class="number">'+m.recentSell+'</td><td class="number">'+m.recentHold+'</td>'+
 '<td>Solo regla · sin órdenes</td></tr>').join("")+'</tbody></table></div>'+
 card('<h3>Contratos necesarios para la ejecución de las carteras</h3>'+
 '<p>Una fuente independiente de OHLC completos y autorizados, fecha de disponibilidad verificable, campañas por divisa/calendario, costes y corporate actions conciliados, configuración inmutable por estrategia, señales grabadas antes de la siguiente apertura, diario persistente y control de sesiones omitidas.</p>'+
 '<p>Hasta comprobar esas condiciones, este módulo expone exclusivamente lógica técnica; no calcula resultados bursátiles ficticios con nombres reales.</p>')+
 paperAccountingView()+
  button("Revisar simulador next-open existente","navigate","monitoring","outline-btn")+
 button("Ver competición sintética","navigate","competition","outline-btn");
}

function economicPaperRecord(slot){
 const current=state.paperFeedRead?.bySlot.get(slot);
 if(current)return {...current,session_count:current.history.length,
   sourceId:state.originalPaper?.bySlot.get(slot)?.sourceId||null};
 const original=state.originalPaper?.bySlot.get(slot);if(original)return original;
 const h=state.historicalPaper?.get(slot);if(!h?.active)return null;
 return {activity:"Paper · "+(h.activity==="demo_con_diario"?"Diario registrado":h.activity.replaceAll("_"," ")),currency:h.currency,first_session:h.first,session_count:h.sessions,initial_capital:h.capital,last_equity:h.nav,last_session:h.last,
  return_pct:h.pct,day_return_pct:h.dayPct,positions:h.positions,pending_orders:h.pending,
  risk:{volatility_pct:null,max_drawdown_pct:h.drawdown},comparison:{eligible:false},
  history:state.historicalCurves.get(slot)||[],historical:true};
}
function originalStrategyName(item){
 return state.originalPaper?.labels?.get(item.slot)||item.name;
}
function compactGroup(group){
 return ({
  "US · Cartera original 8 activos":"8 activos","S&P 500 · cartera ampliada":"S&P 500",
  "ML semanal · vigente":"ML semanal","ML semanal · legado":"ML legado",
  "Selección multicriterio · riesgo":"Multicriterio","Ciclo de capital":"Ciclo capital",
  "Compra en caídas":"Buy The Dip","TimesFM · semanal":"TimesFM sem.",
  "TimesFM · diario":"TimesFM día","Genético · histórico":"Genético",
  "Predicción cuantitativa · cuatro enfoques":"Predicción",
  "Investigación histórica":"Histórico"
 })[group]||group;
}
function shortPaperDate(raw){
 return typeof raw==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(raw)
  ?raw.slice(8)+"/"+raw.slice(5,7)+"/"+raw.slice(2,4):"N/D";
}
function compactCell(label,html,cls="",tooltip=""){
 // Display absence explicitly; never convert missing economic data to zero.
 const display=html==="N/D"?'<span class="unverified-text">No verificable</span>':html;
 return '<td data-label="'+esc(label)+'"'+(cls?' class="'+esc(cls)+'"':"")+
  (tooltip?' title="'+esc(tooltip)+'"':"")+'>'+display+'</td>';
}
function sortedFullRosterRows(){
 if(!state.fullRoster)return [];
 const q=state.fullRosterQuery.trim().toLocaleLowerCase("es");
 const existing=filterRoster(state.fullRoster,{group:state.fullRosterGroup}).filter(item=>
  !q||[item.slot,item.group,item.name,originalStrategyName(item)].some(x=>x.toLocaleLowerCase("es").includes(q))
 ).map(item=>({id:item.slot,name:originalStrategyName(item),group:item.group,
  item,record:economicPaperRecord(item.slot),candidate:null}));
 const proposals=state.strategyCandidates?
  filterStrategyCandidates(state.strategyCandidates,{group:state.fullRosterGroup,query:state.fullRosterQuery}).map(candidate=>({
   id:candidate.id,name:candidate.name,group:candidate.group,item:null,record:null,candidate
  })):[];
 return sortFullCompetitionRows([...existing,...proposals],{key:state.fullRosterSort,ascending:state.fullRosterAsc});
}
const FULL_COMPETITION_COLUMNS=[
 ["name","Estrategia / ID"],["group","Familia"],["activity","Actividad"],
 ["start","Inicio"],["sessions","Sesiones"],["date","Último cierre"],
 ["currency","Divisa"],["return","Rent. acumulada"],["day","Rent. día"],
 ["drawdown","Drawdown"],["comparison","Comparabilidad"],["detail","Detalle"]
];
const COMPARABILITY_EXPLANATION=[
 "La comparabilidad indica si dos rentabilidades paper cuentan con una base metodológica homogénea acreditada.",
 "Para compararlas se deben contrastar fechas de inicio, universo invertible, divisa, reglas de valoración, costes y grupo de comparación.",
 "«Mismo grupo de comparación»: el registro declara elegibilidad; no garantiza por sí solo equivalencia de todos los supuestos.",
 "«No comparable»: falta evidencia suficiente para compararlas directamente.",
 "«Archivo»: campaña histórica separada. «Investigación»: todavía sin operaciones ni valor liquidativo."
].join(" ");
function comparabilityHelp(id){
 return '<span class="comparison-help-wrap">'+
 '<button type="button" class="comparison-help-icon" aria-label="¿Qué significa comparabilidad?" '+
 'aria-describedby="'+id+'">ⓘ</button>'+
 '<span class="comparison-help-popup" id="'+id+'" role="tooltip">'+esc(COMPARABILITY_EXPLANATION)+'</span></span>';
}
function fullRosterHeaders(){
 return FULL_COMPETITION_COLUMNS.map(([key,label])=>{
  if(key==="detail")return '<th scope="col">Detalle</th>';
  const selected=key===state.fullRosterSort;
  const arrow=selected?(state.fullRosterAsc?" ↑":" ↓"):" ↕";
  const numeric=["return","day","sessions","drawdown"].includes(key);
  const aria=selected?(state.fullRosterAsc?"ascending":"descending"):"none";
  return '<th scope="col" aria-sort="'+aria+'"'+(key==="comparison"?' class="comparison-header"':numeric?' class="number"':'')+
   '><button type="button" class="table-sort" data-action="full-column" data-value="'+key+
   '" aria-label="Ordenar '+label+'" title="Ordenar '+label+'">'+label+
   '<span class="sort-indicator" aria-hidden="true">'+arrow+'</span></button>'+
   (key==="comparison"?comparabilityHelp("competition-comparability-tip"):"")+'</th>';
 }).join("");
}
function fullMobileSortControls(){
 return '<div class="competition-mobile-sort"><label>Ordenar por <select id="full-mobile-sort" aria-label="Columna de ordenación">'+
  FULL_COMPETITION_COLUMNS.filter(([key])=>key!=="detail").map(([key,label])=>'<option value="'+key+'"'+
   (key===state.fullRosterSort?' selected':'')+'>'+label+'</option>').join("")+
  '</select></label>'+button(state.fullRosterAsc?"Ascendente ↑":"Descendente ↓","full-sort-direction","toggle","outline-btn")+
  comparabilityHelp("competition-comparability-tip-mobile")+'</div>';
}
function fullRosterRows(){
 return sortedFullRosterRows().map(({id,name,group,record,candidate})=>{
  const identity=compactCell("Estrategia",
   '<strong class="full-strategy-name" title="'+esc(name)+'">'+esc(name)+'</strong>'+
   '<small class="smallline">'+esc(id)+(candidate?' · Investigación':'')+'</small>');
  const familyCell=compactCell("Familia",
   '<span class="clamped-cell">'+esc(compactGroup(group))+'</span>',"family-cell",group);
  const more=compactCell("Detalle",button("Ver detalle","full-detail",id,"outline-btn"),"detail-cell");
  if(candidate)return '<tr class="competition-row">'+identity+familyCell+
   compactCell("Actividad",'<span class="clamped-cell">En investigación</span>',"activity-cell",candidate.status)+
   compactCell("Inicio","N/D","date-cell")+compactCell("Sesiones","N/D","number")+
   compactCell("Último cierre","N/D","date-cell")+
   compactCell("Divisa","N/D","currency-cell")+
   compactCell("Rent. acumulada","N/D","number")+
   compactCell("Rent. día","N/D","number")+
   compactCell("Drawdown","N/D","number")+
   compactCell("Comparabilidad","Investigación","comparison-cell","Sin operaciones ni NAV; no comparable")+
   more+'</tr>';
  const activity=record?.activity??"Sin diario institucional";
  const risk=record?.risk||{},last=record?.last_session||"";
  const compare=record?.historical?"Archivo":record?.comparison?.eligible?"Mismo grupo":"No comparable";
  const compareExplanation=record?.historical?"Corte histórico · grupos de comparación separados":
   record?.comparison?.eligible?"Solo comparable dentro del grupo de comparación verificado":"Sin evidencia comparable";
  const start=record?.first_session||null;
  const sessions=record?.session_count;
  return '<tr class="competition-row">'+identity+familyCell+
   compactCell("Actividad",'<span class="clamped-cell">'+esc(activity.replace(/^Paper\s*·\s*/,""))+'</span>',"activity-cell",activity)+
   compactCell("Inicio",esc(shortPaperDate(start)),"date-cell",start||"Sin fecha acreditada")+
   compactCell("Sesiones",Number.isInteger(sessions)&&sessions>0?esc(sessions):"N/D","number")+
   compactCell("Último cierre",esc(shortPaperDate(last)),"date-cell",last)+
   compactCell("Divisa",esc(record?.currency||"N/D"),"currency-cell")+
   compactCell("Rent. acumulada",record&&finite(record.return_pct)?pctText(record.return_pct):"N/D","number")+
   compactCell("Rent. día",record&&finite(record.day_return_pct)?pctText(record.day_return_pct):"N/D","number")+
   compactCell("Drawdown",record&&finite(risk.max_drawdown_pct)?pctText(risk.max_drawdown_pct):"N/D","number")+
   compactCell("Comparabilidad",esc(compare),"comparison-cell",compareExplanation)+
   more+'</tr>';
 }).join("");
}

function full(){
 const d=state.fullRoster;
 if(!d)return '<div class="competition-heading"><h2>Clasificación de algoritmos</h2></div>'+
  card('<p>Inventario institucional no verificable. No se muestran rentabilidades inventadas.</p>');
 const meta=verifyFullRoster(d);
 const candidate=state.strategyCandidates?.candidates?.[0]||null;
 const leader=paperLeaderboard(d.entries.map(item=>({
  id:item.slot,name:originalStrategyName(item),record:economicPaperRecord(item.slot)
 })));
 const winner=leader?'<div class="paper-leader" role="status" aria-label="Algoritmo líder por rentabilidad acumulada histórica">'+
  '<div><span class="paper-leader-label">LÍDER PROVISIONAL · RENTABILIDAD ACUMULADA PAPER</span>'+
  '<strong>'+esc(leader.name)+'</strong>'+
  '<small>'+esc(leader.id)+' · inicio '+esc(shortPaperDate(leader.record.first_session))+
  ' · '+esc(leader.record.session_count)+' sesiones · último cierre '+esc(shortPaperDate(leader.record.last_session))+'</small></div>'+
  '<div class="paper-leader-return">'+pctText(leader.record.return_pct)+'</div>'+
  button("Ver ficha","full-detail",leader.id,"outline-btn")+'</div>':
  '<div class="paper-leader"><strong>Sin líder verificable</strong><small>No hay diarios con retorno, inicio y sesiones contrastados.</small></div>';
 return '<div class="competition-heading"><h2>Clasificación de algoritmos</h2>'+
  '<span>'+meta.count+' estrategias · '+(candidate?"1 propuesta sin operativa · ":"")+
  'archivo paper con precios de mercado</span></div>'+
  winner+
  fullMobileSortControls()+
  '<div class="table-scroll table-compact full-competition-table"><table><thead><tr>'+
  fullRosterHeaders()+'</tr></thead><tbody id="full-rows">'+fullRosterRows()+
  '</tbody></table></div>';
}
function fullHistoryChart(points){
 if(!Array.isArray(points)||points.length<2)return "";
 const values=points.map(p=>p.nav);
 if(values.some(x=>!finite(x)))return "";
 const low=Math.min(...values),high=Math.max(...values),range=Math.max(high-low,1);
 const coords=values.map((v,i)=>[
  (30+830*i/(values.length-1)).toFixed(1),
  (190-145*(v-low)/range).toFixed(1)]);
 return '<svg class="paper-history-chart" viewBox="0 0 900 225" role="img" aria-label="Evolución del capital paper por sesión">'+
  '<line x1="30" y1="190" x2="870" y2="190" stroke="#cedae4" stroke-width="1"/>'+
  '<polyline points="'+coords.map(p=>p.join(",")).join(" ")+
  '" fill="none" stroke="#205c87" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'+
  '<text x="32" y="214" class="chart-label">'+esc(points[0].date)+'</text>'+
  '<text x="870" y="214" text-anchor="end" class="chart-label">'+esc(points.at(-1).date)+'</text>'+
  '</svg>';
}
function algorithmFiche(){
 const id=state.algorithmId;
 const item=state.fullRoster?.entries.find(s=>s.slot===id);
 const candidate=state.strategyCandidates?.candidates.find(c=>c.id===id);
 if(!item&&!candidate)return '<div class="competition-heading"><h2>Ficha no disponible</h2></div>'+
  button("Volver a la competición","navigate","competition","outline-btn");
 const name=candidate?.name||originalStrategyName(item);
 const group=candidate?.group||item.group;
 const record=item?economicPaperRecord(id):null;
 const sourceId=record?.sourceId||state.originalPaper?.bySlot.get(id)?.sourceId||"";
 const method=algorithmTheory(sourceId,group);
 const history=record?.history||[];
 const sessions=record?.session_count??(history.length||null);
 const fmtMoney=n=>finite(n)?fmt(n)+" "+esc(record?.currency||""):"N/D";
 const stats='<div class="algorithm-stat-grid">'+[
  ["Rentabilidad acumulada",record?pctText(record.return_pct):"N/D"],
  ["Primera sesión",esc(shortPaperDate(record?.first_session))],
  ["Sesiones registradas",Number.isInteger(sessions)&&sessions>0?esc(sessions):"N/D"],
  ["Último cierre",esc(shortPaperDate(record?.last_session))],
  ["Capital inicial",fmtMoney(record?.initial_capital)],
  ["NAV final",fmtMoney(record?.last_equity)]
 ].map(([label,value])=>'<div><small>'+label+'</small><strong>'+value+'</strong></div>').join("")+'</div>';
 const measured=history.length?
  '<section class="algorithm-section"><h3>Evolución de capital y sesiones</h3>'+
  '<p>Diario paper procedente del archivo contrastado; no es dinero real ni prueba de ejecución diaria actual.</p>'+
  fullHistoryChart(history)+
  '<details><summary>Consultar las '+history.length+' observaciones del NAV</summary>'+
  '<div class="table-scroll"><table class="table-compact"><thead><tr><th>Sesión</th><th>NAV</th><th>Rentabilidad desde el inicio</th></tr></thead><tbody>'+
  history.map(p=>'<tr><td>'+esc(p.date)+'</td><td>'+fmtMoney(p.nav)+'</td><td>'+
   (finite(record?.initial_capital)&&record.initial_capital>0?pctText(100*(p.nav/record.initial_capital-1)):"N/D")+
   '</td></tr>').join("")+'</tbody></table></div></details></section>':
  '<section class="algorithm-section"><h3>Evolución y sesiones</h3><p>Sin diario verificable: no existen rentabilidades ni operaciones acreditadas para esta línea.</p></section>';
 const theory=candidate?
  '<section class="algorithm-section"><h3>Teoría e hipótesis</h3><p>'+esc(candidate.subject)+'</p>'+
  '<h4>Diseño metodológico</h4><p>'+esc(candidate.method)+'</p>'+
  '<h4>Regla de investigación</h4><p>'+esc(candidate.rule)+'</p>'+
  '<h4>Matemática</h4><p>La propuesta no dispone todavía de una formulación estimada ni de parámetros contrastados. No se sustituirán por fórmulas ilustrativas.</p></section>':
  '<section class="algorithm-section"><h3>Teoría y fundamento</h3><p>'+esc(method.theory)+'</p>'+
  '<h4>Formulación matemática de referencia</h4><div class="algorithm-formula">'+esc(method.equation)+'</div>'+
  '<p class="algorithm-caveat">'+esc(method.scope)+'</p>'+
  '<h4>Reglas y señales</h4><p>'+esc(method.signal)+'</p></section>';
 const progress=candidate?
  '<p><strong>Fase:</strong> '+esc(candidate.status)+'</p>'+
  '<p><strong>Datos necesarios:</strong> '+esc(candidate.research_requirements)+'</p>'+
  '<p><strong>Validación:</strong> '+esc(candidate.validation)+'</p>'+
  '<p><strong>Limitaciones:</strong> '+esc(candidate.limitations)+'</p>'+
  '<p><a href="'+esc(candidate.source)+'" target="_blank" rel="noopener noreferrer">Fuente académica</a> · '+
  '<a href="'+esc(candidate.data_reference)+'" target="_blank" rel="noopener noreferrer">Datos exploratorios</a></p>':
  '<p><strong>Campaña / evolución:</strong> '+esc(record?.provenance||
   "Documentación de la campaña disponible parcialmente; no se reconstruye la historia de versiones sin pruebas.")+'</p>'+
  '<p><strong>Estado histórico:</strong> '+esc(record?.activity||"Sin diario institucional")+'</p>'+
  '<p><strong>Notas del registro:</strong> '+esc(record?.sourceNote||"No constan notas de desarrollo versionadas para este expediente.")+'</p>'+
  '<p><strong>Motor institucional nuevo:</strong> '+esc(technicalStage(id).label)+
  '. El histórico del motor anterior no acredita que este motor ya esté ejecutándose.</p>'+
  '<p><strong>Control científico:</strong> '+esc(method.validation)+'</p>';
 return '<div class="algorithm-profile">'+
  '<div class="algorithm-breadcrumb">'+button("← Volver a la tabla","navigate","competition","outline-btn")+
  '<span>'+esc(id)+' · '+esc(compactGroup(group))+'</span></div>'+
  '<header class="algorithm-profile-header"><h2>'+esc(name)+'</h2>'+
  '<p>'+esc(candidate?"Propuesta de investigación · sin operaciones":
   "Campaña de capital virtual · "+(record?.historical?"corte histórico":"diario paper registrado"))+
  ' · información disponible, no rentabilidad futura garantizada</p></header>'+
  stats+theory+
  '<section class="algorithm-section"><h3>Desarrollo, cambios y validación</h3>'+progress+
  '<p class="algorithm-caveat">Las fechas indicadas corresponden a las sesiones NAV, no necesariamente a la fecha de creación del algoritmo. Una cronología técnica completa exige commits y versiones acreditados.</p></section>'+
  measured+(state.operationsAudit?renderOperationsAudit(state.operationsAudit,id,state.auditTicker,{tab:state.auditTab,sort:state.auditSort,desc:state.auditDesc}):
   '<section class="algorithm-section"><h3>Operaciones por sesión y motivos</h3><p>'+
   (state.operationsAuditStatus==="pending"?"Comprobando el registro de órdenes…":"Libro de operaciones individuales no disponible; no se reconstruyen operaciones sin evidencia.")+
   '</p></section>')+'</div>';
}

function archive(){
 const groupsInCatalog=state.fullRoster?verifyFullRoster(state.fullRoster).groups:[];
 const count=state.originalPaper?.count||(state.historicalPaper?[...state.historicalPaper.values()].filter(x=>x.active).length:0);
 return head("CATÁLOGO · HISTÓRICO","Estrategias y campañas paper","Los diarios originales se conservan con su capital virtual, fechas y universos. Las campañas separadas no se fusionan como una sola rentabilidad.")+
 '<div class="source-health-strip"><div><span class="label">Estrategias registradas</span><strong>64</strong><small>12 familias metodológicas</small></div>'+
 '<div><span class="label">Diarios paper recuperados</span><strong>'+count+'</strong><small>Operaciones simuladas con datos de mercado</small></div>'+
 '<div><span class="label">Último cierre disponible</span><strong>'+esc(state.originalPaper?.latest||"—")+'</strong><small>Consultar fecha y estado de cada estrategia</small></div></div>'+
 disclaimer("La disponibilidad de los diarios históricos y del código no prueba por sí sola la continuidad automática de todas las estrategias desde Idea Lab. Las valoraciones pausadas y las ausencias de cotización se conservan explícitamente.")+
 '<div class="family-grid">'+groupsInCatalog.map(g=>card('<h3>'+esc(g.name)+'</h3><p>'+g.count+' estrategias registradas.</p>'+button("Ver diarios de esta familia","navigate","competition","outline-btn"))).join("")+'</div>'+
 '<details class="panel"><summary>Ejemplos didácticos con precios artificiales</summary><p>Los 23 prototipos didácticos se conservan aparte; sus resultados no pertenecen a los diarios paper de mercado.</p>'+button("Abrir demo didáctica","navigate","synthetic","outline-btn")+'</details>'+
 button("Volver a la competición paper","navigate","competition","outline-btn");
}

function glossaryRows(query=""){
 const rows=searchGlossary(query);
 if(!rows.length)return '<p class="glossary-empty">No hay conceptos que coincidan con la búsqueda. Prueba otro término.</p>';
 return glossaryGroups.map(group=>{
  const terms=rows.filter(x=>x.group===group);
  if(!terms.length)return "";
  return '<section class="glossary-group"><h3>'+esc(group)+'</h3><dl class="glossary-grid">'+
   terms.map(x=>'<div class="glossary-entry"><dt>'+esc(x.term)+'</dt><dd>'+esc(x.description)+'</dd></div>').join("")+
   '</dl></section>';
 }).join("");
}
function glossary(){
 const stats=verifyGlossary();
 return head("CONCEPTOS DE MIDAS","Glosario financiero y cuantitativo",
  "Explicaciones breves de los términos especializados que aparecen en la competición, las tesis de inversión y la auditoría de datos.")+
  '<div class="glossary-tools"><label for="glossary-query">Buscar un término</label>'+
  '<input id="glossary-query" type="search" placeholder="Ej.: grupo de comparación, CAGR, drawdown, NAV…" autocomplete="off" aria-label="Buscar un concepto en el glosario">'+
  '<span id="glossary-count" role="status">'+stats.entries+' conceptos explicados</span></div>'+
  '<div id="glossary-results" class="glossary-results">'+glossaryRows()+'</div>';
}
function methodology(){
 return head("MÉTODO Y LÍMITES","Evaluación reproducible","Los motores originales y sus diarios paper están publicados. La ejecución automática desde Idea Lab se verifica por separado; disponer de código e históricos no demuestra que todos los modelos estén actualizados.")+
 '<div class="method-grid">'+[
 ["Reloj causal","Cada motor conserva su contrato temporal y sus controles de disponibilidad. Una operación paper debe respetar la fecha de señal y la siguiente apertura; no se reconstruyen decisiones con información posterior."],
 ["Contabilidad paper","El dinero es virtual. Los diarios de mercado registran posiciones, órdenes y valoración; costes, divisa y reglas dependen de cada campaña. La demo didáctica usa precios artificiales y se muestra aparte."],
 ["Comparaciones","Comparar sólo campañas con fechas, universo, referencia y reglas compatibles. No mezclar distintos grupos de comparación históricos ni presentar una simulación como rentabilidad con dinero real."],
 ["Tesis","Valoraciones bajo hipótesis, crecimiento, múltiplos y rentabilidad requerida, con criterios de refutación."],
 ["Estado de los modelos","El código migrado incluye motores clásicos, aprendizaje semanal, series temporales y evolución paramétrica. Cada estrategia conserva su estado; los modelos o datos ausentes no se sustituyen por resultados inventados."],
 ["Auditoría pública","Datos licenciados, fuentes temporales, validación fuera de muestra, trazabilidad y monitorización antes de atribuir capacidad predictiva."]
 ].map(([a,b])=>card('<h3>'+esc(a)+'</h3><p>'+esc(b)+'</p>')).join("")+'</div>'+
 disclaimer("Todos los activos del sitio se publican mediante una lista blanca. Que los archivos nuevos carezcan de referencias personales no demuestra anonimato absoluto si existe material anterior correlacionable.");
}
function svgEl(name,props={},value){const el=document.createElementNS("http://www.w3.org/2000/svg",name);Object.entries(props).forEach(([k,v])=>el.setAttribute(k,String(v)));if(value!==undefined)el.textContent=String(value);return el;}
function chart(){
 const svg=$("nav-chart");if(!svg)return;
 const n=active().nav,low=Math.min(...n)-2,high=Math.max(...n)+2;
 svg.replaceChildren();
 const x=i=>55+i*675/(n.length-1),y=v=>231-(v-low)*180/(high-low);
 for(let j=0;j<5;j++){const v=low+(high-low)*j/4,yy=y(v);svg.append(svgEl("line",{x1:55,x2:730,y1:yy,y2:yy,stroke:"#dbe3ea"}),svgEl("text",{x:5,y:yy+4,fill:"#60758b","font-size":11},v.toFixed(1)));}
 svg.append(svgEl("polyline",{points:n.map((v,i)=>x(i)+","+y(v)).join(" "),fill:"none",stroke:"#143b67","stroke-width":3,"stroke-linejoin":"round"}));
 n.forEach((v,i)=>{if(i%7===0||i===n.length-1)svg.append(svgEl("circle",{cx:x(i),cy:y(v),r:3,fill:"#1b708b"}),svgEl("text",{x:x(i),y:266,"text-anchor":"middle","font-size":11,fill:"#61758b"},state.data.dates[i]));});
}
function render(){
 if(!state.data)return;
 const pages={competition,algorithm:algorithmFiche,synthetic:syntheticCompetition,algorithms,theses,monitoring,archive,ported,full,method:methodology,glossary};
 document.querySelectorAll(".product-tabs [data-view]").forEach(b=>{const active=b.dataset.view===state.view||(state.view==="algorithm"&&b.dataset.view==="competition");b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
 $("app").innerHTML=(pages[state.view]||competition)();chart();
}
function resolveMidasView(){
 const requested=new URLSearchParams(location.search).get("view");
 // Preserve old bookmarks without retaining the deleted Inicio page.
 if(requested==="overview"){
  const u=new URL(location.href);u.searchParams.set("view","competition");
  history.replaceState({view:"competition"},"",u);
  return "competition";
 }
 return viewNames.includes(requested)?requested:"competition";
}
function go(view){
 if(!viewNames.includes(view))return;
 state.view=view;
 const u=new URL(location.href);
 u.searchParams.set("view",view);
 if(view==="algorithm"&&state.algorithmId)u.searchParams.set("algorithm",state.algorithmId);
 else u.searchParams.delete("algorithm");
 history.pushState({view,algorithm:state.algorithmId},"",u);
 render();window.scrollTo({top:0,behavior:"auto"});
}
const asCSV=rows=>rows.map(row=>row.map(x=>'"'+String(x??"").replaceAll('"','""')+'"').join(",")).join("\n");
function download(name,rows){const u=URL.createObjectURL(new Blob(["\ufeff"+asCSV(rows)],{type:"text/csv;charset=utf-8"}));const a=document.createElement("a");a.href=u;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(u);}
function exportData(what){
 if(what==="ranking"){download("midas-ranking-sintetico.csv",[["algoritmo","familia","retorno_pct","drawdown_pct","volatilidad_pct","sharpe","coste"],...competitionReadModel(state.data,{sort:state.sort,ascending:state.asc,group:state.group}).map(x=>[x.name,x.group,x.returnPct,x.drawdownPct,x.volatilityPct,x.sharpe,x.fees])]);}
 if(what==="nav"){download("midas-curva-paper-sintetica.csv",[["sesion","nav_base_100","capital_ficticio"],...active().points.map(p=>[p.session,p.nav,p.equity])]);}
 if(what==="next-open"){const a=causalLedger();download("midas-ordenes-next-open-sinteticas.csv",[["senal_al_cierre","fill_apertura_siguiente","activo","lado","apertura_sintetica","precio_paper","unidades","notional","comision","deslizamiento"],...a.orders.map(o=>[o.signalAt,o.fillAt,o.symbol,o.side,o.openPrice,o.fillPrice,o.units,o.notional,o.fee,o.slippage])]);}
 if(what==="journal"){download("midas-diario-sintetico.csv",[["sesion","activo","accion","precio","unidades","nocional","coste"],...active().orders.map(x=>[x.session,x.symbol,x.action,x.referencePrice,x.units,x.notional,x.cost])]);}
 if(what==="issuers"){
  download(state.localCagr.size?"midas-tesis-publicas-comparacion-local.csv":"midas-tesis-publicas-historicas.csv",
   publicThesisCsv(issuerReadRows(),state.publicTheses,state.localCagr));
 }
 if(what==="theses"){download("midas-tesis-sinteticas.csv",[["entidad","sector","metodo","estado","cagr_central","valor_bajista","valor_central","valor_alcista"],...thesisRank(state.data).map(x=>[x.company,x.sector,x.method,x.status,x.central,x.valuation.bear.fair,x.valuation.base.fair,x.valuation.bull.fair])]);}
}
function openCompetitionRow(id){
 if(!all().some(s=>s.id===id))return;
 state.strategy=id;
 state.detailOpen=true;
 if(state.view==="synthetic")render();
 else go("synthetic");
 window.scrollTo({top:0,behavior:"auto"});
}
function openIssuerRow(id){
 if(!state.universe.issuers.some(i=>i.ticker===id))return;
 state.issuerTicker=id;
 state.issuerMode="catalog";
 if(state.view==="theses")render();else go("theses");
 document.querySelector("#issuer-ficha")?.scrollIntoView({block:"start",behavior:"auto"});
}
$("app").addEventListener("click",e=>{
 const b=e.target.closest("button[data-action]");
 if(!b){
  const row=e.target.closest("tr[data-competition-id]");
  if(row){openCompetitionRow(row.dataset.competitionId);return;}
  const issuer=e.target.closest("tr[data-issuer-id]");
  if(issuer)openIssuerRow(issuer.dataset.issuerId);
  return;
 }
 const {action,value}=b.dataset;
 if(action==="navigate"){state.detailOpen=false;go(value);}
 else if(action==="full-detail"){
  if(!state.fullRoster?.entries.some(x=>x.slot===value)&&
     !state.strategyCandidates?.candidates.some(c=>c.id===value))return;
  state.algorithmId=value;state.auditTab="sessions";state.auditSort="recent";state.auditDesc=true;go("algorithm");
 }
 else if(action==="select")openCompetitionRow(value);
 else if(action==="journal"){state.strategy=value;state.detailOpen=false;go("monitoring");}
 else if(action==="group"){state.group=value;state.detailOpen=false;go("synthetic");}
 else if(action==="close-detail"){state.detailOpen=false;render();}
 else if(action==="rank-column"){
  if(state.sort===value)state.asc=!state.asc;
  else{state.sort=value;state.asc=["name","group"].includes(value);}
  state.detailOpen=false;render();
 }
 else if(action==="paper-select"){state.paperDetail=value;render();}
 else if(action==="full-focus"){
  if(!["IL-038","IL-039"].includes(value))return;
  state.fullRosterGroup="";state.fullRosterQuery=value;render();
 }
 else if(action==="full-sort-direction"){state.fullRosterAsc=!state.fullRosterAsc;render();}
 else if(action==="full-column"){
  if(!FULL_SORT_KEYS.includes(value))return;
  if(state.fullRosterSort===value)state.fullRosterAsc=!state.fullRosterAsc;
  else{
   state.fullRosterSort=value;
   state.fullRosterAsc=["name","group","activity","currency"].includes(value);
  }
  // Preserve horizontal table position when sorting on a small screen.
  const left=document.querySelector("#full-rows")?.closest(".table-scroll")?.scrollLeft||0;
  render();
  const scroller=document.querySelector("#full-rows")?.closest(".table-scroll");
  if(scroller)scroller.scrollLeft=left;
 }
 else if(action==="full-export"){
  if(state.fullRoster){
   download("midas-competicion-64-y-propuestas.csv",[
    ["ID","Nombre","Familia","Fase técnica","Estado económico","Actividad","Rentabilidad","Riesgo","Comparabilidad"],
    ...sortedFullRosterRows().map(({id,name,group,record,candidate})=>candidate?
     [candidate.id,candidate.name,candidate.group,"Investigación sin feed satelital","No iniciado",candidate.status,"N/D","N/D","no comparable"]:
     [id,name,group,technicalStage(id).label,record?.historical?"archivo_historico":record?"diario_paper":"sin_diario",record?.activity||"N/D",record?.return_pct??"N/D",record?.risk?.max_drawdown_pct??"N/D",record?.comparison?.eligible?"misma referencia":"no comparable"])
   ]);
  }
 }
 else if(action==="audit-tab"){
  state.auditTab=value==="operations"?"operations":"sessions";
  const current=document.querySelector("#audit-tab-strip");
  const region=document.querySelector(".audit-section");
  if(current&&region){
   for(const b of current.querySelectorAll("[data-action='audit-tab']"))
    b.setAttribute("aria-selected",String(b.dataset.value===state.auditTab));
   for(const panel of ["sessions","operations"]){
    const el=region.querySelector("#audit-panel-"+panel);
    if(el)el.hidden=panel!==state.auditTab;
   }
  }
 }
 else if(action==="audit-sort"){
  if(!["ticker","action","buyPrice","salePrice","returnPct","pnl","invested","shares"].includes(value))return;
  if(state.auditSort===value)state.auditDesc=!state.auditDesc;
  else{state.auditSort=value;state.auditDesc=true;}
  const top=document.querySelector("#audit-tab-strip")?.getBoundingClientRect().top;
  render();
  if(Number.isFinite(top)){
   const next=document.querySelector("#audit-tab-strip")?.getBoundingClientRect().top;
   if(Number.isFinite(next))window.scrollBy({top:next-top,behavior:"auto"});
  }
 }
 else if(action==="issuer-column"){
  if(state.issuerSort===value)state.issuerAsc=!state.issuerAsc;
  else{state.issuerSort=value;state.issuerAsc=["ticker","company","market"].includes(value);}
  render();
 }
 else if(action==="thesis"){state.thesis=value;state.issuerMode="demo";go("theses");}
 else if(action==="issuer-mode"){state.issuerMode=value==="demo"?"demo":"catalog";render();}
 else if(action==="issuer-select")openIssuerRow(value);
 else if(action==="issuer-local-clear"){state.localCagr=new Map();state.localCagrError="";render();}
 else if(action==="direction"){state.asc=!state.asc;render();}
 else if(action==="issuer-direction"){state.issuerAsc=!state.issuerAsc;render();}
 else if(action==="export")exportData(value);
});
$("app").addEventListener("keydown",e=>{
 if(e.key!=="Enter"&&e.key!==" ")return;
 if(e.target.closest("button,select,input,a,textarea"))return;
 const row=e.target.closest("tr[data-competition-id]");
 if(row){e.preventDefault();openCompetitionRow(row.dataset.competitionId);return;}
 const issuer=e.target.closest("tr[data-issuer-id]");
 if(issuer){e.preventDefault();openIssuerRow(issuer.dataset.issuerId);}
});
$("app").addEventListener("change",e=>{
 const el=e.target;
 if(el.id==="cagr-file"){
  const file=el.files?.[0];
  if(!file)return;
  void (async()=>{
   try{
    if(file.size>1000000)throw Error("CSV demasiado grande");
    const allowed=new Set(state.universe.issuers.map(x=>x.ticker));
    const map=parseLocalCagr2031(await file.text(),allowed);
    state.localCagr=map;state.localCagrError="";
   }catch(error){state.localCagr=new Map();state.localCagrError="Archivo rechazado: "+error.message;}
   render();
  })();
  return;
 }
 if(el.id==="group-select"){state.group=el.value;state.detailOpen=false;render();}
 if(el.id==="full-group-select"){state.fullRosterGroup=el.value;render();}
 if(el.id==="full-mobile-sort"){if(FULL_SORT_KEYS.includes(el.value)){state.fullRosterSort=el.value;state.fullRosterAsc=["name","group","activity","currency"].includes(el.value);render();}}
 if(el.id==="rank-select"){state.sort=el.value;state.asc=["name","group"].includes(el.value);state.detailOpen=false;render();}
 if(el.id==="thesis-sort"){state.thesisSort=el.value;render();}
 if(el.id==="issuer-sort"){state.issuerSort=el.value;state.issuerAsc=["ticker","company","market"].includes(el.value);render();}
 if(el.id==="journal-select"){state.strategy=el.value;render();}
 if(el.id==="audit-ticker"){state.auditTicker=el.value;render();}
});
$("app").addEventListener("input",e=>{
 if(e.target.id==="glossary-query"){
  const query=e.target.value;
  const results=$("glossary-results");if(results)results.innerHTML=glossaryRows(query);
  const counter=$("glossary-count");if(counter)counter.textContent=searchGlossary(query).length+" conceptos encontrados";
 }
 if(e.target.id==="full-query"){state.fullRosterQuery=e.target.value;const tbody=$("full-rows");if(tbody)tbody.innerHTML=fullRosterRows();const n=$("full-count");if(n&&state.fullRoster)n.textContent=sortedFullRosterRows().length;}
 if(e.target.id==="thesis-query"){state.query=e.target.value;const tbody=$("thesis-rows");if(tbody)tbody.innerHTML=thesisTableRows();}
 if(e.target.id==="issuer-query"){
  state.issuerQuery=e.target.value;
  const tbody=$("issuer-rows");if(tbody)tbody.innerHTML=issuerTableRows();
  const count=publicIssuerReadModel(state.universe,{query:state.issuerQuery,sort:state.issuerSort,ascending:state.issuerAsc}).length;
  const text=$("issuer-visible-count");if(text)text.textContent=count+" de "+researchIssuerCount()+" empresas";
  const empty=$("issuer-empty");if(empty)empty.hidden=count!==0;
 }
});
$("app").addEventListener("submit",e=>{
 if(e.target.id!=="paper-form")return;e.preventDefault();
 const form=new FormData(e.target),weights=Object.keys(state.data.market).map(k=>Number(form.get(k))/100);
 const cost=Number(form.get("cost")),name=String(form.get("name")||"").trim();
 if(!name||name.length>70||weights.some(w=>!finite(w)||w<0)||weights.reduce((a,b)=>a+b,0)>1.000001||!finite(cost)||cost<0||cost>100){
  const el=$("paper-feedback");if(el)el.textContent="Pesos inválidos: máximo 100 % y costes de 0 a 100 puntos básicos.";return;
 }
 const id="P-"+String(Math.max(...all().map(x=>Number(x.id.slice(2))))+1).padStart(2,"0");
 state.data.strategies.push({id,name,group:"Carteras locales",mode:"manual",manualWeights:weights,rule:"Pesos elegidos en este navegador. Sin persistencia.",cost_bps:cost,status:"Local · sintético",coverage:100,initialCapital:100000});
 state.strategy=id;state.group="";state.sort="returnPct";state.detailOpen=true;go("competition");
});
document.querySelectorAll(".product-tabs [data-view]").forEach(b=>b.addEventListener("click",()=>{state.detailOpen=false;go(b.dataset.view);}));
window.addEventListener("popstate",()=>{state.view=resolveMidasView();state.algorithmId=new URLSearchParams(location.search).get("algorithm");state.detailOpen=false;render();});
async function init(){
 try{
  const [r,p]=await Promise.all([fetch("./data/demo.json",{cache:"no-store"}),fetch("./data/public-theses.json",{cache:"no-store"})]);
  if(!r.ok||!p.ok)throw Error("Public datasets missing");
  const data=await r.json(),universe=data.issuerCatalog,publication=await p.json();
  verify(data);verifyIssuerCatalog(universe);
  const stats=verifyPublicTheses(publication);
  state.publicTheses=new Map(publication.records.map(x=>[x.ticker,x]));
  state.publicThesesMetadata={...stats,published_as_of:publication.published_as_of};
  state.data=data;state.universe=universe;state.view=resolveMidasView();state.algorithmId=new URLSearchParams(location.search).get("algorithm");render();void loadOfficialFx();void loadForecastLedger();void loadSecFilings();void loadOfficialYield();void loadOriginalPaper();void loadHistoricalPaper();void loadFullRoster();void loadStrategyCandidates();void loadInstitutionalPaperFeed();void loadOperationsAudit();
 }catch(e){$("app").textContent="No se ha podido cargar el catálogo de emisores o el laboratorio sintético; no se muestran datos no verificados.";}
}
async function loadOfficialFx(){
 try{
  const res=await fetch("./data/official-fx.json",{cache:"no-store"});
  if(!res.ok)throw Error("Official dataset absent");
  const doc=await res.json(),verified=verifyOfficialFx(doc);
  state.fx=doc;state.fxCheck=verified;state.fxStatus="ok";
 }catch(_error){state.fx=null;state.fxCheck=null;state.fxStatus="unavailable";}
 if(state.view==="monitoring"&&state.data)render();
}
async function loadForecastLedger(){
 try{
  const response=await fetch("./data/fx-forecast-ledger.json",{cache:"no-store"});
  if(!response.ok)throw Error("Prospective ledger absent");
  const doc=await response.json(),stats=summarizeFxForecastLedger(doc);
  state.forecastLedger=doc;state.forecastSummary=stats;state.forecastStatus="ok";
 }catch(_error){state.forecastLedger=null;state.forecastSummary=null;state.forecastStatus="unavailable";}
 if(state.view==="monitoring"&&state.data)render();
}
async function loadSecFilings(){
 try{
  const response=await fetch("./data/sec-filings.json",{cache:"no-store"});
  if(!response.ok)throw Error("No SEC metadata dataset");
  const doc=await response.json();
  const read=verifySecFilings(doc,state.universe);
  state.secRead=read;state.secCatalog=doc;state.secStatus=read.status==="verified_filings"?"ok":"not_collected";
 }catch(_error){state.secRead=null;state.secCatalog=null;state.secStatus="unavailable";}
 if(state.view==="theses"&&state.data)render();
}
async function loadOfficialYield(){
 try{
  const response=await fetch("./data/official-eur-yield.json",{cache:"no-store"});
  if(!response.ok)throw Error("No verified euro yield curve");
  const doc=await response.json(),check=verifyOfficialYield(doc);
  state.yieldDoc=doc;state.yieldCheck=check;state.yieldStatus="ok";
 }catch(_error){state.yieldDoc=null;state.yieldCheck=null;state.yieldStatus="unavailable";}
 if(state.view==="monitoring"&&state.data)render();
}
async function loadStrategyCandidates(){
 try{
  const response=await fetch("./data/strategy-candidates.json",{cache:"no-store"});
  if(!response.ok)throw Error("Missing strategy research register");
  const doc=await response.json();
  verifyStrategyCandidates(doc);
  state.strategyCandidates=doc;state.strategyCandidatesStatus="ok";
 }catch(_error){state.strategyCandidates=null;state.strategyCandidatesStatus="unavailable";}
 if(["full","competition","algorithm"].includes(state.view)&&state.data)render();
}
async function loadOriginalPaper(){
 try{
  const [r,m]=await Promise.all([fetch("https://raw.githubusercontent.com/idealab2026/laboratorio-cuantitativo/main/strategy_state/dashboard.json",{cache:"no-store",credentials:"omit"}),fetch("./data/original-track-map.json",{cache:"no-store"})]);
  if(!r.ok||!m.ok)throw Error("Diarios no disponibles");
  state.originalPaper=verifyOriginalPaper(await r.json(),await m.json());state.originalPaperStatus="ok";
 }catch(_error){state.originalPaper=null;state.originalPaperStatus="unavailable";}
 if(["full","competition","algorithm","monitoring"].includes(state.view)&&state.data)render();
}
async function loadHistoricalPaper(){
 try{
  const res=await Promise.all([fetch("./data/historical-paper-results.csv",{cache:"no-store"}),fetch("./data/historical-paper-curves.csv",{cache:"no-store"})]);
  if(res.some(r=>!r.ok))throw Error("Archivo histórico no disponible");
  const [results,nav]=await Promise.all(res.map(r=>r.text()));
  const rows=parseLocalPaperResults(results),curves=parseLocalPaperCurves(nav,rows);
  state.historicalPaper=rows;state.historicalCurves=curves;state.historicalPaperStatus="ok";
 }catch(_error){state.historicalPaper=null;state.historicalCurves=null;state.historicalPaperStatus="unavailable";}
 if(["full","competition","algorithm"].includes(state.view)&&state.data)render();
}
async function loadFullRoster(){
 try{
  const response=await fetch("./data/competition-roster.json",{cache:"no-store"});
  if(!response.ok)throw Error("Missing institution-only roster");
  const doc=await response.json();
  verifyFullRoster(doc);
  state.fullRoster=doc;state.fullRosterStatus="ok";
 }catch(_error){state.fullRoster=null;state.fullRosterStatus="unavailable";}
 if(["full","competition","algorithm"].includes(state.view)&&state.data)render();
}
async function loadInstitutionalPaperFeed(){
 try{
  const res=await fetch("./data/institutional-paper-feed.json",{cache:"no-store"});
  if(!res.ok)throw Error("Institutional publication absent");
  const doc=await res.json();
  if(!state.fullRoster){
   const rosterRes=await fetch("./data/competition-roster.json",{cache:"no-store"});
   if(!rosterRes.ok)throw Error("No verified institutional strategy roster");
   const roster=await rosterRes.json();
   verifyFullRoster(roster);state.fullRoster=roster;
  }
  const verified=verifyPaperFeed(doc,state.fullRoster);
  state.paperFeed=doc;state.paperFeedRead=verified;
  state.institutionalFeedStatus=verified.status;
 }catch(_error){state.paperFeed=null;state.paperFeedRead=null;state.institutionalFeedStatus="unavailable";}
 if(["full","competition","algorithm"].includes(state.view)&&state.data)render();
}
async function loadOperationsAudit(){
 try{
  const response=await fetch("./data/operations-audit.json",{cache:"no-store"});
  if(!response.ok)throw Error("Libro de operaciones no publicado");
  const document=await response.json();
  verifyOperationsAudit(document);
  state.operationsAudit=document;
  state.operationsAuditStatus="verified";
 }catch(_error){
  state.operationsAudit=null;
  state.operationsAuditStatus="unavailable";
 }
 if(state.view==="algorithm"&&state.data)render();
}

init();
