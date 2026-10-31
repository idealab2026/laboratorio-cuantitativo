import {verify,simulate,rank,valuation,thesisRank,formatPct,money,finite} from "./metrics.mjs";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>finite(n)?new Intl.NumberFormat("es-ES",{maximumFractionDigits:2}).format(n):"N/D";
const state={data:null,view:"overview",strategy:"P-01",group:"",sort:"returnPct",asc:false,thesis:"T-01",query:"",thesisSort:"central"};
const viewNames=["overview","competition","algorithms","theses","monitoring","method"];
const button=(label,action,value,cls="smallbtn")=>'<button type="button" class="'+cls+'" data-action="'+esc(action)+'" data-value="'+esc(value)+'">'+esc(label)+'</button>';
const head=(label,title,body)=>'<div class="section-heading"><div><span class="kicker">'+esc(label)+'</span><h2>'+esc(title)+'</h2><p class="section-context">'+esc(body)+'</p></div></div>';
const card=(html)=>'<article class="panel">'+html+'</article>';
const disclaimer=(body)=>'<div class="research-note">'+esc(body)+'</div>';
const all=()=>state.data.strategies;
const active=()=>simulate(state.data,state.strategy);
const groups=()=>[...new Set(all().map(s=>s.group))];
const metric=(label,value)=>'<div class="metric"><strong>'+esc(value)+'</strong><small>'+esc(label)+'</small></div>';
const family=(g)=>({"Clásicas":"Equiponderación, tendencia, reversión, menor variabilidad y control en efectivo.","Aprendizaje semanal":"Proxies de métodos supervisados; no se han entrenado modelos reales.","Predicción temporal":"Modelos temporales de referencia; no se ha ejecutado TimesFM.","Capital Cycle":"Ciclo de inversión y disciplina de valoración con supuestos observables.","Buy The Dip":"Escalonamiento de exposición tras caídas, con reserva de liquidez.","Modelos experimentales":"Multicriterio, parámetros fijos y filtro de estrés."})[g]||"Prototipo de estrategia paper.";
function summary(){
 $("stat-strategies").textContent=all().length;
 $("stat-groups").textContent=groups().length;
 $("stat-theses").textContent=state.data.theses.length;
 $("stat-sessions").textContent=state.data.dates.length;
}
function overview(){
 const first=rank(state.data)[0];
 return head("INICIO · INVESTIGACIÓN","Laboratorio cuantitativo","El objetivo es comparar algoritmos y documentar hipótesis con reglas de evaluación reproducibles. Todas las cifras actuales corresponden a una demostración sintética.")+
 '<div class="section-grid">'+card('<span class="label">Mayor variación ilustrativa</span><h3>'+esc(first.name)+'</h3><div class="headline-value">'+esc(formatPct(first.returnPct))+'</div><p>Solo una simulación hipotética: no hay operaciones en mercado.</p>'+button("Abrir ficha","select",first.id))+
 card('<span class="label">Comparación y control</span><h3>'+groups().length+' familias de algoritmos</h3><p>Las series se calculan sobre exactamente el mismo período y activos ficticios. No se importan carteras personales.</p>'+button("Abrir competición","navigate","competition"))+'</div>'+
 head("CATÁLOGO","Familias de estrategias","Una ficha por familia y un detalle operativo por algoritmo, con advertencias para los modelos aún no entrenados.")+
 '<div class="family-grid">'+groups().map(g=>card('<div class="panel-top"><h3>'+esc(g)+'</h3><span class="chip">'+all().filter(x=>x.group===g).length+' métodos</span></div><p>'+esc(family(g))+'</p>'+button("Examinar","group",g))).join("")+'</div>'+
 head("TESIS Y WATCHLIST","Escenarios de valoración","Los flujos, múltiples y precios son ficticios. No corresponden a emisores cotizados.")+
 '<div class="section-grid three">'+thesisRank(state.data).slice(0,3).map(t=>card('<span class="label">'+esc(t.sector)+'</span><h3>'+esc(t.company)+'</h3><p>'+esc(t.thesis)+'</p>'+metric("CAGR base simulado",formatPct(t.central))+button("Analizar","thesis",t.id))).join("")+'</div>'+
 disclaimer("Los modelos de aprendizaje automático, modelos temporales y algoritmos genéticos originales no se han trasladado. Los proxies demuestran las operaciones paper, sin atribuir capacidad predictiva real.");
}
function competition(){
 const rows=rank(state.data,state.sort,state.asc,state.group);
 const current=active();
 return head("COMPETICIÓN PAPER","Clasificación de algoritmos","Cada método parte de 100.000 unidades ficticias y recibe señales basadas en sesiones anteriores, con costes explícitos.")+
 disclaimer("MUESTRA SINTÉTICA. Las curvas y la clasificación no son rentabilidad real ni un backtest validado sobre mercado.")+
 '<div class="filters"><label>Familia<select id="group-select"><option value="">Todas</option>'+groups().map(g=>'<option value="'+esc(g)+'" '+(state.group===g?"selected":"")+'>'+esc(g)+'</option>').join("")+'</select></label>'+
 '<label>Ordenar<select id="rank-select">'+[["returnPct","Rentabilidad"],["drawdownPct","Drawdown"],["volatilityPct","Volatilidad"],["sharpe","Sharpe"],["name","Nombre"]].map(([v,n])=>'<option value="'+esc(v)+'" '+(state.sort===v?"selected":"")+'>'+esc(n)+'</option>').join("")+'</select></label>'+
 button(state.asc?"↑ Ascendente":"↓ Descendente","direction","","outline-btn")+button("Exportar CSV","export","ranking","outline-btn")+'</div>'+
 '<div class="table-scroll"><table><thead><tr><th>Algoritmo</th><th>Bloque</th><th class="number">Retorno</th><th class="number">DD máx.</th><th class="number">Vol. anualizada</th><th class="number">Sharpe</th><th class="number">Sesiones</th><th>Ficha</th></tr></thead><tbody>'+rows.map(s=>'<tr class="'+(s.id===current.id?"is-selected":"")+'"><td><strong>'+esc(s.name)+'</strong><small class="smallline">'+esc(s.id)+'</small></td><td>'+esc(s.group)+'</td><td class="number">'+esc(formatPct(s.returnPct))+'</td><td class="number">'+fmt(s.drawdownPct)+' %</td><td class="number">'+(finite(s.volatilityPct)?fmt(s.volatilityPct)+" %":"N/D")+'</td><td class="number">'+fmt(s.sharpe)+'</td><td class="number">'+s.sessions+'</td><td>'+button("Examinar","select",s.id)+'</td></tr>').join("")+'</tbody></table></div>'+
 '<p class="table-note">Volatilidad y Sharpe anualizados sobre 48 sesiones artificiales: carecen de inferencia estadística sobre mercados reales.</p>'+
 head("FICHA TÉCNICA","Detalle y operaciones","Consulta la evolución del NAV, pesos, actividad y comisiones del método elegido.")+detail(current);
}
function detail(s){
 const proxy=["linear","direction","crossrank","perceptron","memory","ensemble","weekly","daily","genetic"].includes(s.mode);
 return '<div class="strategy-detail"><article class="panel"><div class="panel-top"><div><span class="label">'+esc(s.group)+' · '+esc(s.id)+'</span><h3>'+esc(s.name)+'</h3></div><span class="chip">PAPER · SINTÉTICO</span></div><p>'+esc(s.rule)+'</p>'+
 '<div class="metric-strip">'+metric("Variación",formatPct(s.returnPct))+metric("DD máximo",fmt(s.drawdownPct)+" %")+metric("Volatilidad",fmt(s.volatilityPct)+" %")+metric("Sharpe",fmt(s.sharpe))+'</div>'+
 '<div class="chart-hdr"><strong>Curva del NAV simulado</strong><small>Base 100 · '+s.sessions+' sesiones</small></div><svg id="nav-chart" viewBox="0 0 760 290" role="img" aria-label="Curva de capital paper"></svg>'+
 (proxy?disclaimer("Proxy matemático: no se ha entrenado ni ejecutado el modelo externo de esta familia."):"")+'</article>'+
 '<aside class="panel"><div class="label">CARTERA PAPER</div><h3>'+esc(s.name)+'</h3>'+metric("Capital ficticio final",money(s.points.at(-1).equity))+metric("Costes teóricos",money(s.fees))+metric("Operaciones simuladas",String(s.orders.length))+
 '<div class="minor-heading">Exposición al último cierre</div>'+Object.keys(state.data.market).map((k,i)=>'<div class="bar-label"><span>'+esc(k)+'</span><strong>'+fmt(s.weights[i]*100)+' %</strong></div><div class="exposure-bar"><i style="width:'+Math.max(0,Math.min(100,s.weights[i]*100))+'%"></i></div>').join("")+
 '<p class="small-note">Coste asumido: '+fmt(s.cost_bps)+' puntos básicos por unidad negociada. Sin conexión a ningún broker.</p>'+button("Diario de órdenes","journal",s.id,"outline-btn")+'</aside></div>';
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
function theses(){
 const t=valuation(state.data.theses.find(x=>x.id===state.thesis)||state.data.theses[0]);
 return head("TESIS · SEGUIMIENTO","Hipótesis, escenarios y valoraciones","Cada tesis cuenta con condiciones de refutación, escenarios, supuestos y método. Se trata de entidades y cifras inventadas.")+
 '<div class="filters"><label>Buscar<input id="thesis-query" type="search" placeholder="Entidad o sector" value="'+esc(state.query)+'"></label><label>Ordenar<select id="thesis-sort">'+[["central","CAGR base"],["discountPct","Descuento"],["company","Nombre"],["price","Precio"]].map(([k,v])=>'<option value="'+esc(k)+'" '+(k===state.thesisSort?"selected":"")+'>'+esc(v)+'</option>').join("")+'</select></label>'+button("Exportar CSV","export","theses","outline-btn")+'</div>'+
 '<div class="table-scroll"><table><thead><tr><th>Entidad</th><th>Método</th><th>Estado</th><th class="number">Precio</th><th class="number">Valor base</th><th class="number">CAGR</th><th class="number">Descuento</th><th>Ficha</th></tr></thead><tbody id="thesis-rows">'+thesisTableRows()+'</tbody></table></div>'+
 head("ANÁLISIS","Ficha de tesis","Comparación de supuestos y criterios falsables.")+thesisDetail(t)+
 disclaimer("Ninguna ficha procede de una watchlist personal, trabajo académico o firma de análisis externa.");
}
function monitoring(){
 const s=active();
 return head("SEGUIMIENTO","Diario paper y salud de fuentes","Se conservan operaciones hipotéticas, reglas de costes y ausencia de fuentes verificadas. No existe conectividad con cuentas reales.")+
 '<div class="section-grid three">'+card('<span class="label">PROCEDENCIA</span><h3>Datos sintéticos</h3><p>Tres activos ficticios. Ningún proveedor de cotizaciones.</p>')+
 card('<span class="label">COTIZACIONES AUSENTES</span><h3>0 en el ejemplo</h3><p>Si un precio es inválido, la simulación no fabrica un fill ni un NAV.</p>')+
 card('<span class="label">ESTADO FINANCIERO</span><h3>Sin operaciones reales</h3><p>Solo operaciones paper calculadas en el navegador.</p>')+'</div>'+
 head("OPERACIONES","Diario de órdenes simuladas","El libro de órdenes documenta compra o venta, unidades, referencia y coste por sesión.")+
 '<div class="filters"><label>Algoritmo<select id="journal-select">'+all().map(x=>'<option value="'+esc(x.id)+'" '+(x.id===state.strategy?"selected":"")+'>'+esc(x.name)+'</option>').join("")+'</select></label>'+button("Exportar diario CSV","export","journal","outline-btn")+'</div>'+
 '<div class="metric-strip spaced">'+metric("Órdenes",String(s.orders.length))+metric("Valor final",money(s.points.at(-1).equity))+metric("Costes",money(s.fees))+metric("Cobertura","100 %")+'</div>'+
 '<div class="table-scroll"><table><thead><tr><th>Sesión</th><th>Activo</th><th>Acción</th><th class="number">Referencia</th><th class="number">Unidades</th><th class="number">Nocional</th><th class="number">Coste</th><th>Tipo</th></tr></thead><tbody>'+s.orders.slice(-30).reverse().map(x=>'<tr><td>'+esc(x.session)+'</td><td>'+esc(x.symbol)+'</td><td>'+esc(x.action)+'</td><td class="number">'+money(x.referencePrice)+'</td><td class="number">'+fmt(x.units)+'</td><td class="number">'+money(x.notional)+'</td><td class="number">'+money(x.cost)+'</td><td>PAPER</td></tr>').join("")+'</tbody></table></div>'+
 disclaimer("Últimas 30 operaciones mostradas; la exportación incluye todo el diario. Ninguna ejecución se origina en una cuenta personal.");
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
 const pages={overview,competition,algorithms,theses,monitoring,methodology};
 document.querySelectorAll(".product-tabs [data-view]").forEach(b=>{const active=b.dataset.view===state.view;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
 $("app").innerHTML=(pages[state.view]||overview)();chart();
}
function go(view){if(!viewNames.includes(view))return;state.view=view;const u=new URL(location.href);u.searchParams.set("view",view);history.pushState({view},"",u);render();window.scrollTo({top:0,behavior:"auto"});}
const asCSV=rows=>rows.map(row=>row.map(x=>'"'+String(x??"").replaceAll('"','""')+'"').join(",")).join("\n");
function download(name,rows){const u=URL.createObjectURL(new Blob(["\ufeff"+asCSV(rows)],{type:"text/csv;charset=utf-8"}));const a=document.createElement("a");a.href=u;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(u);}
function exportData(what){
 if(what==="ranking"){download("midas-ranking-sintetico.csv",[["algoritmo","familia","retorno_pct","drawdown_pct","volatilidad_pct","sharpe","coste"],...rank(state.data,state.sort,state.asc,state.group).map(x=>[x.name,x.group,x.returnPct,x.drawdownPct,x.volatilityPct,x.sharpe,x.fees])]);}
 if(what==="journal"){download("midas-diario-sintetico.csv",[["sesion","activo","accion","precio","unidades","nocional","coste"],...active().orders.map(x=>[x.session,x.symbol,x.action,x.referencePrice,x.units,x.notional,x.cost])]);}
 if(what==="theses"){download("midas-tesis-sinteticas.csv",[["entidad","sector","metodo","estado","cagr_central","valor_bajista","valor_central","valor_alcista"],...thesisRank(state.data).map(x=>[x.company,x.sector,x.method,x.status,x.central,x.valuation.bear.fair,x.valuation.base.fair,x.valuation.bull.fair])]);}
}
$("app").addEventListener("click",e=>{
 const b=e.target.closest("button[data-action]");if(!b)return;const {action,value}=b.dataset;
 if(action==="navigate")go(value);
 else if(action==="select"||action==="journal"){state.strategy=value;go(action==="journal"?"monitoring":"competition");}
 else if(action==="group"){state.group=value;go("competition");}
 else if(action==="thesis"){state.thesis=value;go("theses");}
 else if(action==="direction"){state.asc=!state.asc;render();}
 else if(action==="export")exportData(value);
});
$("app").addEventListener("change",e=>{
 const el=e.target;
 if(el.id==="group-select"){state.group=el.value;render();}
 if(el.id==="rank-select"){state.sort=el.value;render();}
 if(el.id==="thesis-sort"){state.thesisSort=el.value;render();}
 if(el.id==="journal-select"){state.strategy=el.value;render();}
});
$("app").addEventListener("input",e=>{
 if(e.target.id==="thesis-query"){state.query=e.target.value;const tbody=$("thesis-rows");if(tbody)tbody.innerHTML=thesisTableRows();}
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
  const r=await fetch("./data/demo.json",{cache:"no-store"});if(!r.ok)throw Error("Dataset missing");const data=await r.json();verify(data);
  state.data=data;const v=new URLSearchParams(location.search).get("view");state.view=viewNames.includes(v)?v:"overview";summary();render();
 }catch(e){$("app").textContent="No se ha podido cargar el registro sintético o no cumple el contrato de integridad.";}
}
init();
