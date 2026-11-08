import {LIVE_REFRESH_MS, readLiveAttempts, renderLiveSession, sessionToday} from "./live-session.mjs?v=2057d4fd24d2";
import {renderThesisReport,verifyFullReports} from "./thesis-report.mjs?v=e1fa6cfb16cf";
import {verifyFinancialSankeys} from "./financial-sankey.mjs?v=a50f0cb89012";
import {verifyOriginalPaper} from "./original-paper.mjs?v=b4ab52ea9863";
import {algorithmTheory,paperLeaderboard} from "./algorithm-detail.mjs";
import {glossaryGroups,searchGlossary,verifyGlossary} from "./glossary.mjs";
import {verifyOperationsAudit,renderOperationsAudit,renderTradeLotsTable,summarizeOperationsAudit,buildSessionActionColumns,renderSessionTickerList} from "./operations-audit.mjs?v=5b772a793f3b";
import {parseLocalPaperResults,parseLocalPaperCurves,summarizePrivatePaper} from "./private-paper.mjs?v=4baff08a2202";
import {signalResearchSummary,methodCatalog} from "./paper-methods.mjs";
import {parseLocalCagr2031} from "./private-theses.mjs";
import {verifyPublicTheses,publicResearchRows,orderedThesisRows,publicThesisTableRows,publicThesisDetail,publicThesisCsv,verifyPublicCloseFeed} from "./public-theses.mjs?v=df965fd74e7a";
import {artificialCampaignComparison} from "./paper-ledger.mjs";
import {verifyFullRoster,filterRoster,technicalStage,technicalCoverage,verifyStrategyCandidates,filterStrategyCandidates,FULL_SORT_KEYS,sortFullCompetitionRows,COMPETITION_PHASES,strategyCompetitionPhase,partitionCompetitionRows} from "./competition-roster.mjs?v=0e6d86112171";
import {verifyPaperFeed} from "./paper-feed.mjs";
import {verify,simulate,rank,valuation,thesisRank,formatPct,money,finite,verifyIssuerCatalog,filterIssuers,syntheticBarsFromDemo,nextOpenPaper,evaluateIssuerScreen,competitionReadModel,publicIssuerReadModel,verifyOfficialFx,summarizeFxForecastLedger,verifySecFilings,verifyOfficialYield} from "./metrics.mjs";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>finite(n)?new Intl.NumberFormat("es-ES",{maximumFractionDigits:2}).format(n):"N/D";
const state={data:null,universe:null,fx:null,fxCheck:null,fxStatus:"pending",forecastLedger:null,forecastSummary:null,forecastStatus:"pending",secStatus:"pending",secRead:null,secCatalog:null,yieldDoc:null,yieldCheck:null,yieldStatus:"pending",view:"home",strategy:"P-01",group:"",sort:"returnPct",asc:false,detailOpen:false,thesis:"T-01",query:"",thesisSort:"central",issuerMode:"catalog",issuerQuery:"",issuerSort:"base",issuerAsc:false,issuerTicker:"MSFT",paperDetail:"M-10",originalPaper:null,originalPaperStatus:"pending",historicalPaper:null,historicalCurves:null,historicalPaperStatus:"pending",fullRoster:null,fullRosterStatus:"pending",strategyCandidates:null,strategyCandidatesStatus:"pending",fullRosterGroup:"",fullRosterQuery:"",fullRosterSort:"return",fullRosterAsc:false,competitionPhase:"active",algorithmId:null,operationsAudit:null,operationsAuditStatus:"pending",auditTicker:null,auditTab:"sessions",auditSort:"recent",auditDesc:true,monitoringTab:"today",monitoringStrategy:"IL-039",monitoringSort:"recent",monitoringDesc:true,executionHistory:null,executionHistoryStatus:"pending",institutionalFeedStatus:"pending",paperFeed:null,paperFeedRead:null,localCagr:new Map(),localCagrError:"",publicTheses:new Map(),publicThesesMetadata:null,fullReports:new Map(),financialSankeys:new Map(),financialPeriodByTicker:new Map(),publicCloses:new Map(),closeFeedStatus:"not_configured",closeFeedSource:null,closeFeedUpdatedAt:null};
const viewNames=["home","competition","trading","algorithm","algorithms","theses","thesis","monitoring","method","glossary","ported","full","synthetic"];
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
 return orderedThesisRows(rows,state.publicTheses,state.localCagr,state.issuerSort,state.issuerAsc,state.publicCloses);
}
function researchIssuerCount(){return new Set([...state.universe.issuers.map(x=>x.ticker),...state.publicTheses.keys()]).size;}
function issuerTableRows(){
 return publicThesisTableRows(issuerReadRows(),state.publicTheses,state.localCagr,null,state.publicCloses);
}

function issuerDetail(ticker){
 const publicRecord=state.publicTheses.get(ticker);
 if(publicRecord)return publicThesisDetail(publicRecord,state.localCagr.get(ticker));
 const i=state.universe.issuers.find(x=>x.ticker===ticker)||state.universe.issuers[0];
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
 const columns=[["company","Empresa · cotización"],["market","Mercado"],
 ["bull","Bull 5a"],["bear","Bear 5a"],["base","Central 5a"],["entry","Precio 15 %"],
 ["target","Objetivo 5a"],["earnings","Resultados (registro)"],["report","Ficha pública"]];
 const headers=columns.map(([key,label])=>'<th scope="col" aria-sort="'+(state.issuerSort===key?(state.issuerAsc?"ascending":"descending"):"none")+'"><button class="table-sort" type="button" data-action="issuer-column" data-value="'+key+'" aria-label="Ordenar por '+esc(label)+'">'+esc(label)+' <span aria-hidden="true">'+(state.issuerSort===key?(state.issuerAsc?"↑":"↓"):"↕")+'</span></button></th>').join("");
 const found=issuerReadRows().length;
 const screens=state.universe.publicScreens?.length||0;
 return head("TESIS · SEGUIMIENTO PÚBLICO","Investigación de empresas","Tesis, hipótesis y escenarios históricos de Idea Lab. Cada ficha conserva las fechas y cifras de su estudio; no son cotizaciones actuales ni rentabilidades obtenidas.")+
 '<div class="source-health-strip"><div><span class="label">Empresas analizadas</span><strong>'+state.publicTheses.size+' tesis</strong><small>Expedientes históricos publicados</small></div>'+
 '<div><span class="label">Modelos exploratorios</span><strong>'+screens+' modelos</strong><small>Escenarios independientes; no tesis aprobadas</small></div>'+
 '<div><span class="label">Corte documental</span><strong>'+esc(state.publicThesesMetadata?.published_as_of||"N/D")+'</strong><small>Los datos no se recalculan en tiempo real</small></div></div>'+
 '<p class="thesis-quotes-status" id="thesis-quotes-status" role="status">'+(state.closeFeedStatus==="verified"?
   'Cierres públicos verificados: '+state.publicCloses.size+' empresas · fuente: '+esc(state.closeFeedSource?.name||"no indicada")+' · última ingestión '+esc(state.closeFeedUpdatedAt||"N/D")+'. Actualización del feed público cada 24 horas, si está habilitado.':
   'Cotizaciones mostradas por TradingView (según disponibilidad y retraso por mercado). Los cierres autorizados, cuando existan, prevalecen; los precios históricos de las tesis siguen separados.')+'</p>'+
 '<div class="table-scroll table-compact thesis-public-table"><table><thead><tr>'+headers+'</tr></thead><tbody id="issuer-rows">'+issuerTableRows()+'</tbody></table></div>'+
 '<p id="issuer-empty" class="table-note" '+(found?'hidden':'')+'>No hay empresas coincidentes.</p>';
}

function thesisView(){
 const ticker=(new URLSearchParams(location.search).get("ticker")||"").toUpperCase();
 if(!/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/.test(ticker)||!state.publicTheses.has(ticker))
  return head("TESIS · CONSULTA","Informe no disponible","No existe una tesis pública validada para el símbolo solicitado.")+'<p><a href="./index.html?view=theses">← Volver al seguimiento</a></p>';
 return renderThesisReport(state.publicTheses.get(ticker),state.fullReports.get(ticker)||null,state.financialSankeys.get(ticker)||null,state.financialPeriodByTicker.get(ticker)||null);
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

/**
 * GitHub Actions session health, NOT the individual paper trading ledger.
 * A workflow shared by 9 slots can report 9 affected algorithms, while the
 * source badge discloses that all share one execution event.
 */
const monitoringTabs=[["today","Sesión de hoy"],["summary","Indicadores"],["operations","Operaciones"],["daily","Histórico de sesiones"]];
const liveJobCache=new Map();
let liveSessionData=null, liveSessionRequest=null, liveLastRequest=0;
const liveSessionActive=()=>state.view==="monitoring"&&state.monitoringTab==="today";
const dailyHistoryActive=()=>state.view==="monitoring"&&state.monitoringTab==="daily";
const currentSession=()=>sessionToday(state.executionHistory?.live_plan);
const SIGNAL_REFRESH_MS=60_000;
const signalNames={buy:"Comprar",sell:"Vender",hold:"Mantener",rebalance:"Rebalancear"};
let signalFeed=null,signalFeedError=false,signalRequest=null,signalChecked=0,signalSlot="IL-038",signalPlanDate=null;

const signalDate=d=>typeof d==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(d);
function verifyLiveSignals(doc){
 const validDate=d=>d===null||signalDate(d);
 const validPrice=p=>p===null||typeof p==="number"&&Number.isFinite(p)&&p>0;
 if(doc?.schema!=="midas_execution_signals_v1"||!Number.isFinite(Date.parse(doc.published_at_utc))||
    !doc.tracks||Object.keys(doc.tracks).length!==35)throw Error("Registro de señales incompleto");
 for(const [id,track] of Object.entries(doc.tracks)){
  if(strategyCompetitionPhase(id)!=="active"||typeof track.label!=="string"||track.label.length>160||
     !["recorded","paused","unavailable"].includes(track.status)||![null,"USD","EUR"].includes(track.currency)||
     !validDate(track.session)||!validDate(track.decision_session)||
     !Array.isArray(track.signals)||!Array.isArray(track.executions))throw Error("Cartera de señales no verificable");
  for(const signal of track.signals){
   if(!/^[A-Z0-9.-]{1,14}$/.test(signal.ticker)||!Object.hasOwn(signalNames,signal.action)||
      !validDate(signal.decision_session)||!validDate(signal.target_session)||!validPrice(signal.limit_price)||
      !(signal.target_weight===null||Number.isFinite(signal.target_weight)&&signal.target_weight>=0&&signal.target_weight<=1))
    throw Error("Señal no verificable");
  }
  if((track.pause_date!==undefined&&!validDate(track.pause_date))||
     (track.pause_reason!==undefined&&![null,"missing_ohlc","unreconciled_session","expired_open"].includes(track.pause_reason)))
   throw Error("Pausa de la cartera no verificable");
  const coverage=track.analysis_coverage;
  if(coverage!=null&&(!signalDate(coverage.date)||!["eligible","features","evaluated","scored"].includes(coverage.stage)||
     !Number.isInteger(coverage.eligible)||!Number.isInteger(coverage.total)||coverage.eligible<0||
     coverage.eligible>coverage.total||coverage.total>1000))
   throw Error("Cobertura de análisis no verificable");
  const trace=track.analysis;
  if(trace!=null&&(!signalDate(trace.date)||!["classic","ahp","monthly"].includes(trace.method)||
    !(trace.excluded===null||Number.isSafeInteger(trace.excluded)&&trace.excluded>=0)||
    !Array.isArray(trace.rows)||trace.rows.length>600||trace.rows.some(row=>!Array.isArray(row)||row.length!==3||
      !validSignalTicker(row[0])||!Object.hasOwn(terminalLabels,row[1])||!Array.isArray(row[2])||
      row[2].some(check=>!Object.hasOwn(terminalRules,check)))))
   throw Error("Registro de análisis no verificable");
  if(trace?.ratios!==undefined&&(!trace.ratios||typeof trace.ratios!=="object"||
     Array.isArray(trace.ratios)||Object.entries(trace.ratios).some(([ticker,values])=>
      !validSignalTicker(ticker)||!values||typeof values!=="object"||Array.isArray(values)||
      Object.entries(values).some(([key,value])=>!Object.hasOwn(terminalRules,key)||
       !Number.isFinite(value)||value<0||value>1))))
   throw Error("Indicadores del análisis no verificables");
  for(const fill of track.executions){
   if(!/^[A-Z0-9.-]{1,14}$/.test(fill.ticker)||!["buy","sell"].includes(fill.action)||
      !validPrice(fill.price)||!validDate(fill.decision_session))throw Error("Operación no verificable");
  }
 }
 for(const [day,plan] of Object.entries(doc.opening_plans||{})){
  if(!signalDate(day)||!signalDate(plan.previous_session)||plan.previous_session>=day||
     !Number.isFinite(Date.parse(plan.opens_at))||!/^([a-f0-9]{40})$/.test(plan.source_commit))
   throw Error("Fecha del plan no verificable");
  for(const [id,track] of Object.entries(plan.tracks)){
   if(!doc.tracks[id]||!["recorded","paused","stale","archived","unavailable"].includes(track.status)||
      !validDate(track.session)||!Array.isArray(track.orders)||!Array.isArray(track.holdings)||
      !Number.isSafeInteger(track.undated)||track.undated<0||
      track.holdings.some(t=>!validSignalTicker(t))||track.orders.some(o=>!validSignalTicker(o.ticker)||
       !["buy","sell","rebalance"].includes(o.action)||!signalDate(o.decision_session)||
       o.decision_session>=day||o.target_session!==day||!validPrice(o.limit_price)||
       !(o.target_weight===null||Number.isFinite(o.target_weight)&&o.target_weight>=0&&o.target_weight<=1)))
    throw Error("Plan de apertura no verificable");
  }
 }
 return doc;
}
const validSignalTicker=t=>typeof t==="string"&&/^[A-Z0-9.-]{1,14}$/.test(t);
function renderSignalRows(rows,currency,executed){
 const money=value=>value===null||!currency?"N/D":
  new Intl.NumberFormat("es-ES",{style:"currency",currency,currencyDisplay:"code"}).format(value);
 const percent=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:2});
 return '<table class="midas-signal-table"><thead><tr><th scope="col">Activo</th><th scope="col">Decisión</th><th scope="col">'+
  (executed?'Precio simulado':'Precio o peso objetivo')+'</th></tr></thead><tbody>'+
  rows.map(row=>{
   const label=executed?(row.action==="buy"?"Compra registrada":"Venta registrada"):signalNames[row.action];
   const timing=executed?(row.decision_session?"Señal del "+shortPaperDate(row.decision_session):"Operación del diario paper"):
    row.action==="hold"?"Posición abierta sin orden pendiente":
    (row.decision_session?"Señal del "+shortPaperDate(row.decision_session)+" · ":"")+
    (row.target_session?"Apertura prevista del "+shortPaperDate(row.target_session):"Orden pendiente en el diario");
   const value=executed?money(row.price):row.limit_price!==null?money(row.limit_price):
    row.target_weight!==null?percent.format(row.target_weight):
    row.action==="hold"?"—":"Por determinar";
   return '<tr><th scope="row">'+esc(row.ticker)+'</th><td><strong class="audit-'+esc(row.action)+'">'+esc(label)+'</strong><small>'+
    esc(timing)+'</small></td><td>'+esc(value)+'</td></tr>';
  }).join("")+'</tbody></table>';
}
function openingPlanDay(){
 const days=Object.keys(signalFeed?.opening_plans||{}).sort();
 if(days.includes(signalPlanDate))return signalPlanDate;
 const nyDate=new Intl.DateTimeFormat("sv-SE",{timeZone:"America/New_York",dateStyle:"short"}).format(new Date());
 return days.filter(day=>day<=nyDate).at(-1)||days[0];
}
function openingPlanOptions(){
 const selected=openingPlanDay();
 return Object.keys(signalFeed?.opening_plans||{}).sort().reverse().map(day=>
  '<option value="'+esc(day)+'"'+(day===selected?' selected':'')+'>'+esc(shortPaperDate(day))+'</option>').join("");
}
function openingPlanContent(track){
 const day=openingPlanDay(), plan=signalFeed.opening_plans[day];
 const entry=plan.tracks[signalSlot];
 const marketTime=new Intl.DateTimeFormat("es-ES",{timeStyle:"short",timeZone:"Europe/Madrid"})
  .format(new Date(plan.opens_at));
 const before=Date.parse(signalFeed.published_at_utc)<Date.parse(plan.opens_at);
 const notes={
  archived:"El libro está archivado. No hay un plan operativo para esta sesión.",
  unavailable:"No hay un diario verificable para esta estrategia y sesión.",
  stale:"El diario no incorpora la sesión anterior. El plan puede estar incompleto.",
  paused:"El diario estaba pausado. El plan puede estar incompleto."
 };
 const note=entry?notes[entry.status]:notes.unavailable;
 return '<h4>Plan para la apertura del '+esc(shortPaperDate(day))+'</h4>'+
  '<p class="midas-signal-meta">Apertura a las '+esc(marketTime)+' (Madrid) · '+
  (before?'Último plan publicado antes de abrir. Puede actualizarse.':'Reconstruido del diario guardado antes de abrir.')+
  (entry?.session?' Diario hasta el '+esc(shortPaperDate(entry.session))+'.':"")+'</p>'+
  (note?'<p class="monitoring-explanation">'+esc(note)+'</p>':"")+
  (entry?.orders.length?renderSignalRows(entry.orders,track.currency,false):
   !note&&!entry?.undated?'<p class="monitoring-explanation">Sin órdenes previstas para esta apertura.</p>':"")+
  (signalSlot==="IL-042"&&entry?.orders.length?'<p class="monitoring-explanation">TimesFM diario prevé cerrar al final de la sesión las posiciones que consiga abrir.</p>':"")+
  (entry?.undated?'<p class="monitoring-explanation">Hay órdenes pendientes sin una fecha de ejecución verificable para esta apertura.</p>':"")+
  (entry?.holdings.length&&!["archived","unavailable"].includes(entry.status)?
   '<details class="midas-signal-holdings"><summary>Posiciones del diario sin orden pendiente · '+entry.holdings.length+'</summary>'+
   renderSignalRows(entry.holdings.map(ticker=>({ticker,action:"hold",limit_price:null,target_weight:null})),
    track.currency,false)+'</details>':"");
}
function liveSignalsContent(){
 const track=signalFeed?.tracks[signalSlot];
 if(!track)return '<p class="monitoring-explanation" role="status">'+
  (signalFeedError?"El registro de señales no está disponible. Usa «Actualizar» para volver a consultarlo.":"Consultando el diario de señales…")+'</p>';
 const published=new Intl.DateTimeFormat("es-ES",{dateStyle:"short",timeStyle:"short",timeZone:"Europe/Madrid"})
  .format(new Date(signalFeed.published_at_utc));
 const pending=track.signals.filter(row=>row.action!=="hold");
 const holdings=track.signals.filter(row=>row.action==="hold");
 const plan=openingPlanDay();
 return '<p class="midas-signal-meta" role="status">Publicado '+esc(published)+' (Madrid)'+
  (signalFeedError?' · Se muestra la última copia disponible':"")+'</p>'+
  (plan?openingPlanContent(track):'<h4>Órdenes pendientes del último diario</h4>'+
   (pending.length?renderSignalRows(pending,track.currency,false):'<p class="monitoring-explanation">El diario no muestra órdenes pendientes.</p>')+
   (holdings.length?'<details class="midas-signal-holdings"><summary>Posiciones del diario sin orden pendiente · '+holdings.length+'</summary>'+
    renderSignalRows(holdings,track.currency,false)+'</details>':""))+
  '<h4>Operaciones registradas'+(track.session?' el '+esc(shortPaperDate(track.session)):"")+'</h4>'+
  (track.executions.length?renderSignalRows(track.executions,track.currency,true):
   '<p class="monitoring-explanation">No hay compras ni ventas individuales documentadas para esa sesión.</p>');
}
function liveSignalOptions(){
 return Object.entries(signalFeed?.tracks||{}).map(([id,track])=>
  '<option value="'+esc(id)+'"'+(signalSlot===id?' selected':'')+'>'+esc(id+' · '+track.label)+'</option>').join("");
}
function liveSignalsPanel(){
 const options=liveSignalOptions();
 return '<section class="midas-live-signals" aria-labelledby="midas-signal-title">'+
  '<div class="daily-ledger-header"><h3 id="midas-signal-title">Señales de los algoritmos</h3>'+
  '<button type="button" class="outline-btn" data-action="live-signals-refresh">Actualizar señales</button></div>'+
  '<p class="monitoring-explanation">Consulta qué tenía previsto cada estrategia para una apertura y qué operaciones simuladas se registraron después. El diario se consulta cada minuto con esta vista abierta. La vista cubre 35 carteras con diario; las demás estrategias del catálogo no tienen plan disponible aquí.</p>'+
  '<div id="midas-opening-date-control" class="monitoring-operation-controls"'+(openingPlanDay()?"":' hidden')+'>'+
  '<label for="midas-opening-date">Sesión prevista</label><select id="midas-opening-date">'+openingPlanOptions()+'</select></div>'+
  '<div class="monitoring-operation-controls"><label for="live-signal-algorithm">Algoritmo</label>'+
  '<select id="live-signal-algorithm"'+(options?"":' disabled')+'>'+
  (options||'<option>Consultando algoritmos…</option>')+'</select></div>'+
  '<div id="midas-signal-content">'+liveSignalsContent()+'</div></section>';
}
async function refreshLiveSignals(force=false){
 const room=tradingRoomActive();
 const interval=room?TRADING_REFRESH_MS:SIGNAL_REFRESH_MS;
 if((!liveSessionActive()&&!room)||document.hidden||signalRequest||(!force&&Date.now()-signalChecked<interval))return;
 signalChecked=Date.now();
 const previous=signalFeed,failed=signalFeedError;
 signalRequest=fetch("./data/execution-signals.json",{cache:"no-store"});
 try{
  const response=await signalRequest;
  if(!response.ok)throw Error("Registro no publicado");
  const next=verifyLiveSignals(await response.json());
  if(!previous||Date.parse(next.published_at_utc)>Date.parse(previous.published_at_utc))signalFeed=next;
  signalFeedError=false;
 }catch{
  signalFeedError=true;
 }finally{
  signalRequest=null;
  if(previous!==signalFeed||failed!==signalFeedError||$("trading-date")?.value!==tradingDay())paintTradingRoom();
  const picker=$("live-signal-algorithm"),content=$("midas-signal-content");
  if(picker&&signalFeed&&(!previous||picker.disabled)){
   picker.innerHTML=liveSignalOptions();
   picker.disabled=false;
  }
  if(content&&(previous?.published_at_utc!==signalFeed?.published_at_utc||failed!==signalFeedError)){
   const dateControl=$("midas-opening-date-control"),datePicker=$("midas-opening-date");
   if(dateControl&&datePicker){
    dateControl.hidden=!openingPlanDay();
    datePicker.innerHTML=openingPlanOptions();
   }
   const open=content.querySelector(".midas-signal-holdings")?.open;
   content.innerHTML=liveSignalsContent();
   const details=content.querySelector(".midas-signal-holdings");
   if(details&&open)details.open=true;
  }
 }
}

const TRADING_REFRESH_MS=30_000;
const tradingRoomActive=()=>state.view==="trading";
const tradingSides={all:"Todas",buy:"Compras",sell:"Ventas",rebalance:"Rebalanceos"};
const tradingFilter={date:null,slot:"",ticker:"",side:"all"};
const madridTime=new Intl.DateTimeFormat("es-ES",{timeStyle:"short",timeZone:"Europe/Madrid"});
const madridDateTime=new Intl.DateTimeFormat("es-ES",{dateStyle:"short",timeStyle:"short",timeZone:"Europe/Madrid"});

function tradingDay(){
 const days=Object.keys(signalFeed?.opening_plans||{}).sort();
 if(days.includes(tradingFilter.date))return tradingFilter.date;
 const today=new Intl.DateTimeFormat("sv-SE",{timeZone:"America/New_York",dateStyle:"short"}).format(new Date());
 return days.filter(day=>day<=today).at(-1)||days[0];
}
function tradingOptions(values,selected){
 return values.map(([value,label])=>'<option value="'+esc(value)+'"'+
  (value===selected?' selected':'')+'>'+esc(label)+'</option>').join("");
}
function tradingDates(){
 return tradingOptions(Object.keys(signalFeed?.opening_plans||{}).sort().reverse().map(day=>[day,shortPaperDate(day)]),tradingDay());
}
function tradingAlgorithms(){
 return tradingOptions([["","Todos los algoritmos"],...Object.entries(signalFeed?.tracks||{}).map(([slot,track])=>
  [slot,slot+" · "+track.label])],tradingFilter.slot);
}
function tradingReadModel(feed,day,{slot="",ticker="",side="all",slots=null}={}){
 const plan=feed?.opening_plans?.[day];
 const ids=slot?[slot]:Object.keys(feed?.tracks||{}).filter(id=>!slots?.size||slots.has(id));
 const text=ticker.trim().toUpperCase();
 const base=ids.flatMap(id=>(plan?.tracks[id]?.orders||[]).filter(order=>order.ticker.includes(text)).map(order=>({
  ...order,id,label:feed.tracks[id].label,currency:feed.tracks[id].currency
 })));
 const counts={all:base.length,buy:0,sell:0,rebalance:0};
 for(const order of base)counts[order.action]++;
 const orders=base.filter(order=>side==="all"||order.action===side)
  .sort((a,b)=>a.action.localeCompare(b.action)||a.ticker.localeCompare(b.ticker)||a.id.localeCompare(b.id));
 const journals=day?ids.filter(id=>feed?.tracks[id]?.session===day):[];
 const fills=journals.flatMap(id=>feed.tracks[id].executions.filter(fill=>fill.ticker.includes(text)).map(fill=>({
  ...fill,id,label:feed.tracks[id].label,currency:feed.tracks[id].currency
 })));
 return {plan,orders,counts,fills,journals:journals.length};
}
function tradingStatus(){
 if(!signalFeed)return signalFeedError?"Diario no disponible":"Conectando con el diario";
 const published=madridDateTime.format(new Date(signalFeed.published_at_utc));
 return (signalFeedError?"Copia guardada del ":"Última publicación · ")+published+" (Madrid)";
}
function tradingOrderPrice(order){
 if(order.limit_price!==null&&order.currency)
  return ["Precio límite",fmt(order.limit_price)+" "+order.currency];
 if(order.target_weight!==null)
  return ["Peso objetivo",new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:2}).format(order.target_weight)];
 return ["Precio","Por determinar"];
}
function tradingCoverage(plan,slot="",slots=null){
 const entry=plan.tracks[slot];
 if(slot){
  if(!entry||entry.status==="unavailable")return "Esta cartera no tiene un diario verificable para la sesión.";
  if(entry.status==="archived")return "Este diario está archivado.";
  const notes=[];
  if(entry.status==="stale")notes.push("Diario atrasado hasta el "+shortPaperDate(entry.session)+".");
  if(entry.status==="paused")notes.push("El diario estaba pausado antes de abrir.");
  if(entry.undated)notes.push("Hay órdenes pendientes sin fecha de ejecución verificable.");
  return notes.join(" ");
 }
 const entries=Object.entries(plan.tracks).filter(([id,track])=>(!slots?.size||slots.has(id))&&track.status!=="archived").map(([,track])=>track);
 const incomplete=entries.filter(track=>track.status!=="recorded"||track.undated).length;
 return incomplete?incomplete+" de "+entries.length+" carteras con diario vigente tienen información incompleta para esta sesión.":"";
}
const tradingDesk={slots:new Set(),symbols:null,phase:"opening"};
const deskPhases={opening:"Apertura prevista",next:"Siguiente apertura",fills:"Ejecuciones simuladas"};

function deskActivity(feed,day,filter,phase,slots){
 const nextDay=Object.keys(feed?.opening_plans||{}).sort().find(key=>feed.opening_plans[key].previous_session===day);
 const target=phase==="next"?nextDay:day;
 const model=tradingReadModel(feed,target,{...filter,slot:"",slots});
 if(phase==="fills"){
  const fills=tradingReadModel(feed,day,{...filter,slot:"",slots}).fills;
  model.orders=fills.filter(order=>filter.side==="all"||filter.side===order.action);
  model.counts={all:fills.length,buy:0,sell:0,rebalance:0};
  for(const fill of fills)model.counts[fill.action]++;
  model.plan=feed?.opening_plans?.[day];
 }else if(phase==="next"){
  const relevant=tradingReadModel(feed,target,{...filter,slot:"",slots,side:"all"}).orders.filter(order=>order.decision_session===day);
  model.orders=relevant.filter(order=>filter.side==="all"||filter.side===order.action);
  model.counts={all:relevant.length,buy:0,sell:0,rebalance:0};
  for(const order of relevant)model.counts[order.action]++;
 }
 return {...model,target};
}
function deskAlgorithmFilters(){
 const entries=Object.entries(signalFeed?.tracks||{});
 return '<details class="desk-algorithms" id="desk-algorithms"><summary>'+
  esc(tradingDesk.slots.size?tradingDesk.slots.size+" seleccionados":"Todos los algoritmos")+'</summary>'+
  '<div class="desk-filter-popover"><button type="button" class="outline-btn" data-action="desk-reset">Ver todos</button>'+
  entries.map(([slot,track])=>'<label><input type="checkbox" data-desk-algorithm="'+esc(slot)+'"'+
   (tradingDesk.slots.has(slot)?' checked':"")+'><span>'+esc(slot+" · "+track.label)+'</span></label>').join("")+'</div></details>';
}
let deskPriceSource=null,deskPrices=new Map();
function deskChartSeries(symbol,day){
 const audit=state.operationsAudit;
 if(audit!==deskPriceSource){
  deskPriceSource=audit;
  deskPrices=new Map();
  for(const track of Object.values(audit?.tracks||{})){
   for(const [ticker,series] of Object.entries(track.prices||{})){
    if(!deskPrices.has(ticker))deskPrices.set(ticker,new Map());
    const byDay=deskPrices.get(ticker);
    for(const row of series){
     if(!Number.isFinite(row.price)||row.price<=0)continue;
     if(!byDay.has(row.date))byDay.set(row.date,row.price);
     else if(byDay.get(row.date)!==row.price)byDay.set(row.date,null);
    }
   }
  }
 }
 return [...(deskPrices.get(symbol)||[])].filter(([date,price])=>date<=day&&price!==null)
  .sort(([a],[b])=>a.localeCompare(b)).slice(-18);
}
function deskChart(symbol,day){
 const series=deskChartSeries(symbol,day);
 const last=series.at(-1),first=series[0];
 const values=series.map(([,price])=>price);
 return '<article class="desk-chart"><div class="desk-chart-head"><strong>'+esc(symbol)+'</strong>'+
  (last?'<span>'+esc(fmt(last[1]))+' USD</span>':"")+
  '<button type="button" data-action="desk-chart-remove" data-value="'+esc(symbol)+
  '" aria-label="Quitar gráfico de '+esc(symbol)+'">×</button></div>'+
  (series.length>=2?sparkline(values,"Cierres auditados de "+symbol):
   '<p>'+(state.operationsAuditStatus==="pending"?"Cargando cierres…":"Histórico auditado insuficiente")+'</p>')+
  (last?'<small>'+esc(shortPaperDate(first[0]))+(series.length>1?' – '+esc(shortPaperDate(last[0])):"")+
   ' · '+series.length+' cierres auditados</small>':"")+'</article>';
}
function deskSignalTable(orders,phase,symbols,plan){
 const grouped=new Map();
 for(const order of orders){
  if(!grouped.has(order.ticker))grouped.set(order.ticker,[]);
  grouped.get(order.ticker).push(order);
 }
 return '<div class="desk-table-scroll" tabindex="0" aria-label="Señales agrupadas por empresa"><table class="desk-table">'+
  '<thead><tr><th scope="col">Empresa</th><th scope="col">Señales por algoritmo</th></tr></thead><tbody>'+
  [...grouped].sort(([a],[b])=>a.localeCompare(b)).map(([ticker,items])=>
   '<tr><th scope="row"><button type="button" data-action="desk-chart" data-value="'+esc(ticker)+
   '" aria-pressed="'+symbols.includes(ticker)+'" title="Mostrar gráfico de '+esc(ticker)+'">'+esc(ticker)+'</button></th><td>'+
   items.map(item=>{
    const action=signalNames[item.action];
    const [caption,value]=phase==="fills"?
     ["Precio simulado",item.price!=null&&item.currency?fmt(item.price)+" "+item.currency:"Sin precio publicado"]:
     tradingOrderPrice(item);
    return '<span class="desk-signal" title="'+esc(caption+" · "+value)+'"><b data-side="'+esc(item.action)+'">'+esc(action)+'</b>'+
     '<span>'+esc(item.label)+'</span><small>'+esc(item.id+
     (plan?.tracks[item.id]?.status==="archived"?" · Archivo":"")+
     (value==="Por determinar"?"":" · "+value))+'</small></span>';
   }).join("")+'</td></tr>').join("")+'</tbody></table></div>';
}
function deskResults(model){
 if(!signalFeed)return '<p class="trading-empty">'+(signalFeedError?"Usa «Actualizar» para consultar el diario.":"Cargando las señales publicadas…")+'</p>';
 const phase=tradingDesk.phase,day=tradingDay();
 const symbols=deskChartSymbols(model.orders);
 const dateLabel=model.target?shortPaperDate(model.target):"Pendiente";
 const open=phase!=="fills"&&model.plan?.opens_at?
  " · "+madridTime.format(new Date(model.plan.opens_at))+" Madrid":"";
 const coverage=model.plan?tradingCoverage(model.plan,"",tradingDesk.slots):"";
 return '<div class="desk-layout"><section class="desk-tape" aria-labelledby="desk-tape-title">'+
  '<div class="desk-heading"><h3 id="desk-tape-title">'+esc(deskPhases[phase])+' <small>'+esc(dateLabel+open)+'</small></h3>'+
  '<span>'+model.orders.length+' registros</span></div>'+
  (coverage&&phase!=="fills"?'<p class="desk-coverage">'+esc(coverage)+'</p>':"")+
  (phase!=="fills"&&model.orders.some(order=>order.id==="IL-042")?
   '<p class="desk-note">TimesFM diario prevé cerrar al final de la sesión las posiciones que llegue a abrir.</p>':"")+
  (model.orders.length?deskSignalTable(model.orders,phase,symbols,model.plan):'<p class="trading-empty">'+
   (phase==="fills"&&!model.journals?"Sin diario de ejecuciones para esta selección.":"Sin registros publicados para esta selección.")+'</p>')+
  '</section><aside class="desk-charts" aria-labelledby="desk-chart-title"><div class="desk-heading">'+
  '<h3 id="desk-chart-title">Gráficos de cierre</h3><span>Hasta 3 empresas</span></div>'+
  (symbols.length?symbols.map(symbol=>deskChart(symbol,day)).join(""):'<p class="trading-empty">Pulsa un ticker para mostrar su gráfico.</p>')+
  '</aside></div>';
}
function deskChartSymbols(orders){
 return tradingDesk.symbols??[...new Set(orders.map(order=>order.ticker))].slice(0,3);
}

const terminalState={mode:"signals",useLatest:false,count:0,stage:0,timer:null,activity:new Map(),pending:new Set()};
const terminalLabels={
 buy:"Regla de compra activada",sell:"Regla de venta activada",no_trigger:"Sin activación de regla",
 selected:"Seleccionada",passed:"Superó el filtro técnico",filtered:"Descartada en el filtro técnico",
 recorded_buy:"Compra simulada",recorded_sell:"Venta simulada",
 next_buy:"Compra prevista",next_sell:"Venta prevista",next_rebalance:"Rebalanceo previsto"
};
const terminalRunLabels={running:"En curso",queued:"En cola",success:"Completado",failure:"Con incidencias",unknown:"Sin confirmar"};
const terminalRules={rsi:"RSI",macd:"MACD",bollinger:"Bollinger",stochastic:"Estocástico"};

function terminalSessionEvidence(feed,day,slot){
 const track=feed?.tracks[slot];
 const plans=feed?.opening_plans||{};
 const nextDay=Object.keys(plans).sort().find(candidate=>plans[candidate].previous_session===day);
 const next=(plans[nextDay]?.tracks[slot]?.orders||[]).filter(order=>order.decision_session===day);
 return {track,plan:plans[day]?.tracks[slot],nextDay,next,
  fills:track&&track.session===day?track.executions:[]};
}
function terminalBookNote(evidence){
 const {track,plan}=evidence;
 const day=tradingDay();
 if(track?.status==="paused"&&(track.pause_date===day||plan?.status==="paused")){
  const explanations={unreconciled_session:"Falta conciliar una sesión anterior.",
   missing_ohlc:"Faltan precios requeridos para la valoración.",
   expired_open:"La apertura prevista pasó sin una ejecución conciliada."};
  return "Cartera pausada. Última valoración del "+shortPaperDate(track.session)+". "+
   (explanations[track.pause_reason]||"Consulta el estado del motor.");
 }
 if(plan?.status==="archived")
  return "Campaña separada. Sus ejecuciones simuladas se consultan aparte del plan de la cartera vigente.";
 if(plan?.status==="stale")
  return "Antes de abrir, el diario solo llegaba al "+shortPaperDate(plan.session)+".";
 return "";
}
function terminalRows(){
 const track=signalFeed?.tracks[tradingFilter.slot];
 const trace=track?.analysis;
 const day=tradingDay();
 const search=tradingFilter.ticker.trim().toUpperCase();
 if(trace&&(trace.date===day||terminalState.useLatest))return {trace,rows:trace.rows.filter(([ticker])=>ticker.includes(search))};
 const {plan,nextDay,next,fills}=terminalSessionEvidence(signalFeed,day,tradingFilter.slot);
 const rows=(plan?.orders||[]).filter(order=>order.ticker.includes(search)).map(order=>
  [order.ticker,signalNames[order.action],["Señal del "+shortPaperDate(order.decision_session)]]);
 for(const fill of fills.filter(fill=>fill.ticker.includes(search))){
  const price=fill.price!=null&&track.currency?" · "+fmt(fill.price)+" "+track.currency:"";
  rows.push([fill.ticker,"recorded_"+fill.action,["Ejecución simulada del "+shortPaperDate(day)+price]]);
 }
 for(const order of next.filter(order=>order.ticker.includes(search)))
  rows.push([order.ticker,"next_"+order.action,["Decisión del "+shortPaperDate(day)+" · apertura del "+shortPaperDate(nextDay)]]);
 if(plan?.status==="recorded"){
  const changed=new Set([...fills,...next].map(record=>record.ticker));
  for(const ticker of plan.holdings.filter(ticker=>ticker.includes(search)&&!changed.has(ticker)))
   rows.push([ticker,"Mantener",["Posición abierta sin orden prevista en el plan de apertura"]]);
 }
 return {trace:null,rows};
}
function terminalActivityHTML(){
 const day=tradingDay();
 const activity=terminalState.activity.get(day);
 const lanes=state.executionHistory?.live_plan?.days?.[day]?.lanes||[];
 const workflows=new Set(lanes.filter(lane=>lane.slots.includes(tradingFilter.slot)).map(lane=>lane.workflow));
 const matches=(activity?.attempts||[]).filter(attempt=>workflows.has(attempt.workflow));
 const status=activity?.error?"No se pudo comprobar el estado de los motores.":
  terminalState.pending.has(day)?"Consultando el estado del motor…":
  !workflows.size?"El calendario no acredita una ejecución programada para esta selección.":
  "No se ha observado una ejecución programada para esta sesión.";
 return '<div class="terminal-activity"><h4>Actividad del motor · '+esc(shortPaperDate(day))+'</h4>'+
  (matches.length?'<ul>'+matches.slice(-3).reverse().map(attempt=>'<li><time datetime="'+
   esc(new Date(attempt.time).toISOString())+'">'+esc(madridDateTime.format(attempt.time))+
   ' Madrid</time><span class="terminal-run-state" data-status="'+esc(attempt.status)+'">'+
   esc(terminalRunLabels[attempt.status])+'</span><a href="'+esc(attempt.url)+
   '" target="_blank" rel="noopener noreferrer">Abrir ejecución</a></li>').join("")+'</ul>':
   '<p>'+esc(status)+'</p>')+'</div>';
}
function paintTerminalActivity(){
 const node=$("terminal-activity");
 if(node&&terminalState.mode==="terminal"){
  const content=terminalActivityHTML();
  if(node.dataset.content!==content){node.innerHTML=content;node.dataset.content=content;}
 }
}
async function refreshTerminalActivity(force=false){
 if(!tradingRoomActive()||terminalState.mode!=="terminal"||document.hidden||!tradingFilter.slot)return;
 const day=tradingDay(), plan=state.executionHistory?.live_plan;
 if(!day||!plan?.days?.[day]||terminalState.pending.has(day))return;
 const session=sessionToday(plan,Date.parse(day+"T17:00:00Z"));
 if(!session.lanes||Date.now()<session.close)return;
 const prior=terminalState.activity.get(day);
 if(prior&&Date.now()-prior.checked<(force?30_000:LIVE_REFRESH_MS))return;
 terminalState.pending.add(day);
 paintTerminalActivity();
 try{
  const result=await readLiveAttempts(session,fetch,liveJobCache);
  terminalState.activity.set(day,{...result,checked:Date.now()});
 }catch{
  terminalState.activity.set(day,{...prior,error:true,checked:Date.now()});
 }finally{
  terminalState.pending.delete(day);
  paintTerminalActivity();
 }
}
function terminalHTML(){
 const track=signalFeed?.tracks[tradingFilter.slot];
 if(!track)return '<p class="trading-empty">Selecciona un algoritmo para ver su actividad y recorrer las empresas registradas.</p>';
 const {trace,rows}=terminalRows();
 const notes={
  classic:"Resultados de la regla por empresa, antes de aplicar los límites de la cartera.",
  ahp:"Filtros técnicos superados y selección final del método multicriterio.",
  monthly:"El diario conserva las empresas seleccionadas en este rebalanceo."
 };
 const otherDate=!trace&&track.analysis?.date;
 const description=trace?notes[trace.method]:
  "Plan de apertura, ejecuciones simuladas de la sesión y órdenes que quedaron previstas para la siguiente apertura.";
 const bookNote=terminalBookNote(terminalSessionEvidence(signalFeed,tradingDay(),tradingFilter.slot));
 const coverage=track.analysis_coverage;
 const stages={eligible:"elegibles",features:"con variables disponibles",evaluated:"evaluados",scored:"con puntuación"};
 const scope=coverage?coverage.eligible+" / "+coverage.total+" valores "+stages[coverage.stage]+
  " · "+shortPaperDate(coverage.date):"Cobertura del motor no publicada para esta cartera.";
 const more=terminalState.useLatest&&trace?.date!==tradingDay()?
  button("Volver al registro de la sesión","terminal-latest","selected","outline-btn"):
  otherDate?button("Ver análisis del "+shortPaperDate(otherDate),"terminal-latest","latest","outline-btn"):"";
 return '<div class="terminal-shell"><div id="terminal-activity"></div>'+
  '<div class="terminal-heading"><div><h4>Reproducción del registro · '+esc(shortPaperDate(trace?.date||tradingDay()))+
  '</h4><p>'+esc(description)+'</p>'+more+
  '<p><a href="./index.html?view=algorithm&amp;algorithm='+esc(tradingFilter.slot)+'">Consultar reglas del algoritmo</a></p></div>'+
  '<div class="terminal-buttons">'+(rows.length?
   '<button type="button" id="terminal-play" data-action="terminal-play">Reproducir</button>'+
   '<button type="button" data-action="terminal-next">Siguiente empresa</button>'+
   '<button type="button" data-action="terminal-all">Ver todo</button>':"")+'</div></div>'+
  '<p class="terminal-note terminal-scope"><strong>Cobertura del motor:</strong> '+esc(scope)+
  ' <strong>Reproducción:</strong> '+rows.length+' registros con este filtro.</p>'+
  (bookNote?'<p class="trading-coverage terminal-note">'+esc(bookNote)+'</p>':"")+
  (trace?.excluded?'<p class="terminal-note">'+esc(trace.excluded)+' incidencias de datos registradas.</p>':"")+
  (rows.length?'<div class="terminal-screen"><div class="terminal-progress">'+
   '<progress aria-label="Registros mostrados" max="'+rows.length+'" value="0"></progress><span id="terminal-count"></span></div>'+
   '<div id="terminal-visual" class="terminal-visual"></div>'+
   '<details class="terminal-ledger"><summary>Registro de empresas</summary>'+
   '<ol id="terminal-rows" aria-label="Resultados registrados por empresa"></ol></details></div>':
   '<p class="terminal-note">No hay resultados publicados para esta fecha y filtro.</p>')+
  '<p class="terminal-note">La reproducción recorre datos ya publicados. El estado del motor se consulta cada tres minutos.</p></div>';
}
const terminalPercent=new Intl.NumberFormat("es-ES",{style:"percent",maximumFractionDigits:1});

function terminalOutcome(ticker,result,trace){
 if(["buy","sell"].includes(result))return [signalNames[result],"Regla activada antes de aplicar los límites de cartera",result];
 if(result==="no_trigger"){
  const date=trace?.date;
  const day=Object.keys(signalFeed?.opening_plans||{}).find(day=>signalFeed.opening_plans[day].previous_session===date);
  const plan=signalFeed?.opening_plans?.[day]?.tracks[tradingFilter.slot];
  if(plan?.status==="recorded"&&plan.holdings.includes(ticker))
   return ["Mantener","Posición abierta sin orden prevista para la siguiente apertura","hold"];
  return ["Sin señal","La regla no activó una orden","neutral"];
 }
 if(result.startsWith("recorded_"))return [terminalLabels[result],"Ejecución registrada en el diario simulado",result.slice(9)];
 if(result.startsWith("next_")){
  const side=result.slice(5);
  return [terminalLabels[result],"Orden prevista para la siguiente apertura",side==="rebalance"?"neutral":side];
 }
 if(result==="Mantener")return [result,"Posición abierta sin orden prevista para la apertura","hold"];
 if(result==="selected")return ["Seleccionada","El algoritmo incluyó la empresa en su selección","buy"];
 if(result==="passed")return ["Pasa el filtro","Superó el filtro técnico y quedó fuera de la selección final","neutral"];
 if(result==="filtered")return ["Descartada","Quedó fuera en el filtro técnico","sell"];
 return [result,"Señal prevista para la apertura",result==="Comprar"?"buy":result==="Vender"?"sell":"neutral"];
}
function terminalCriteria(ticker,checks,trace){
 if(trace?.method==="ahp"){
  const ratios=trace.ratios?.[ticker]||{};
  return '<small class="terminal-metrics-label">% de sesiones con la condición</small>'+
   '<ul class="terminal-metrics">'+Object.entries(terminalRules).map(([key,label])=>{
    const value=ratios[key];
    const passed=checks.includes(key);
    return '<li data-pass="'+passed+'"><span>'+esc(label)+'</span>'+
     (value===undefined?'<span>Sin valor</span>':
      '<div class="terminal-meter" aria-hidden="true"><i style="--level:'+100*value+'%"></i></div>'+
      '<strong>'+esc(terminalPercent.format(value))+'</strong>')+
     '<small>'+(passed?"Cumple":"No cumple")+'</small></li>';
   }).join("")+'</ul>';
 }
 const text=trace?.method==="classic"?"Regla técnica evaluada":
  trace?.method==="monthly"?"Selección del rebalanceo":checks.join(" · ");
 return '<p class="terminal-evidence">'+esc(text)+'</p>';
}
function terminalConnector(direction,branched){
 const outgoing=["M0 50 C25 50 37 14 64 14","M0 50 C26 50 38 38 64 38",
  "M0 50 C26 50 38 62 64 62","M0 50 C25 50 37 86 64 86"];
 const incoming=["M0 14 C27 14 39 50 64 50","M0 38 C26 38 38 50 64 50",
  "M0 62 C26 62 38 50 64 50","M0 86 C27 86 39 50 64 50"];
 const paths=branched?(direction==="out"?outgoing:incoming):["M0 50 H64"];
 return '<div class="terminal-wire" data-wire="'+direction+'" aria-hidden="true">'+
  '<svg viewBox="0 0 64 100" preserveAspectRatio="none" focusable="false">'+paths.map(path=>
   '<path d="'+path+'"></path><path class="terminal-packet" pathLength="100" d="'+path+'"></path>').join("")+'</svg></div>';
}
function paintTerminalVisual(rows,trace){
 const node=$("terminal-visual");
 if(!node||!rows.length)return;
 const {stage,count}=terminalState;
 const index=Math.max(0,Math.min(rows.length-1,stage===2?count-1:count));
 const [ticker,result,checks]=rows[index];
 const [outcome,detail,tone]=terminalOutcome(ticker,result,trace);
 const steps=["Empresa","Evidencia","Resultado"];
 const html='<ol class="terminal-steps" aria-label="Pasos de la reproducción">'+steps.map((label,step)=>
  '<li'+(step===stage?' aria-current="step"':"")+'><span>0'+(step+1)+'</span>'+label+'</li>').join("")+'</ol>'+
  '<div class="terminal-board" data-stage="'+stage+'">'+
  '<div class="terminal-company"><span>REGISTRO '+(index+1)+' / '+rows.length+'</span><strong>'+esc(ticker)+'</strong></div>'+terminalConnector("out",trace?.method==="ahp")+
  '<div class="terminal-evaluation">'+(stage>=1?terminalCriteria(ticker,checks,trace):
   '<p class="terminal-evidence">'+(terminalState.timer?"Abriendo el registro…":"Lista para reproducir")+'</p>')+'</div>'+terminalConnector("in",trace?.method==="ahp")+
  '<div class="terminal-outcome" data-tone="'+(stage===2?tone:"neutral")+'"><span>Resultado registrado</span>'+
  (stage===2?'<strong>'+esc(outcome)+'</strong><small>'+esc(detail)+'</small>':
   '<strong class="terminal-awaiting">—</strong>')+'</div></div>';
 if(node.dataset.frame!==html){node.innerHTML=html;node.dataset.frame=html;}
}
function paintTerminalRows(){
 const list=$("terminal-rows");
 if(!list){paintTerminalMapFrame();return;}
 const {rows,trace}=terminalRows();
 const visible=Math.min(terminalState.count,rows.length);
 const progress=list.closest(".terminal-screen").querySelector("progress");
 progress.value=visible;
 $("terminal-count").textContent=visible+" / "+rows.length;
 const play=$("terminal-play");
 play.textContent=terminalState.timer?"Pausar":visible&&visible<rows.length?"Continuar":"Reproducir";
 const ledger=list.closest("details");
 const html=rows.slice(0,visible).map(([ticker,result,checks])=>
  '<li><strong>'+esc(ticker)+'</strong><span>'+esc(Object.hasOwn(terminalLabels,result)?terminalLabels[result]:result)+
  '</span><small>'+esc(checks.map(check=>Object.hasOwn(terminalRules,check)?terminalRules[check]:check).join(" · "))+'</small></li>').join("");
 if(list.dataset.rows!==html){list.innerHTML=html;list.dataset.rows=html;}
 if(ledger.open&&terminalState.timer)list.scrollTop=list.scrollHeight;
 paintTerminalVisual(rows,trace);
 paintTerminalMapFrame(rows,trace);
}
function stopTerminal(){
 clearInterval(terminalState.timer);
 terminalState.timer=null;
}
function resetTerminal(){
 stopTerminal();
 terminalState.count=0;
 terminalState.stage=0;
}
function runTerminalPlayback(action){
 const {rows}=terminalRows();
 if(!rows.length)return;
 const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
 if(action==="terminal-play"&&terminalState.timer){stopTerminal();paintTerminalRows();return;}
 const single=action==="terminal-next";
 stopTerminal();
 if(action==="terminal-all"||reduced){
  terminalState.count=action==="terminal-all"||!single?rows.length:Math.min(terminalState.count+1,rows.length);
  terminalState.stage=2;
  if(action==="terminal-all")$("terminal-rows").closest("details").open=true;
  paintTerminalRows();
  return;
 }
 if(terminalState.count>=rows.length)resetTerminal();
 if(terminalState.stage===2)terminalState.stage=0;
 terminalState.timer=setInterval(()=>{
  if(!tradingRoomActive()||terminalState.mode!=="terminal"){stopTerminal();return;}
  const total=terminalRows().rows.length;
  if(terminalState.stage===2)terminalState.stage=0;
  else{
   terminalState.stage++;
   if(terminalState.stage===2){
    terminalState.count=Math.min(total,terminalState.count+1);
    if(single||terminalState.count>=total)stopTerminal();
   }
  }
  paintTerminalRows();
 },430);
 paintTerminalRows();
}

const terminalFamilies=[
 {id:"classic",label:"Clásicos S&P 500",note:"Indicadores técnicos",first:10,last:18},
 {id:"weekly",label:"Machine learning",note:"Selección semanal y archivo",first:19,last:36},
 {id:"ahp",label:"Multicriterio",note:"Filtros técnicos y selección",first:37,last:37},
 {id:"fundamental",label:"Fundamental",note:"Capital Cycle y Buy The Dip",first:38,last:39},
 {id:"timesfm",label:"TimesFM",note:"Modelos de series temporales",first:40,last:43},
 {id:"genetic",label:"Genético",note:"Estrategia de referencia",first:44,last:44}
];
const mapFamily=slot=>terminalFamilies.find(family=>Number(slot.slice(3))>=family.first&&Number(slot.slice(3))<=family.last);
let expandedFamily=null;

function terminalMapHTML(){
 if(!signalFeed)return "";
 const day=tradingDay();
 const plan=signalFeed.opening_plans?.[day];
 const entries=Object.entries(signalFeed.tracks);
 const active=mapFamily(tradingFilter.slot)?.id;
 const selected=expandedFamily||active;
 const count=plan?Object.values(plan.tracks).reduce((total,track)=>total+track.orders.length,0):null;
 const branches=terminalFamilies.map((family,index)=>{
  const destination=18+32*Math.floor(index/2)+(index%2?4:-4);
  const d="M0 50 C35 50 40 "+destination+" 80 "+destination;
  return '<g data-family="'+family.id+'"><path d="'+d+'"></path><path class="terminal-map-packet" pathLength="100" d="'+d+'"></path></g>';
 }).join("");
 const groups=terminalFamilies.map(family=>{
  const members=entries.filter(([slot])=>mapFamily(slot)===family);
  const orders=plan?members.reduce((total,[slot])=>total+(plan.tracks[slot]?.orders.length||0),0):null;
  const incomplete=plan&&members.some(([slot])=>["stale","paused","unavailable"].includes(plan.tracks[slot]?.status));
  const countLabel=!orders&&incomplete?"plan incompleto":"órdenes";
  return '<button type="button" class="terminal-map-family" data-action="terminal-family" data-value="'+family.id+
   '" data-family="'+family.id+'" aria-expanded="'+(selected===family.id)+'" aria-controls="terminal-map-algorithms">'+
   '<span class="terminal-map-dot" aria-hidden="true"></span><span><strong>'+esc(family.label)+'</strong><small>'+
   esc(family.note)+'</small></span><span class="terminal-map-order-count">'+(orders??"—")+'<small>'+countLabel+'</small></span></button>';
 }).join("");
 const family=terminalFamilies.find(item=>item.id===selected);
 const algorithms=family?entries.filter(([slot])=>mapFamily(slot)===family).map(([slot,track])=>{
  const entry=plan?.tracks[slot];
  const status=entry?.status==="archived"?" · Archivo":
   track.status==="paused"&&(track.pause_date===day||entry?.status==="paused")?" · Pausada":"";
  return '<button type="button" data-action="terminal-map-algorithm" data-value="'+esc(slot)+
   '" aria-pressed="'+(tradingFilter.slot===slot)+'"><small>'+esc(slot+status)+'</small>'+esc(track.label)+'</button>';
 }).join(""):"";
 const totals=[[terminalFamilies.length,"Familias"],[entries.length,"Carteras con diario"],[count??"—","Órdenes previstas"]];
 const canPlay=terminalRows().rows.length>0;
 return '<div class="terminal-map-head"><div><h3 id="terminal-map-title">Mapa de motores</h3>'+
  '<p>Sesión '+esc(shortPaperDate(day))+' · Elige una familia y un algoritmo.</p></div>'+
  '<dl class="terminal-map-totals">'+totals.map(([value,label])=>'<div><dt>'+esc(label)+'</dt><dd>'+esc(value)+'</dd></div>').join("")+
  '</dl></div><div class="terminal-map-diagram">'+
  '<div class="terminal-map-origin"><div class="terminal-map-hub"><span>MIDAS</span><small id="terminal-map-progress">Selección de motor</small></div></div>'+
  '<svg class="terminal-map-links" viewBox="0 0 80 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">'+branches+'</svg>'+
  '<div class="terminal-map-families">'+groups+'</div></div>'+
  '<div id="terminal-map-algorithms"'+(algorithms?"":' hidden')+'>'+
  (algorithms?'<h4>'+esc(family.label)+'</h4><div class="terminal-map-choices">'+algorithms+'</div>':"")+'</div>'+
  '<div class="terminal-map-log"><div><h4>Registro de reproducción</h4>'+
  (canPlay?'<button type="button" class="outline-btn" id="terminal-map-play" data-action="terminal-play">Reproducir</button>':"")+
  '</div><div id="terminal-map-events"></div></div>';
}
function paintTerminalMap(){
 const map=$("terminal-map");
 if(!map)return;
 const html=terminalMapHTML();
 if(map.dataset.content!==html){
  const focused=map.contains(document.activeElement)?document.activeElement:null;
  map.innerHTML=html;
  map.dataset.content=html;
  if(focused?.id)$(focused.id)?.focus({preventScroll:true});
  else if(focused?.dataset.action){
   [...map.querySelectorAll("button")].find(button=>button.dataset.action===focused.dataset.action&&
    button.dataset.value===focused.dataset.value)?.focus({preventScroll:true});
  }
 }
}
function paintTerminalMapFrame(rows=[],trace=null){
 const map=$("terminal-map"),events=$("terminal-map-events");
 if(!map||!events)return;
 const active=expandedFamily||mapFamily(tradingFilter.slot)?.id;
 for(const branch of map.querySelectorAll("[data-family]"))
  branch.classList.toggle("is-active",branch.dataset.family===active);
 map.dataset.playing=String(Boolean(terminalState.timer));
 const visible=Math.min(terminalState.count,rows.length);
 const play=$("terminal-map-play");
 if(play)play.textContent=$("terminal-play")?.textContent||"Reproducir";
 const progress=$("terminal-map-progress");
 progress.textContent=rows.length?visible+" / "+rows.length+" registros":"Selección de motor";
 const note=terminalBookNote(terminalSessionEvidence(signalFeed,tradingDay(),tradingFilter.slot));
 const empty=rows.length?"Pulsa Reproducir para recorrer el registro.":note||
  (tradingFilter.slot?"Sin registros para esta sesión y filtro.":"Selecciona un algoritmo.");
 const html=visible?'<ul>'+rows.slice(Math.max(0,visible-3),visible).map(([ticker,result])=>{
  const [label,,tone]=terminalOutcome(ticker,result,trace);
  return '<li data-tone="'+esc(tone)+'"><strong>'+esc(ticker)+'</strong><span>'+esc(label)+'</span></li>';
 }).join("")+'</ul>':
  '<p>'+esc(empty)+'</p>';
 if(events.dataset.content!==html){events.innerHTML=html;events.dataset.content=html;}
}

function tradingRoom(){
 return '<section class="trading-room" aria-labelledby="trading-title">'+
  '<header class="trading-mast"><div><h2 id="trading-title">Sala de trading</h2>'+
  '<p>Señales de los algoritmos para tu operativa manual.</p></div>'+
  '<div class="trading-feed"><span id="trading-published" role="status">'+esc(tradingStatus())+'</span>'+
  '<button type="button" data-action="live-signals-refresh">Actualizar</button></div></header>'+
  '<div class="trading-workspace"><div class="terminal-mode" role="group" aria-label="Vista de la sala">'+
  button("Panel","trading-mode","signals","outline-btn")+button("Terminal de análisis","trading-mode","terminal","outline-btn")+
  '</div><p class="trading-cadence">El diario se consulta cada 30 segundos. Los gráficos muestran cierres auditados.</p>'+
  '<div class="trading-controls"><div><label for="trading-date">Sesión</label><select id="trading-date"'+
   (tradingDay()?"":" disabled")+'>'+tradingDates()+'</select></div>'+
  '<div id="desk-algorithm-picker"><span class="desk-control-label">Algoritmos</span><div id="desk-algorithm-filters"></div></div>'+
  '<div id="terminal-algorithm-picker" hidden><label for="trading-algorithm">Algoritmo</label><select id="trading-algorithm"'+
   (signalFeed?"":" disabled")+'>'+tradingAlgorithms()+'</select></div>'+
  '<div id="desk-phase-picker"><label for="desk-phase">Vista de señales</label><select id="desk-phase">'+
   tradingOptions(Object.entries(deskPhases),tradingDesk.phase)+'</select></div>'+
  '<div><label for="trading-ticker">Ticker</label><input id="trading-ticker" type="search" maxlength="14" placeholder="Ej. AAPL" value="'+esc(tradingFilter.ticker)+'"></div></div>'+
  '<div class="trading-filters" role="group" aria-label="Tipo de señal">'+
  Object.entries(tradingSides).map(([key,label])=>'<button type="button" data-action="trading-side" data-value="'+key+
   '" aria-pressed="'+(tradingFilter.side===key)+'">'+label+' <span>—</span></button>').join("")+'</div>'+
  '<section id="terminal-map" class="terminal-map" aria-labelledby="terminal-map-title" hidden></section>'+
  '<div id="trading-results"></div></div></section>';
}
function paintTradingRoom(){
 if(!tradingRoomActive())return;
 const results=$("trading-results");
 if(!results)return;
 const model=deskActivity(signalFeed,tradingDay(),tradingFilter,tradingDesk.phase,tradingDesk.slots);
 const date=$("trading-date"),algorithm=$("trading-algorithm");
 const dates=tradingDates(),algorithms=tradingAlgorithms();
 if(date.dataset.options!==dates){date.innerHTML=dates;date.dataset.options=dates;}
 if(algorithm.dataset.options!==algorithms){algorithm.innerHTML=algorithms;algorithm.dataset.options=algorithms;}
 date.disabled=!tradingDay();
 algorithm.disabled=!signalFeed;
 const terminal=terminalState.mode==="terminal";
 $("terminal-algorithm-picker").hidden=!terminal;
 $("desk-algorithm-picker").hidden=terminal;
 $("desk-phase-picker").hidden=terminal;
 const filters=$("desk-algorithm-filters"),filterHTML=deskAlgorithmFilters();
 if(filters.dataset.content!==filterHTML){
  const open=$("desk-algorithms")?.open;
  const active=document.activeElement;
  const slot=filters.contains(active)?active.dataset.deskAlgorithm:null;
  filters.innerHTML=filterHTML;
  filters.dataset.content=filterHTML;
  if(open)$("desk-algorithms").open=true;
  if(slot)filters.querySelector('[data-desk-algorithm="'+slot+'"]')?.focus({preventScroll:true});
 }
 const published=$("trading-published"),status=tradingStatus();
 if(published.textContent!==status)published.textContent=status;
 for(const chip of document.querySelectorAll("[data-action='trading-side']")){
  chip.setAttribute("aria-pressed",String(chip.dataset.value===tradingFilter.side));
  chip.querySelector("span").textContent=model.plan?model.counts[chip.dataset.value]:"—";
 }
 for(const tab of document.querySelectorAll("[data-action='trading-mode']")){
  tab.setAttribute("aria-pressed",String(tab.dataset.value===terminalState.mode));
 }
 document.querySelector(".trading-filters").hidden=terminal;
 $("terminal-map").hidden=!terminal||!signalFeed;
 if(terminal){
  paintTerminalMap();
  const content=terminalHTML();
  if(results.dataset.terminal!==content){
   results.innerHTML=content;
   results.dataset.terminal=content;
  }
  paintTerminalRows();
  paintTerminalActivity();
  void refreshTerminalActivity();
  return;
 }
 delete results.dataset.terminal;
 const focus=results.contains(document.activeElement)?document.activeElement:null;
 results.innerHTML=deskResults(model);
 if(focus?.dataset.action)
  [...results.querySelectorAll("button")].find(button=>button.dataset.action===focus.dataset.action&&
   button.dataset.value===focus.dataset.value)?.focus({preventScroll:true});
}

function liveSessionHTML(){
 // Verified public lifecycle roster, not the daily workflow denominator.
 const competing=Array.isArray(state.fullRoster?.entries)?
  state.fullRoster.entries.filter(entry=>strategyCompetitionPhase(entry.slot)==="active").length:null;
 return renderLiveSession(currentSession(),liveSessionData,Date.now(),
  state.executionHistoryStatus==="pending",competing);
}
function paintLiveSession(){
 const panel=$("monitoring-live-status");
 if(!panel||!liveSessionActive())return;
 const scroll=panel.querySelector(".session-live-scroll")?.scrollLeft??0;
 const focused=panel.contains(document.activeElement)?document.activeElement:null;
 panel.innerHTML=liveSessionHTML();
 const chart=panel.querySelector(".session-live-scroll");
 if(chart)chart.scrollLeft=scroll;
 if(focused?.dataset.action==="live-session-refresh"){
  panel.querySelector("[data-action='live-session-refresh']")?.focus({preventScroll:true});
 }else if(focused?.href){
  [...panel.querySelectorAll("a")].find(link=>link.href===focused.href)?.focus({preventScroll:true});
 }else if(focused?.classList.contains("session-live-scroll"))chart?.focus({preventScroll:true});
}
async function refreshLiveSession(force=false){
 if(!liveSessionActive()||document.hidden||liveSessionRequest)return;
 const session=currentSession();
 if(!session.lanes){paintLiveSession();return;}
 const now=Date.now();
 if(liveSessionData?.date===session.date&&now-liveLastRequest<(force?30_000:LIVE_REFRESH_MS))return;
 liveLastRequest=now;
 liveSessionRequest=readLiveAttempts(session,fetch,liveJobCache);
 try{
  const result=await liveSessionRequest;
  liveSessionData={date:session.date,status:"ok",checked:Date.now(),...result};
 }catch{
  const previous=liveSessionData?.date===session.date?liveSessionData:null;
  liveSessionData={date:session.date,status:"error",checked:previous?.checked,attempts:previous?.attempts??[]};
 }finally{
  liveSessionRequest=null;
  paintLiveSession();
 }
}
function refreshActiveMonitoring(){
 if(document.hidden)return;
 if(dailyHistoryActive())void loadExecutionHistory();
 else void refreshLiveSession();
}
document.addEventListener("visibilitychange",()=>{
 refreshActiveMonitoring();
 void refreshTerminalActivity();
 void refreshLiveSignals();
});
setInterval(refreshActiveMonitoring,LIVE_REFRESH_MS);
setInterval(()=>{void refreshTerminalActivity();},LIVE_REFRESH_MS);
setInterval(()=>{void refreshLiveSignals();},TRADING_REFRESH_MS);

function verifyExecutionHistory(doc){
 if(!doc||doc.schema!=="midas_daily_execution_health_v1"||
    !["verified_github_actions","unavailable"].includes(doc.status))throw Error("Registro diario inválido");
 if(!Array.isArray(doc.days))throw Error("Sin filas comprobables");
 if(doc.status==="unavailable"){
  if(doc.days.length)throw Error("Fuente caída con recuentos ficticios");
  return doc;
 }
 if(doc.slot_count!==64||doc.automated_slots!==26||doc.days.length>500)
  throw Error("Inventario diario inesperado");
 let previous="9999-99-99";
 for(const d of doc.days){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(d.date)||d.date>=previous)
   throw Error("Fecha diaria inválida");
  previous=d.date;
  if(!Array.isArray(d.journals)||d.journals.length>128)throw Error("Sin evidencia contable válida");
  const journalKeys=new Set(), recovered=new Set(), journalSlots=new Set();
  for(const j of d.journals){
   const key=j.slot+"/"+j.cohort;
   if(!/^IL-\d{3}$/.test(j.slot)||Number(j.slot.slice(3))<1||Number(j.slot.slice(3))>64||journalKeys.has(key)||
      !Number.isFinite(j.nav)||j.nav<0||!/^[A-Z]{3}$/.test(j.currency)||
      typeof j.cohort!=="string"||typeof j.inactive!=="boolean"||typeof j.recovered!=="boolean"||
      !/^[a-f0-9]{64}$/.test(j.source_sha256)||
      !/^https:\/\/github\.com\/idealab2026\/laboratorio-cuantitativo\/blob\/(?:main|[a-f0-9]{40})\/[A-Za-z0-9_./-]+$/.test(j.source_url)||
      j.source_url.includes("/../"))throw Error("Diario sin trazabilidad institucional");
   journalKeys.add(key);journalSlots.add(j.slot);if(j.recovered)recovered.add(j.slot);
  }
  if(d.journal_count!==journalSlots.size||d.recovered_count!==recovered.size||
     d.recovered_failures!==d.details.filter(x=>x.status==="failure"&&recovered.has(x.slot)).length)
   throw Error("Recuperaciones y diarios no conciliados");
  if(d.data_status==="archived_observations"){
   const keys=["success","failure","unverified"];
   if(keys.some(k=>!Number.isInteger(d[k])||d[k]<0)||
      keys.reduce((n,k)=>n+d[k],0)!==d.expected||d.details.length!==d.expected||
      keys.some(k=>d[k]!==d.details.filter(x=>x.status===k).length)||
      ["not_run","pending","not_scheduled","complete"].some(k=>d[k]!==null))
    throw Error("Archivo histórico con programación inventada");
   const ids=new Set();
   for(const item of d.details){
    if(!/^IL-\d{3}$/.test(item.slot)||Number(item.slot.slice(3))<1||Number(item.slot.slice(3))>64||ids.has(item.slot)||
       !["success","failure","unverified"].includes(item.status)||!Array.isArray(item.workflows)||!item.workflows.length)
     throw Error("Resultado archivado inválido");
    ids.add(item.slot);
    for(const w of item.workflows){
     if(w.source_kind!=="reviewed_archive"||w.run_url!==null||w.run_id!==null||
        !/^[a-z0-9_-]+\.yml$/.test(w.workflow)||!/^ARCH-\d{4}$/.test(w.evidence_id)||
        !Number.isInteger(w.attempts)||w.attempts<1||!keys.includes(w.status)||
        !/^[a-f0-9]{64}$/.test(w.evidence_sha256)||
        !/^https:\/\/github\.com\/idealab2026\/laboratorio-cuantitativo\/blob\/(?:main|[a-f0-9]{40})\/data\/execution-history-archive\.json$/.test(w.evidence_url))
      throw Error("Evidencia archivada sin revisión institucional");
    }
   }
   continue;
  }
  if(d.data_status==="not_verifiable"){
   if(d.details.length!==0||d.complete!==null||
      ["expected","success","failure","not_run","pending","unverified","not_scheduled"].some(k=>d[k]!==null))
    throw Error("Sin histórico pero con resultados inventados");
   continue;
  }
  if(!["verified","partially_verified"].includes(d.data_status))
   throw Error("Cobertura diaria desconocida");
  if(!Number.isInteger(d.expected)||!Number.isInteger(d.not_scheduled)||
     d.expected+d.not_scheduled!==64||!Array.isArray(d.details)||d.details.length!==d.expected)
   throw Error("Inventario diario no conciliado");
  let sum=0;const ids=new Set();
  for(const key of ["success","failure","not_run","pending","unverified"]){
   if(!Number.isInteger(d[key])||d[key]<0)throw Error("Recuento diario incorrecto");
   sum+=d[key];
  }
  if(sum!==d.expected)throw Error("Resultados de ejecución no conciliados");
  for(const item of d.details){
   if(!/^IL-\d{3}$/.test(item.slot)||ids.has(item.slot)||
      !["success","failure","not_run","pending","unverified"].includes(item.status)||
      !Array.isArray(item.workflows)||!item.workflows.length)
    throw Error("Algoritmo duplicado o sin trazabilidad");
   ids.add(item.slot);
   for(const workflow of item.workflows){
    if(!/^[a-z0-9_-]+\.yml$/.test(workflow.workflow)||
       (workflow.run_url&&!/^https:\/\/github\.com\/idealab2026\/laboratorio-cuantitativo\/actions\/runs\/\d+$/.test(workflow.run_url)))
      throw Error("Enlace de ejecución no autorizado");
   }
  }
 }
 return doc;
}
function renderDailyExecutionTable(doc,status,roster){
 if(status==="pending")return '<p class="audit-method-note">Consultando diarios conservados y ejecuciones programadas…</p>';
 if(!["verified","stale"].includes(status)||!doc||doc.status!=="verified_github_actions")
  return '<p class="audit-method-note">No se ha podido verificar el histórico de sesiones. No se muestran ceros ni fallos inventados.</p>';
 const num=v=>v===null?"N/D":new Intl.NumberFormat("es-ES").format(v);
 const names=new Map((roster?.entries||[]).map(e=>[e.slot,e.name]));
 const captions={success:"Correcto",failure:"Falló originalmente",not_run:"Sin ejecución",pending:"Pendiente",unverified:"Sin evidencia histórica"};
 const rows=doc.days.map(day=>{
  const label=day.date.split("-").reverse().join("/");
  const bySlot=new Map(day.details.map(d=>[d.slot,d]));
  const journals=new Map();
  for(const j of day.journals){if(!journals.has(j.slot))journals.set(j.slot,[]);journals.get(j.slot).push(j);}
  const ids=[...new Set([...bySlot.keys(),...journals.keys()])].sort((a,b)=>{
   const rank={failure:0,not_run:1,unverified:2,pending:3,success:4};
   return (rank[bySlot.get(a)?.status]??5)-(rank[bySlot.get(b)?.status]??5)||a.localeCompare(b);
  });
  const expanded=ids.length?'<details class="daily-execution-details"><summary>Ver '+ids.length+(ids.length===1?' algoritmo':' algoritmos')+'</summary>'+
   '<div class="daily-execution-subtable"><table><thead><tr><th>Algoritmo</th><th>Diario conservado</th><th>Automatización</th><th>Evidencia</th></tr></thead><tbody>'+
   ids.map(sid=>{
    const d=bySlot.get(sid), records=journals.get(sid)||[];
    const journalText=records.length?records.map(j=>{
     const label=j.inactive?"Recuperada · sin operaciones":j.recovered?"Valoración recuperada":"Valoración registrada";
     const nav=new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2}).format(j.nav);
     return '<strong>'+esc(label)+'</strong><small>'+esc(j.cohort)+' · NAV '+esc(nav)+' '+esc(j.currency)+
      (j.recorded_at_utc?' · registrada '+esc(j.recorded_at_utc.replace("T"," ").slice(0,16))+' UTC':"")+
      (j.first_trading_session?' · reanudación habilitada '+esc(j.first_trading_session):"")+'</small>';
    }).join(""):'Sin valoración registrada para esta fecha';
    const links=(d?.workflows||[]).map(w=>{
     const textLabel=esc(w.workflow.replace(/\.yml$/,"").replaceAll("_"," "));
     if(w.source_kind==="reviewed_archive")return '<a href="'+esc(w.evidence_url)+'" target="_blank" rel="noopener noreferrer">Archivo técnico · '+textLabel+'</a><small>'+esc(w.evidence_id)+' · '+num(w.attempts)+' intentos · SHA-256 '+esc(w.evidence_sha256)+'</small>';
     return w.run_url?'<a href="'+esc(w.run_url)+'" target="_blank" rel="noopener noreferrer">'+textLabel+'</a>':
      '<span>'+textLabel+' · sin ejecución registrada</span>';
    });
    for(const j of records)links.push('<a href="'+esc(j.source_url)+'" target="_blank" rel="noopener noreferrer">Diario · '+esc(j.cohort)+'</a><small>SHA-256 '+esc(j.source_sha256)+'</small>');
    const recovered=records.some(j=>j.recovered);
    const runLabel=d?captions[d.status]:day.data_status==="not_verifiable"?"Sin verificar":"Sin automatización acreditada";
    return '<tr><td><strong>'+esc(sid)+'</strong><small>'+esc(names.get(sid)||"")+'</small></td>'+
     '<td>'+journalText+'</td><td><span class="daily-run-state '+esc(d?.status||"unverified")+'">'+esc(runLabel)+'</span>'+
     (d?.status==="failure"&&recovered?'<small class="daily-recovery-note">Recuperación posterior documentada; se conserva el fallo original.</small>':"")+
     (d?.reason?'<small>'+esc(d.reason)+'</small>':"")+'</td><td>'+links.join("<br>")+'</td></tr>';
   }).join("")+'</tbody></table></div></details>':'Sin registros disponibles';
  const technical=day.technical_as_of_utc?"Último registro técnico disponible · "+day.technical_as_of_utc.replace("T"," ").slice(0,16)+" UTC":
   day.data_status==="archived_observations"?"Archivo técnico recuperado":
   day.data_status==="not_verifiable"?"Automatización sin verificar":
   day.complete?"Registro técnico completo":
   day.success||day.failure||day.not_run?"Registro técnico parcial":"Registro técnico pendiente";
  const outcomeCount=value=>num(value===0&&!day.complete&&day.data_status!=="archived_observations"?null:value);
  return '<tr'+(day.data_status==="not_verifiable"?' class="daily-unverifiable"':"")+'><td><strong>'+esc(label)+'</strong><small>'+esc(technical)+'</small></td>'+
   '<td class="daily-count">'+num(day.journal_count)+'</td>'+
   '<td class="daily-count daily-ok">'+num(day.recovered_count)+'</td>'+
   (day.data_status==="not_verifiable"?'<td colspan="6">Sin registro técnico acreditado para esta fecha</td>':
   '<td class="daily-count daily-ok">'+outcomeCount(day.success)+'</td>'+
   '<td class="daily-count daily-fail">'+outcomeCount(day.failure)+(day.recovered_failures?'<small class="daily-recovery-note">'+num(day.recovered_failures)+' recuperados</small>':"")+'</td>'+
   (day.data_status==="archived_observations"?'<td colspan="4">Archivo de ejecuciones; programación histórica no reconstruida'+
    (day.unverified?' · '+num(day.unverified)+' resultados sin verificar':"")+'</td>':
   '<td class="daily-count daily-absent">'+outcomeCount(day.not_run)+'</td>'+
   '<td class="daily-count">'+num(day.pending)+'</td>'+
   '<td class="daily-count daily-unverified">'+num(day.unverified)+'</td>'+
   '<td class="daily-count daily-neutral">'+num(day.not_scheduled)+'</td>'))+
   '<td>'+expanded+'</td></tr>';
 }).join("");
 return '<div class="daily-ledger-header"><strong>Histórico de sesiones y automatización</strong>'+
   '<span>Diarios conservados + GitHub Actions · actualizado '+esc(doc.as_of_utc.replace("T"," ").slice(0,16))+' UTC</span></div>'+
  (status==="stale"?'<p class="audit-method-note">No se pudo actualizar el histórico. Se muestra la última información disponible.</p>':"")+
  '<p class="audit-method-note">Registros conservados desde '+esc(doc.first_tracked_session.split("-").reverse().join("/"))+
   '. «Diarios» cuenta algoritmos con valoración registrada; «Recuperadas» identifica valoraciones añadidas después de una interrupción. '+
   'Las cohortes archivadas conservan su identidad y no se unen a la campaña activa. '+
   (doc.reviewed_archive?'Archivo técnico recuperado: '+esc(doc.reviewed_archive.first_session)+' a '+esc(doc.reviewed_archive.last_session)+'. ':"")+
   (doc.actions_available===false?'La consulta actual de GitHub Actions no está disponible. Se muestran los diarios y la última evidencia técnica publicada.':
    'Automatización institucional verificable desde '+esc(doc.oldest_retained_run_session||"fecha aún no acreditada")+'. Las fechas sin registro técnico conservan sus valoraciones.')+'</p>'+
  '<div class="table-scroll daily-execution-scroll"><table class="daily-execution-table"><thead><tr>'+
   '<th>Fecha / sesión</th><th>Diarios</th><th>Recuperadas</th><th>Correctos</th><th>Fallos originales</th><th>No ejecutados</th>'+
   '<th>Pendientes</th><th>Sin verificar</th><th>Sin programación</th><th>Detalle</th></tr></thead><tbody>'+
   rows+'</tbody></table></div>'+
  '<p class="monitoring-caveat">Los diarios acreditan valoraciones conservadas, no una ejecución automática puntual ni compraventas. '+
   'Una sesión recuperada sin operaciones mantiene las posiciones y no inventa órdenes pasadas. Los fallos originales siguen visibles junto a su recuperación. '+
   'El archivo recuperado acredita los resultados observados; no permite inferir ejecuciones ausentes ni reconstruir toda la programación histórica. '+
   'Los recuentos de automatización institucional cubren los 26 algoritmos vinculados a workflows programados de los 64 catalogados. '+
   'Un workflow compartido cuenta por cada algoritmo asociado, pero su éxito no acredita independientemente todos los libros. '+
   'Los reintentos de madrugada corresponden a la sesión estadounidense anterior. «No ejecutados» solo cuenta ejecuciones vencidas sin registro; las futuras permanecen pendientes. '+
   '«Sin programación» incluye archivos, propuestas y algoritmos no previstos ese día. Las fechas históricas se conservan tal como constan en sus diarios.</p>';
}
function monitoring(){
 const roster=state.fullRoster, candidates=state.strategyCandidates, audit=state.operationsAudit;
 const summary=summarizeOperationsAudit(audit);
 const number=v=>Number.isInteger(v)?new Intl.NumberFormat("es-ES").format(v):"N/D";
 const rosterCount=Array.isArray(roster?.entries)?roster.entries.length:null;
 const proposals=Array.isArray(candidates?.candidates)?candidates.candidates.length:null;
 const registered=rosterCount!==null&&proposals!==null?rosterCount+proposals:null;
 const feed=state.paperFeedRead;
 const productive=feed?.status==="source_verified"?
   [...feed.bySlot.values()].filter(x=>x.activity==="active"||x.activity==="cash").length:
   feed?.status==="not_connected"?0:null;
 const latestPaper=summary?.latestSession||state.originalPaper?.latest||null;
 const latestTrade=summary?.latestTrade||null;
 const selectedTab=["summary","operations","daily"].includes(state.monitoringTab)?state.monitoringTab:"today";
 const tabs='<div class="monitoring-tabs" id="monitoring-tab-strip" role="tablist" aria-label="Paneles de salud operativa">'+
  monitoringTabs.map(([key,label])=>
   '<button type="button" role="tab" data-action="monitoring-tab" data-value="'+key+
   '" aria-selected="'+(selectedTab===key)+'" aria-controls="monitoring-panel-'+key+'">'+label+'</button>').join("")+'</div>';
 const health=summary?summary.withExecutions:null;
 const totalPaper=summary?.slots||rosterCount;
 const percent=totalPaper?Math.min(100,Math.max(0,100*(health||0)/totalPaper)):0;
 const summaryPanel='<div id="monitoring-panel-summary" role="tabpanel"'+(selectedTab!=="summary"?' hidden':'')+'>'+
  '<div class="monitoring-kpis">'+
  '<article><span>Algoritmos propuestos</span><strong>'+number(registered)+'</strong>'+
   '<small>'+(registered!==null?rosterCount+' estrategias en inventario + '+proposals+' propuesta en investigación':'Comprobando el inventario de proyectos')+'</small></article>'+
  '<article><span>Algoritmos productivos</span><strong>'+number(productive)+'</strong>'+
   '<small>Con ejecución institucional vigente acreditada; no cuenta diarios históricos</small></article>'+
  '<article><span>Algoritmos con operaciones paper</span><strong>'+number(health)+'</strong>'+
   '<small>Libros con compras o ventas registradas, no prueba de operación actual</small></article>'+
  '<article><span>Última sesión de trading paper</span><strong>'+esc(shortPaperDate(latestPaper))+'</strong>'+
   '<small>Última compraventa documentada: '+esc(shortPaperDate(latestTrade))+'</small></article>'+
  '</div>'+
  '<section class="monitoring-chart-panel"><div class="monitoring-chart-header"><h3>Cobertura del diario de operaciones</h3>'+
   '<strong>'+(health!==null&&totalPaper!==null?number(health)+' / '+number(totalPaper):"N/D")+'</strong></div>'+
   '<div class="monitoring-coverage-bar" role="img" aria-label="'+
    esc(health!==null&&totalPaper!==null?health+' de '+totalPaper+' estrategias con operaciones paper archivadas':'Sin datos de cobertura verificables')+
    '"><span style="width:'+percent.toFixed(2)+'%"></span></div>'+
   '<div class="monitoring-coverage-legend"><span>Con compraventas verificables: '+number(health)+'</span>'+
    '<span>Sin compraventas reconstruibles: '+number(summary?.withoutExecutions)+'</span></div>'+
   '<p class="monitoring-explanation">Diarios históricos con posiciones simuladas y precios observados del mercado. No implican que los algoritmos estén ejecutándose hoy. '+(summary?'Ejecuciones documentadas: '+number(summary.executions)+'. Conversiones corporativas: '+number(summary.conversions)+'.':'Cargando libro de operaciones.')+'</p></section>'+
  '<p class="monitoring-caveat">«Productivo» exige un motor institucional con registro independiente verificable. Un algoritmo con resultados paper archivados no se clasifica automáticamente como productivo. Si falla la fuente de verificación, se muestra N/D en lugar de atribuirle actividad.</p>'+
  '</div>';
 const options=roster?.entries?.map(x=>({id:x.slot,name:originalStrategyName(x)}))||
   (audit?Object.keys(audit.tracks).sort().map(id=>({id,name:id})):[]);
 const chosen=options.some(x=>x.id===state.monitoringStrategy)?
  state.monitoringStrategy:options[0]?.id||null;
 const picker='<div class="monitoring-operation-controls"><label for="monitoring-algorithm">Algoritmo</label>'+
  '<select id="monitoring-algorithm" aria-label="Seleccionar algoritmo para revisar operaciones"'+(options.length?'':' disabled')+'>'+
  options.map(x=>{
   const count=audit?.tracks?.[x.id]?.coverage?.executions;
   return '<option value="'+esc(x.id)+'"'+(x.id===chosen?' selected':'')+'>'+esc(x.id+' · '+x.name)+
     (Number.isInteger(count)?' · '+count+' ejecuciones':'')+'</option>';
  }).join("")+'</select></div>';
 const table=chosen&&audit?.tracks?.[chosen]?
  renderTradeLotsTable(audit.tracks[chosen],state.monitoringSort,state.monitoringDesc):
  '<p class="audit-method-note">'+
   (state.operationsAuditStatus==="pending"?"Comprobando el registro auditado de compras y ventas…":
    "No hay un libro de ejecuciones verificable para mostrar la tabla.")+'</p>';
 const operationPanel='<div id="monitoring-panel-operations" role="tabpanel"'+(selectedTab!=="operations"?' hidden':'')+'>'+
  '<p class="monitoring-explanation">Registro por lotes, idéntico al apartado «Operaciones» de la ficha de cada algoritmo. Las estrategias sin fills individuales quedan señaladas como sin operaciones documentadas.</p>'+
  picker+'<div id="monitoring-trade-table">'+table+'</div></div>';
 const dailyPanel='<div id="monitoring-panel-daily" role="tabpanel"'+(selectedTab!=="daily"?' hidden':'')+'>'+
  renderDailyExecutionTable(state.executionHistory,state.executionHistoryStatus,roster)+'</div>';
 return head("SALUD OPERATIVA","Estado del laboratorio MIDAS",
  "Propuestas, actividad paper documentada y evidencia de producción, separadas para no confundir simulaciones con ejecución automática.")+
  tabs+'<div id="monitoring-panel-today" role="tabpanel"'+(selectedTab!=="today"?' hidden':'')+'>'+
  '<p><a href="./index.html?view=trading">Abrir Sala de trading para filtrar las señales</a></p>'+liveSignalsPanel()+'<div id="monitoring-live-status">'+liveSessionHTML()+'</div></div>'+summaryPanel+operationPanel+dailyPanel;
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
 const selected=COMPETITION_PHASES.includes(state.competitionPhase)?state.competitionPhase:"active";
 const existing=filterRoster(state.fullRoster,{group:state.fullRosterGroup}).filter(item=>
  strategyCompetitionPhase(item.slot)===selected&&
  (!q||[item.slot,item.group,item.name,originalStrategyName(item)].some(x=>x.toLocaleLowerCase("es").includes(q)))
 ).map(item=>({id:item.slot,name:originalStrategyName(item),group:item.group,
  item,record:economicPaperRecord(item.slot),candidate:null}));
 const proposals=selected==="development"&&state.strategyCandidates?
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
 const phase=COMPETITION_PHASES.includes(state.competitionPhase)?state.competitionPhase:"active";
 const phases=partitionCompetitionRows(d.entries);
 const research=state.strategyCandidates?.candidates||[];
 const counts={
  active:phases.active.length,
  obsolete:phases.obsolete.length,
  development:phases.development.length+research.length
 };
 // Only source-admitted CURRENT paper slots may lead the active leaderboard.
 // The historical campaigns are never ranked against active paper campaigns.
 const leader=phase==="active"?paperLeaderboard(phases.active.map(item=>({
  id:item.slot,name:originalStrategyName(item),record:economicPaperRecord(item.slot)
 }))):null;
 const tabs='<div class="competition-lifecycle-tabs" role="tablist" aria-label="Fase de las estrategias">'+
  [["active","Activos"],["obsolete","Obsoletos"],["development","En desarrollo"]].map(([key,label])=>
   '<button type="button" role="tab" data-action="competition-phase" data-value="'+key+
   '" aria-selected="'+(phase===key)+'" aria-controls="competition-lifecycle-panel">'+
   esc(label)+' <span class="competition-phase-count">'+counts[key]+'</span></button>').join("")+
  '</div>';
 const leaderBlock=leader?'<div class="paper-leader" role="status" aria-label="Líder de la cohorte paper activa">'+
  '<div><span class="paper-leader-label">LÍDER PROVISIONAL · RENTABILIDAD ACUMULADA PAPER</span>'+
  '<strong>'+esc(leader.name)+'</strong>'+
  '<small>'+esc(leader.id)+' · inicio '+esc(shortPaperDate(leader.record.first_session))+
  ' · '+esc(leader.record.session_count)+' sesiones · último cierre '+esc(shortPaperDate(leader.record.last_session))+'</small></div>'+
  '<div class="paper-leader-return">'+pctText(leader.record.return_pct)+'</div>'+
  button("Ver ficha","full-detail",leader.id,"outline-btn")+'</div>':
  '<div class="paper-leader"><strong>Sin líder verificable</strong><small>No hay resultados actuales con trazabilidad suficiente para una clasificación de rentabilidad.</small></div>';
 const context=phase==="active"?
   '<p class="competition-phase-context">La rentabilidad se calcula sobre capital simulado y precios de mercado registrados en el diario. '+
   'Consulta el inicio, el último cierre y la divisa de cada cartera antes de comparar. '+
   '<a href="./index.html?view=trading">Abrir Sala de trading</a>.</p>':
  phase==="obsolete"?
   '<div class="competition-phase-notice"><strong>Campañas históricas retiradas</strong><span>Sus sesiones y resultados se conservan para consulta. No participan en la clasificación ni en el liderazgo de la competición vigente.</span></div>':
   '<div class="competition-phase-notice"><strong>Investigación y desarrollo</strong><span>'+
   phases.development.length+' estrategias sin operativa comparable acreditada'+
   (state.strategyCandidates?'; '+research.length+' propuesta de investigación adicional.':'; las propuestas adicionales aún no se han podido verificar.')+
   ' No se asigna rentabilidad ni líder a proyectos sin operaciones documentadas.</span></div>';
 const summary=phase==="active"?counts.active+' estrategias con seguimiento vigente':
  phase==="obsolete"?counts.obsolete+' campañas históricas retiradas':
  phases.development.length+' estrategias en desarrollo'+(state.strategyCandidates?' · '+research.length+' propuesta adicional':" · propuestas sin verificar");
 return '<div class="competition-heading"><h2>Clasificación de algoritmos</h2>'+
  '<span>'+esc(summary)+' · '+meta.count+' fichas catalogadas</span></div>'+
  tabs+'<section id="competition-lifecycle-panel" role="tabpanel" aria-label="'+
   esc(phase==="active"?"Activos":phase==="obsolete"?"Obsoletos":"En desarrollo")+'">'+
  (phase==="active"?leaderBlock:context)+
  (phase==="active"?context:"")+
  fullMobileSortControls()+
  '<div class="table-scroll table-compact full-competition-table"><table><thead><tr>'+
  fullRosterHeaders()+'</tr></thead><tbody id="full-rows">'+fullRosterRows()+
  '</tbody></table></div></section>';
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
 // NAV observations and audited actions are different sources; align ONLY by date.
 // A NAV observation never implies that a buy, sale or hold took place.
 const auditTrack=state.operationsAudit?.tracks?.[id]||null;
 const navActions=new Map(buildSessionActionColumns(auditTrack).map(row=>[row.date,row]));
 const navActionCell=(day,key)=>{
  if(!auditTrack)return '<span class="audit-no-data">'+
    (state.operationsAuditStatus==="pending"?"Cargando…":"N/D")+'</span>';
  const row=navActions.get(day);
  if(!row)return '<span class="audit-no-data" title="Sin registro individual acreditado para esta fecha">N/D</span>';
  return renderSessionTickerList(row[key],key==="sells"?row.partialSells:[]);
 };
 const measured=history.length?
  '<section class="algorithm-section"><h3>Evolución de capital y sesiones</h3>'+
  '<p>Diario paper procedente del archivo contrastado; no es dinero real ni prueba de ejecución diaria actual.</p>'+
  fullHistoryChart(history)+
  '<details><summary>Consultar las '+history.length+' observaciones del NAV</summary>'+
  '<div class="table-scroll nav-session-table-wrap"><table class="table-compact nav-session-table"><thead><tr>'+
  '<th scope="col">Sesión</th><th scope="col">NAV</th>'+
  '<th scope="col">Rentabilidad desde el inicio</th>'+
  '<th scope="col">COMPRAS</th><th scope="col">VENTAS</th><th scope="col">MANTENER</th>'+
  '</tr></thead><tbody>'+
  history.map(p=>'<tr><td>'+esc(p.date)+'</td><td>'+fmtMoney(p.nav)+'</td><td>'+
   (finite(record?.initial_capital)&&record.initial_capital>0?pctText(100*(p.nav/record.initial_capital-1)):"N/D")+
   '</td><td>'+navActionCell(p.date,"buys")+'</td>'+
   '<td>'+navActionCell(p.date,"sells")+'</td>'+
   '<td>'+navActionCell(p.date,"holds")+'</td></tr>').join("")+
  '</tbody></table></div>'+
  '<p class="audit-method-note">* Venta parcial acreditada: permanecen acciones del mismo ticker. MANTENER expresa continuidad contable inferida, no una orden. — indica que no consta ninguna acción de esa clase en una sesión auditada; N/D significa que falta el desglose de acciones para esa fecha.</p>'+
  '</details></section>':
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
  '<span>'+esc(id)+' · '+esc(compactGroup(group))+'</span>'+
  (strategyCompetitionPhase(id)==="active"?
   '<a class="outline-btn" href="./index.html?view=trading&amp;algorithm='+esc(id)+'">Ver señales en Sala de trading</a>':"")+'</div>'+
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
 ["Auditoría pública","Datos licenciados, fuentes temporales, validación fuera de muestra, trazabilidad y monitorización antes de atribuir capacidad predictiva."],
 ["Robustez del backtest","El protocolo combina ventanas sucesivas fuera de muestra, Monte Carlo por bloques de retornos y cambios pequeños en cada parámetro congelado. Las pruebas usan costes y una referencia comparable. Un resultado alto por sí solo no acredita la estrategia."]
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
 const home=state.view==="home";
 $("midas-home").hidden=!home;
 $("app").hidden=home;
 document.body.classList.toggle("midas-thesis-mode",state.view==="thesis");
 document.body.classList.toggle("midas-trading-mode",tradingRoomActive());
 const pages={competition,algorithm:algorithmFiche,synthetic:syntheticCompetition,algorithms,theses,thesis:thesisView,monitoring,ported,full,method:methodology,glossary,trading:tradingRoom};
 document.querySelectorAll(".product-tabs [data-view]").forEach(b=>{const active=b.dataset.view===state.view||(state.view==="algorithm"&&b.dataset.view==="competition")||(state.view==="thesis"&&b.dataset.view==="theses");b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
 if(home||!state.data)return;
 $("app").innerHTML=(pages[state.view]||competition)();
 const financialPicker=document.getElementById("financial-sankey-period");
 if(financialPicker)financialPicker.addEventListener("change",()=>{
  const ticker=(new URLSearchParams(location.search).get("ticker")||"").toUpperCase();
  if(state.financialSankeys.has(ticker)){
   state.financialPeriodByTicker.set(ticker,financialPicker.value);render();
  }
 });
 chart();
 if(liveSessionActive()){void refreshLiveSession();void refreshLiveSignals();}
 if(tradingRoomActive()){paintTradingRoom();void refreshLiveSignals();}
}
function resolveMidasView(){
 const requested=new URLSearchParams(location.search).get("view");
 // Keep legacy competition bookmarks pointing to the competition.
 if(requested==="overview"||requested==="archive"){
  const u=new URL(location.href);u.searchParams.set("view","competition");
  history.replaceState({view:"competition"},"",u);
  return "competition";
 }
 return viewNames.includes(requested)?requested:"home";
}
function go(view){
 if(!viewNames.includes(view))return;
 state.view=view;
 const u=new URL(location.href);
 u.searchParams.set("view",view);
 if(view==="algorithm"&&state.algorithmId)u.searchParams.set("algorithm",state.algorithmId);
 else u.searchParams.delete("algorithm");
 if(view!=="thesis")u.searchParams.delete("ticker");
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
 if(!/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/.test(id))return;
 if(!state.publicTheses.has(id)&&!state.universe.issuers.some(i=>i.ticker===id))return;
 const url="./index.html?view=thesis&ticker="+encodeURIComponent(id);
 window.open(url,"_blank","noopener,noreferrer");
}
$("app").addEventListener("click",e=>{
 const b=e.target.closest("button[data-action]");
 if(!b){
  const row=e.target.closest("tr[data-competition-id]");
  if(row){openCompetitionRow(row.dataset.competitionId);return;}
  if(e.target.closest("a[href]"))return;
  const issuer=e.target.closest("tr[data-issuer-id]");
  if(issuer)openIssuerRow(issuer.dataset.issuerId);
  return;
 }
 const {action,value}=b.dataset;
 if(action==="navigate"){state.detailOpen=false;go(value);}
 else if(action==="full-detail"){
  if(!state.fullRoster?.entries.some(x=>x.slot===value)&&
     !state.strategyCandidates?.candidates.some(c=>c.id===value))return;
  state.auditTab="sessions";state.auditSort="recent";state.auditDesc=true;
  state.algorithmId=value;go("algorithm");
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
  state.competitionPhase="active";state.fullRosterGroup="";state.fullRosterQuery=value;render();
 }
 else if(action==="competition-phase"){
  if(!COMPETITION_PHASES.includes(value))return;
  const previous=document.querySelector(".competition-lifecycle-tabs")?.getBoundingClientRect().top;
  state.competitionPhase=value;
  state.fullRosterGroup="";state.fullRosterQuery="";
  render();
  if(Number.isFinite(previous)){
   const after=document.querySelector(".competition-lifecycle-tabs")?.getBoundingClientRect().top;
   if(Number.isFinite(after))window.scrollBy({top:after-previous,behavior:"auto"});
  }
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
 else if(action==="live-session-refresh"){void refreshLiveSession(true);}
 else if(action==="live-signals-refresh"){void refreshLiveSignals(true);void refreshTerminalActivity(true);}
 else if(action==="trading-mode"&&["signals","terminal"].includes(value)){
  resetTerminal();
  terminalState.mode=value;
  const url=new URL(location.href);
  if(value==="terminal")url.searchParams.set("panel","terminal");
  else url.searchParams.delete("panel");
  history.replaceState(history.state,"",url);
  paintTradingRoom();
 }
 else if(action==="terminal-family"&&terminalFamilies.some(family=>family.id===value)){
  if(mapFamily(tradingFilter.slot)?.id!==value)selectTerminalAlgorithm("");
  expandedFamily=value;
  paintTradingRoom();
 }
 else if(action==="terminal-map-algorithm"&&signalFeed?.tracks[value]){
  selectTerminalAlgorithm(value);
  paintTradingRoom();
 }
 else if(action==="terminal-latest"){
  resetTerminal();terminalState.useLatest=value==="latest";paintTradingRoom();
 }
 else if(["terminal-play","terminal-all","terminal-next"].includes(action)){runTerminalPlayback(action);}
 else if(action==="desk-reset"){tradingDesk.slots.clear();paintTradingRoom();}
 else if(["desk-chart","desk-chart-remove"].includes(action)&&validSignalTicker(value)){
  const model=deskActivity(signalFeed,tradingDay(),tradingFilter,tradingDesk.phase,tradingDesk.slots);
  const current=deskChartSymbols(model.orders);
  if(action==="desk-chart-remove")tradingDesk.symbols=current.filter(symbol=>symbol!==value);
  else tradingDesk.symbols=[value,...current.filter(symbol=>symbol!==value)].slice(0,3);
  paintTradingRoom();
 }
 else if(action==="trading-side"&&Object.hasOwn(tradingSides,value)){
  tradingFilter.side=value;paintTradingRoom();
 }
 else if(action==="monitoring-tab"){
  state.monitoringTab=monitoringTabs.some(([key])=>key===value)?value:"today";
  const tabs=document.querySelector("#monitoring-tab-strip");
  if(tabs){
   for(const tab of tabs.querySelectorAll("[data-action='monitoring-tab']"))
    tab.setAttribute("aria-selected",String(tab.dataset.value===state.monitoringTab));
   for(const [key] of monitoringTabs){
    const el=document.querySelector("#monitoring-panel-"+key);
    if(el)el.hidden=key!==state.monitoringTab;
   }
  }
  if(liveSessionActive()){paintLiveSession();void refreshLiveSession();void refreshLiveSignals();}
  else if(dailyHistoryActive())void loadExecutionHistory();
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
  const inHealth=state.view==="monitoring";
  if(inHealth){
   if(state.monitoringSort===value)state.monitoringDesc=!state.monitoringDesc;
   else{state.monitoringSort=value;state.monitoringDesc=true;}
  }else{
   if(state.auditSort===value)state.auditDesc=!state.auditDesc;
   else{state.auditSort=value;state.auditDesc=true;}
  }
  const region=inHealth?"#monitoring-panel-operations":"#audit-tab-strip";
  const top=document.querySelector(region)?.getBoundingClientRect().top;
  render();
  if(Number.isFinite(top)){
   const next=document.querySelector(region)?.getBoundingClientRect().top;
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
 if(el.id==="trading-date"&&signalFeed?.opening_plans?.[el.value]){
  resetTerminal();terminalState.useLatest=false;tradingFilter.date=el.value;paintTradingRoom();
 }
 if(el.id==="trading-algorithm"){selectTerminalAlgorithm(el.value);paintTradingRoom();}
 if(el.id==="desk-phase"&&Object.hasOwn(deskPhases,el.value)){tradingDesk.phase=el.value;paintTradingRoom();}
 if(el.dataset.deskAlgorithm&&signalFeed?.tracks[el.dataset.deskAlgorithm]){
  if(el.checked)tradingDesk.slots.add(el.dataset.deskAlgorithm);
  else tradingDesk.slots.delete(el.dataset.deskAlgorithm);
  paintTradingRoom();
 }
 if(el.id==="midas-opening-date"&&signalFeed?.opening_plans?.[el.value]){
  signalPlanDate=el.value;
  const content=$("midas-signal-content");
  if(content)content.innerHTML=liveSignalsContent();
 }
 if(el.id==="live-signal-algorithm"&&signalFeed?.tracks[el.value]){
  signalSlot=el.value;
  const content=$("midas-signal-content");
  if(content)content.innerHTML=liveSignalsContent();
 }
 if(el.id==="monitoring-algorithm"){
  if(!/^IL-\d{3}$/.test(el.value)||!state.operationsAudit?.tracks?.[el.value])return;
  state.monitoringStrategy=el.value;
  const place=document.querySelector("#monitoring-trade-table");
  if(place)place.innerHTML=renderTradeLotsTable(state.operationsAudit.tracks[el.value],state.monitoringSort,state.monitoringDesc);
 }
});
$("app").addEventListener("input",e=>{
 if(e.target.id==="trading-ticker"){
  stopTerminal();terminalState.count=Number.MAX_SAFE_INTEGER;terminalState.stage=2;
  tradingFilter.ticker=e.target.value;paintTradingRoom();
  if(terminalState.mode==="terminal")paintTerminalRows();
 }
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
function selectTerminalAlgorithm(slot){
 resetTerminal();terminalState.useLatest=false;tradingFilter.slot=slot;
 expandedFamily=mapFamily(slot)?.id||null;
 const url=new URL(location.href);
 if(slot)url.searchParams.set("algorithm",slot);
 else url.searchParams.delete("algorithm");
 history.replaceState(history.state,"",url);
}
function readViewFromURL(){
 state.view=resolveMidasView();
 state.algorithmId=new URLSearchParams(location.search).get("algorithm");
 if(tradingRoomActive()){
  const id=state.algorithmId||"";
  terminalState.mode=new URLSearchParams(location.search).get("panel")==="terminal"?"terminal":"signals";
  resetTerminal();terminalState.useLatest=false;expandedFamily=null;
  const slot=Number(id.slice(3));
  tradingFilter.slot=/^IL-\d{3}$/.test(id)&&slot>=10&&slot<=44?id:"";
  tradingDesk.slots=new Set(tradingFilter.slot&&terminalState.mode!=="terminal"?[tradingFilter.slot]:[]);
 }
}
window.addEventListener("popstate",()=>{readViewFromURL();state.detailOpen=false;render();});
async function init(){
 try{
  const [r,p,full,financial]=await Promise.all([fetch("./data/demo.json",{cache:"no-store"}),fetch("./data/public-theses.json",{cache:"no-store"}),fetch("./data/thesis-reports.json",{cache:"no-store"}),fetch("./data/financial-sankeys.json",{cache:"no-store"})]);
  if(!r.ok||!p.ok||!full.ok||!financial.ok)throw Error("Public datasets or official financial Sankey catalog missing");
  const data=await r.json(),universe=data.issuerCatalog,publication=await p.json();
  verify(data);verifyIssuerCatalog(universe);
  const stats=verifyPublicTheses(publication);
  state.fullReports=verifyFullReports(await full.json(),new Set(publication.records.map(x=>x.ticker)));
  state.financialSankeys=verifyFinancialSankeys(await financial.json(),new Set(publication.records.map(x=>x.ticker)));
  state.publicTheses=new Map(publication.records.map(x=>[x.ticker,x]));
  state.publicThesesMetadata={...stats,published_as_of:publication.published_as_of};
  state.data=data;state.universe=universe;render();void loadPublicCloses();void loadOfficialFx();void loadForecastLedger();void loadSecFilings();void loadOfficialYield();void loadOriginalPaper();void loadHistoricalPaper();void loadFullRoster();void loadStrategyCandidates();void loadInstitutionalPaperFeed();void loadOperationsAudit();void loadExecutionHistory().then(()=>{if(tradingRoomActive()&&terminalState.mode==="terminal")paintTradingRoom();});
 }catch(e){$("app").textContent="No se ha podido cargar el catálogo de emisores o el laboratorio sintético; no se muestran datos no verificados.";}
}
/* The public snapshot is refreshed in-browser; it never queries a market vendor.
   An authorised EOD publisher must update the canonical JSON independently. */
let publicCloseLoadInProgress=false;
async function loadPublicCloses(){
 if(!state.universe||publicCloseLoadInProgress||document.visibilityState==="hidden")return;
 publicCloseLoadInProgress=true;
 const previous=JSON.stringify([...state.publicCloses]);
 const previousStatus=state.closeFeedStatus;
 try{
  const response=await fetch("./data/public-closes.json",{cache:"no-store"});
  if(!response.ok)throw Error("Public price feed missing");
  const allowed=new Set([...state.universe.issuers.map(x=>x.ticker),...state.publicTheses.keys()]);
  const checked=verifyPublicCloseFeed(await response.json(),allowed);
  state.publicCloses=checked.quotes;
  state.closeFeedStatus=checked.status;
  state.closeFeedSource=checked.source;
  state.closeFeedUpdatedAt=checked.updatedAt||null;
 }catch(_error){
  state.publicCloses=new Map();
  state.closeFeedStatus="unavailable";
  state.closeFeedSource=null;
  state.closeFeedUpdatedAt=null;
 }finally{publicCloseLoadInProgress=false;}
 if(state.view==="theses"&&(previous!==JSON.stringify([...state.publicCloses])||previousStatus!==state.closeFeedStatus)){
  const scroll=document.querySelector(".thesis-public-table")?.scrollLeft||0;
  render();
  const element=document.querySelector(".thesis-public-table");
  if(element)element.scrollLeft=scroll;
 }
}
window.setInterval(()=>{if(state.view==="theses")void loadPublicCloses();},86400000);
window.addEventListener("focus",()=>{if(state.view==="theses")void loadPublicCloses();});
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&state.view==="theses")void loadPublicCloses();});

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
 if(["theses","thesis"].includes(state.view)&&state.data)render();
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
 if(["full","competition","algorithm","monitoring"].includes(state.view)&&state.data)render();
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
 if(["full","competition","algorithm","monitoring"].includes(state.view)&&state.data)render();
}
async function loadFullRoster(){
 try{
  const response=await fetch("./data/competition-roster.json",{cache:"no-store"});
  if(!response.ok)throw Error("Missing institution-only roster");
  const doc=await response.json();
  verifyFullRoster(doc);
  state.fullRoster=doc;state.fullRosterStatus="ok";
 }catch(_error){state.fullRoster=null;state.fullRosterStatus="unavailable";}
 if(["full","competition","algorithm","monitoring"].includes(state.view)&&state.data)render();
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
 if(["full","competition","algorithm","monitoring"].includes(state.view)&&state.data)render();
}
let executionHistoryLoading=false;
async function loadExecutionHistory(){
 if(executionHistoryLoading)return;
 executionHistoryLoading=true;
 const previous=state.executionHistory;
 const previousStatus=state.executionHistoryStatus;
 try{
  const response=await fetch("./data/execution-history.json",{cache:"no-store"});
  if(!response.ok)throw Error("No daily execution ledger");
  const doc=verifyExecutionHistory(await response.json());
  if(doc.status!=="verified_github_actions"||
     (previous&&Date.parse(doc.as_of_utc)<Date.parse(previous.as_of_utc)))
   throw Error("No current execution evidence");
  if(doc.as_of_utc!==previous?.as_of_utc)state.executionHistory=doc;
  state.executionHistoryStatus="verified";
 }catch(_error){
  state.executionHistoryStatus=previous?"stale":"unavailable";
 }finally{
  executionHistoryLoading=false;
 }
 if(state.view==="monitoring"&&state.data&&
    (previous!==state.executionHistory||previousStatus!==state.executionHistoryStatus))render();
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
 if(["algorithm","monitoring"].includes(state.view)&&state.data)render();
 if(tradingRoomActive()&&terminalState.mode!=="terminal")paintTradingRoom();
}

readViewFromURL();
render();
init();
