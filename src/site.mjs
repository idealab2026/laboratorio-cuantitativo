import {verify,simulate,rank,valuation,thesisRank,formatPct,money,finite,verifyIssuerCatalog,filterIssuers,syntheticBarsFromDemo,nextOpenPaper} from "./metrics.mjs";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>finite(n)?new Intl.NumberFormat("es-ES",{maximumFractionDigits:2}).format(n):"N/D";
const state={data:null,universe:null,view:"overview",strategy:"P-01",group:"",sort:"returnPct",asc:false,thesis:"T-01",query:"",thesisSort:"central",issuerMode:"catalog",issuerQuery:"",issuerSort:"ticker",issuerTicker:"MSFT"};
const viewNames=["overview","competition","algorithms","theses","monitoring","method"];
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
function sparkline(nav){
 if(!Array.isArray(nav)||nav.length<2||nav.some(n=>!finite(n)))return "N/D";
 const lo=Math.min(...nav),hi=Math.max(...nav),span=Math.max(hi-lo,.01);
 const points=nav.map((n,i)=>(3+i*110/(nav.length-1)).toFixed(1)+","+(27-(n-lo)*23/span).toFixed(1)).join(" ");
 return '<svg class="mini-chart '+tone(nav.at(-1)-nav[0])+'" viewBox="0 0 116 32" width="116" height="32" role="img" aria-label="Evolución sintética del capital"><polyline points="'+points+'" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"/></svg>';
}
const metric=(label,value)=>'<div class="metric"><strong>'+esc(value)+'</strong><small>'+esc(label)+'</small></div>';
const family=(g)=>({"Clásicas":"Equiponderación, tendencia, reversión, menor variabilidad y control en efectivo.","Aprendizaje semanal":"Proxies de métodos supervisados; no se han entrenado modelos reales.","Predicción temporal":"Modelos temporales de referencia; no se ha ejecutado TimesFM.","Capital Cycle":"Ciclo de inversión y disciplina de valoración con supuestos observables.","Buy The Dip":"Escalonamiento de exposición tras caídas, con reserva de liquidez.","Modelos experimentales":"Multicriterio, parámetros fijos y filtro de estrés."})[g]||"Prototipo de estrategia paper.";
function summary(){
 $("stat-strategies").textContent=all().length;
 $("stat-groups").textContent=groups().length;
 $("stat-theses").textContent=state.universe.issuers.length;
 $("stat-sessions").textContent=state.data.dates.length;
}
function overview(){
 const first=rank(state.data)[0];
 const featured=["MSFT","META","PLTR"].map(t=>state.universe.issuers.find(i=>i.ticker===t)).filter(Boolean);
 return head("INICIO · INVESTIGACIÓN","Laboratorio cuantitativo","Comparación reproducible de métodos y catálogo público de compañías. Las clasificaciones son sintéticas; no se atribuyen rentabilidades bursátiles reales.")+
 '<div class="section-grid">'+card('<span class="label">Variación simulada más alta</span><h3>'+esc(first.name)+'</h3><div class="headline-value '+tone(first.returnPct)+'">'+esc(formatPct(first.returnPct))+'</div><p>Resultado exclusivamente sintético; no existen operaciones en bolsa.</p>'+button("Abrir ficha","select",first.id))+
 card('<span class="label">Universo de empresas</span><h3>'+state.universe.issuers.length+' emisores y estudios identificados</h3><p>Empresas reales, sin publicar precios ni valoraciones no verificados; investigación institucional pendiente.</p>'+button("Ver empresas","navigate","theses"))+'</div>'+
 head("CATÁLOGO","Familias de estrategias","Las simulaciones siguen siendo demostraciones; los modelos entrenados de la sección de investigación no están conectados a esta competición.")+
 '<div class="family-grid">'+groups().map(g=>card('<div class="panel-top"><h3>'+esc(g)+'</h3><span class="chip">'+all().filter(x=>x.group===g).length+' métodos</span></div><p>'+esc(family(g))+'</p>'+button("Examinar","group",g))).join("")+'</div>'+
 head("EMPRESAS","Seguimiento por emisor","Nombres reales y mercados de referencia; fichas públicas en preparación, sin replicar documentos externos ni carteras privadas.")+
 '<div class="section-grid three">'+featured.map(t=>card('<span class="label">'+esc(t.ticker)+' · '+esc(t.market)+'</span><h3>'+esc(t.company)+'</h3><p>'+esc(t.sector)+'</p><p>Valoración pública independiente: pendiente de validación.</p>'+button("Ver ficha","issuer-select",t.ticker))).join("")+'</div>'+
 disclaimer("No existe migración completa de los motores ni de los expedientes de inversión. Sin cotizaciones actualizadas, no se muestran CAGR históricos como pronósticos vigentes.");
}
function competition(){
 const rows=rank(state.data,state.sort,state.asc,state.group);
 const current=active();
 return head("COMPETICIÓN PAPER","Clasificación de algoritmos","Tabla compacta: un algoritmo por fila, actividad, rentabilidad y curva de NAV. Todo el registro es sintético, no histórico de mercado.")+
 disclaimer("SIMULACIÓN SINTÉTICA · Las rentabilidades, órdenes y curvas no son resultados de inversión reales ni operaciones verificadas.")+
 '<div class="filters"><label>Familia<select id="group-select"><option value="">Todas</option>'+groups().map(g=>'<option value="'+esc(g)+'" '+(state.group===g?"selected":"")+'>'+esc(g)+'</option>').join("")+'</select></label>'+
 '<label>Ordenar<select id="rank-select">'+[["returnPct","Rentabilidad"],["drawdownPct","Drawdown"],["volatilityPct","Volatilidad"],["sharpe","Sharpe"],["name","Nombre"]].map(([v,n])=>'<option value="'+esc(v)+'" '+(state.sort===v?"selected":"")+'>'+esc(n)+'</option>').join("")+'</select></label>'+
 button(state.asc?"↑ Ascendente":"↓ Descendente","direction","","outline-btn")+button("Exportar CSV","export","ranking","outline-btn")+'</div>'+
 '<div class="table-scroll table-compact"><table><thead><tr><th>Algoritmo</th><th>Familia</th><th class="number">Rentabilidad</th><th class="number">DD máx.</th><th class="number">Vol.</th><th class="number">Sharpe</th><th>Actividad paper</th><th>Curva</th><th>Ficha</th></tr></thead><tbody>'+
 rows.map(s=>{
  const exposed=s.weights.filter(w=>w>0.005).length;
  const activity=s.orders.length===0?"Sin operaciones":"Órdenes: "+s.orders.length;
  return '<tr class="'+(s.id===current.id?"is-selected":"")+'"><td><strong>'+esc(s.name)+'</strong> <small class="inline-id">'+esc(s.id)+'</small></td><td>'+esc(s.group)+'</td><td class="number">'+pctText(s.returnPct)+'</td><td class="number">'+esc(fmt(s.drawdownPct))+' %</td><td class="number">'+(finite(s.volatilityPct)?esc(fmt(s.volatilityPct))+" %":"N/D")+'</td><td class="number">'+esc(fmt(s.sharpe))+'</td><td><span class="activity-main">'+esc(activity)+'</span><small class="activity-meta">'+exposed+' activos · '+esc(fmt(Math.max(0,s.cash)*100))+' % caja</small></td><td>'+sparkline(s.nav)+'</td><td>'+button("Ver","select",s.id)+'</td></tr>';
 }).join("")+'</tbody></table></div>'+
 '<p class="table-note">Una fila por algoritmo. Ordenes, posiciones, retornos y minigráficas corresponden únicamente a 48 sesiones artificiales. Los colores indican el signo, no una recomendación.</p>'+
 head("FICHA TÉCNICA","Detalle y operaciones","Consulta el NAV, exposición, movimientos y costes del método seleccionado.")+detail(current);
}
function detail(s){
 const proxy=["linear","direction","crossrank","perceptron","memory","ensemble","weekly","daily","genetic"].includes(s.mode);
 return '<div class="strategy-detail"><article class="panel"><div class="panel-top"><div><span class="label">'+esc(s.group)+' · '+esc(s.id)+'</span><h3>'+esc(s.name)+'</h3></div><span class="chip">PAPER · SINTÉTICO</span></div><p>'+esc(s.rule)+'</p>'+
 '<div class="metric-strip">'+metric("Variación",formatPct(s.returnPct))+metric("DD máximo",fmt(s.drawdownPct)+" %")+metric("Volatilidad",fmt(s.volatilityPct)+" %")+metric("Sharpe",fmt(s.sharpe))+'</div>'+
 '<div class="chart-hdr"><strong>Curva del NAV simulado</strong><small>Base 100 · '+s.sessions+' sesiones</small></div><svg id="nav-chart" viewBox="0 0 760 290" role="img" aria-label="Curva de capital paper"></svg>'+
 (proxy?disclaimer("Proxy matemático: no se ha entrenado ni ejecutado el modelo externo de esta familia."):"")+'</article>'+
 '<aside class="panel"><div class="label">CARTERA PAPER</div><h3>'+esc(s.name)+'</h3>'+metric("Capital ficticio final",money(s.points.at(-1).equity))+metric("Costes teóricos",money(s.fees))+metric("Operaciones simuladas",String(s.orders.length))+
 '<div class="minor-heading">Exposición al último cierre</div>'+Object.keys(state.data.market).map((k,i)=>'<div class="bar-label"><span>'+esc(k)+'</span><strong>'+fmt(s.weights[i]*100)+' %</strong></div><div class="exposure-bar"><i style="width:'+Math.max(0,Math.min(100,s.weights[i]*100))+'%"></i></div>').join("")+
 '<p class="small-note">Coste asumido: '+fmt(s.cost_bps)+' puntos básicos por unidad negociada. Sin conexión a ningún broker.</p>'+button("Diario de órdenes","journal",s.id,"outline-btn")+button("Exportar NAV","export","nav","outline-btn")+'</aside></div>';
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

function issuerTableRows(){
 return filterIssuers(state.universe,state.issuerQuery,state.issuerSort).map(i=>
 '<tr class="'+(state.issuerTicker===i.ticker?"is-selected":"")+'"><td><strong>'+esc(i.ticker)+'</strong></td><td><strong>'+esc(i.company)+'</strong><small class="smallline">'+esc(i.sector)+'</small></td><td>'+esc(i.market)+'</td><td class="number">N/D</td><td class="number perf-neutral">N/D</td><td class="number perf-neutral">N/D</td><td class="number perf-neutral">N/D</td><td class="number">N/D</td><td class="number">N/D</td><td>N/D</td><td>'+button("Ficha","issuer-select",i.ticker)+'</td></tr>'
 ).join("");
}
function issuerDetail(){
 const i=state.universe.issuers.find(x=>x.ticker===state.issuerTicker)||state.universe.issuers[0];
 return card('<div class="panel-top"><div><span class="label">'+esc(i.ticker)+' · '+esc(i.market)+'</span><h3>'+esc(i.company)+'</h3></div><span class="status-chip">Pendiente de validación</span></div><p>'+esc(i.sector)+'</p>'+
 '<div class="metric-strip">'+metric("Cotización verificable","N/D")+metric("Bear / Base / Bull","N/D")+metric("Precio para CAGR 15 %","N/D")+metric("Próximos resultados","N/D")+'</div>'+
 '<h3 class="minor-heading">Fuentes oficiales</h3>'+(i.secCik?'<p>Expediente regulatorio verificado de la SEC: <a href="https://www.sec.gov/edgar/browse/?CIK='+esc(i.secCik)+'" target="_blank" rel="noopener noreferrer">Consultar formularios SEC (10-K, 10-Q, 8-K)</a>. Esto no implica que las cuentas y supuestos de valoración se hayan auditado.</p>':'<p>Identificador de expediente regulatorio pendiente de contrastar.</p>')+
 '<h3 class="minor-heading">Control de publicación</h3><p>Identidad del emisor incorporada al catálogo. Para publicar una tesis hacen falta fuentes primarias, fecha y divisa de precio, escenarios reconstruidos, CAGR y una revisión independiente. No se traslada un dossier privado ni se enlaza a él.</p>');
}
function theses(){
 if(state.issuerMode==="demo")return syntheticTheses();
 return head("TESIS · CATÁLOGO PÚBLICO","Empresas analizadas y en seguimiento","Inventario de "+state.universe.issuers.length+" compañías y estudios. Se muestran sus nombres y mercados, pero ninguna valoración histórica se presenta como dato actual.")+
 disclaimer("DATOS PENDIENTES · N/D significa que IDEA LAB no ha validado todavía una cotización puntual ni una tesis publicable de forma independiente. No equivale a rentabilidad cero.")+
 '<div class="filters"><label>Buscar<input id="issuer-query" type="search" placeholder="Ticker, empresa o sector" value="'+esc(state.issuerQuery)+'"></label>'+
 '<label>Ordenar<select id="issuer-sort">'+[["ticker","Ticker"],["company","Empresa"],["market","Mercado"],["sector","Sector"]].map(([k,n])=>'<option value="'+k+'" '+(k===state.issuerSort?"selected":"")+'>'+n+'</option>').join("")+'</select></label>'+
 button("Exportar catálogo CSV","export","issuers","outline-btn")+button("Ver tesis ficticias","issuer-mode","demo","outline-btn")+'</div>'+
 '<div class="table-scroll table-compact thesis-public-table"><table><thead><tr><th>Ticker</th><th>Empresa</th><th>Mercado</th><th class="number">Precio actual</th><th class="number">CAGR Bear 5a</th><th class="number">CAGR Base 5a</th><th class="number">CAGR Bull 5a</th><th class="number">Precio 15 %</th><th class="number">Objetivo 5a</th><th>Resultados</th><th>Informe</th></tr></thead><tbody id="issuer-rows">'+issuerTableRows()+'</tbody></table></div>'+
 head("ANÁLISIS","Ficha pública de emisor","Fichas independientes: sin referencias privadas ni métricas financieras trasladadas sin auditoría.")+issuerDetail()+
 disclaimer("El catálogo público no equivale a una migración documental. Los estados y objetivos históricos requieren reconstrucción y autorización de publicación independientes.");
}

function monitoring(){
 const s=active(),audit=causalLedger();
 return head("SEGUIMIENTO","Diario paper y salud de fuentes","Se conservan operaciones hipotéticas, reglas de costes y ausencia de fuentes verificadas. No existe conectividad con cuentas reales.")+
 '<div class="section-grid three">'+card('<span class="label">PROCEDENCIA</span><h3>Datos sintéticos</h3><p>Tres activos ficticios. Ningún proveedor de cotizaciones.</p>')+
 card('<span class="label">COTIZACIONES AUSENTES</span><h3>0 en el ejemplo</h3><p>Si un precio es inválido, la simulación no fabrica un fill ni un NAV.</p>')+
 card('<span class="label">ESTADO FINANCIERO</span><h3>Sin operaciones reales</h3><p>Solo operaciones paper calculadas en el navegador.</p>')+'</div>'+
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
function methodology(){
 return head("MÉTODO Y LÍMITES","Evaluación reproducible","La infraestructura pública reproduce la experiencia funcional de un laboratorio cuantitativo, pero no ha importado ni los resultados ni los motores entrenados de ningún sistema externo.")+
 '<div class="method-grid">'+[
 ["Reloj causal","Cada señal se genera con los datos sintéticos disponibles hasta la sesión anterior; no se usan retornos futuros para seleccionar la cartera."],
 ["Contabilidad paper","Cambios de exposición, comisiones teóricas, curva de capital y riesgo calculados de manera determinista."],
 ["Comparaciones","Ventana común y supuestos declarados. No anualizar una demostración breve para afirmar resultados reales."],
 ["Tesis","Valoraciones bajo hipótesis, crecimiento, múltiplos y rentabilidad requerida, con criterios de refutación."],
 ["Modelos pendientes","Entrenamiento real de modelos de árboles, redes, modelos de series y evolución paramétrica no implementado."],
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
 const pages={overview,competition,algorithms,theses,monitoring,method:methodology};
 document.querySelectorAll(".product-tabs [data-view]").forEach(b=>{const active=b.dataset.view===state.view;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
 $("app").innerHTML=(pages[state.view]||overview)();chart();
}
function go(view){if(!viewNames.includes(view))return;state.view=view;const u=new URL(location.href);u.searchParams.set("view",view);history.pushState({view},"",u);render();window.scrollTo({top:0,behavior:"auto"});}
const asCSV=rows=>rows.map(row=>row.map(x=>'"'+String(x??"").replaceAll('"','""')+'"').join(",")).join("\n");
function download(name,rows){const u=URL.createObjectURL(new Blob(["\ufeff"+asCSV(rows)],{type:"text/csv;charset=utf-8"}));const a=document.createElement("a");a.href=u;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(u);}
function exportData(what){
 if(what==="ranking"){download("midas-ranking-sintetico.csv",[["algoritmo","familia","retorno_pct","drawdown_pct","volatilidad_pct","sharpe","coste"],...rank(state.data,state.sort,state.asc,state.group).map(x=>[x.name,x.group,x.returnPct,x.drawdownPct,x.volatilityPct,x.sharpe,x.fees])]);}
 if(what==="nav"){download("midas-curva-paper-sintetica.csv",[["sesion","nav_base_100","capital_ficticio"],...active().points.map(p=>[p.session,p.nav,p.equity])]);}
 if(what==="next-open"){const a=causalLedger();download("midas-ordenes-next-open-sinteticas.csv",[["senal_al_cierre","fill_apertura_siguiente","activo","lado","apertura_sintetica","precio_paper","unidades","notional","comision","deslizamiento"],...a.orders.map(o=>[o.signalAt,o.fillAt,o.symbol,o.side,o.openPrice,o.fillPrice,o.units,o.notional,o.fee,o.slippage])]);}
 if(what==="journal"){download("midas-diario-sintetico.csv",[["sesion","activo","accion","precio","unidades","nocional","coste"],...active().orders.map(x=>[x.session,x.symbol,x.action,x.referencePrice,x.units,x.notional,x.cost])]);}
 if(what==="issuers"){download("midas-emisores-publicos.csv",[["ticker","empresa","mercado","sector","precio_actual","cagr_bear_5y","cagr_base_5y","cagr_bull_5y","precio_15pct","objetivo_5y","proximos_resultados","estado"],...filterIssuers(state.universe,state.issuerQuery,state.issuerSort).map(i=>[i.ticker,i.company,i.market,i.sector,"N/D","N/D","N/D","N/D","N/D","N/D","N/D",i.status])]);}
 if(what==="theses"){download("midas-tesis-sinteticas.csv",[["entidad","sector","metodo","estado","cagr_central","valor_bajista","valor_central","valor_alcista"],...thesisRank(state.data).map(x=>[x.company,x.sector,x.method,x.status,x.central,x.valuation.bear.fair,x.valuation.base.fair,x.valuation.bull.fair])]);}
}
$("app").addEventListener("click",e=>{
 const b=e.target.closest("button[data-action]");if(!b)return;const {action,value}=b.dataset;
 if(action==="navigate")go(value);
 else if(action==="select"||action==="journal"){state.strategy=value;go(action==="journal"?"monitoring":"competition");}
 else if(action==="group"){state.group=value;go("competition");}
 else if(action==="thesis"){state.thesis=value;state.issuerMode="demo";go("theses");}
 else if(action==="issuer-mode"){state.issuerMode=value==="demo"?"demo":"catalog";render();}
 else if(action==="issuer-select"){state.issuerTicker=value;state.issuerMode="catalog";if(state.view!=="theses")go("theses");else render();}
 else if(action==="direction"){state.asc=!state.asc;render();}
 else if(action==="export")exportData(value);
});
$("app").addEventListener("change",e=>{
 const el=e.target;
 if(el.id==="group-select"){state.group=el.value;render();}
 if(el.id==="rank-select"){state.sort=el.value;render();}
 if(el.id==="thesis-sort"){state.thesisSort=el.value;render();}
 if(el.id==="issuer-sort"){state.issuerSort=el.value;render();}
 if(el.id==="journal-select"){state.strategy=el.value;render();}
});
$("app").addEventListener("input",e=>{
 if(e.target.id==="thesis-query"){state.query=e.target.value;const tbody=$("thesis-rows");if(tbody)tbody.innerHTML=thesisTableRows();}
 if(e.target.id==="issuer-query"){state.issuerQuery=e.target.value;const tbody=$("issuer-rows");if(tbody)tbody.innerHTML=issuerTableRows();}
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
 state.strategy=id;state.group="";state.sort="returnPct";summary();go("competition");
});
document.querySelectorAll(".product-tabs [data-view]").forEach(b=>b.addEventListener("click",()=>go(b.dataset.view)));
window.addEventListener("popstate",()=>{const v=new URLSearchParams(location.search).get("view");state.view=viewNames.includes(v)?v:"overview";render();});
async function init(){
 try{
  const r=await fetch("./data/demo.json",{cache:"no-store"});if(!r.ok)throw Error("Dataset missing");const data=await r.json(),universe=data.issuerCatalog;verify(data);verifyIssuerCatalog(universe);
  state.data=data;state.universe=universe;const v=new URLSearchParams(location.search).get("view");state.view=viewNames.includes(v)?v:"overview";summary();render();
 }catch(e){$("app").textContent="No se ha podido cargar el catálogo de emisores o el laboratorio sintético; no se muestran datos no verificados.";}
}
init();
