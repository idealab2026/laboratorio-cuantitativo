// Read-only audit UI. No unrecorded fills, reasons or quote history are invented.
const esc=s=>String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
const num=v=>typeof v==="number"&&Number.isFinite(v);
const day=v=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v);
const stamp=v=>Date.parse(v+"T00:00:00Z");
const fmt=v=>num(v)?new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:3}).format(v):"No verificable";
const safePath=v=>v===null||typeof v==="string"&&v.length<170&&!/https?:|[<>@]|\.\./.test(v);
export function verifyOperationsAudit(doc){
 if(doc?.schema!=="midas_operations_audit_v1"||doc.purpose!=="read_only_paper_decision_evidence"||
    !doc.tracks||Object.keys(doc.tracks).length!==64||!day(doc.asof))
  throw Error("Contrato de historial de operaciones incorrecto");
 for(let n=1;n<=64;n++){
  const id="IL-"+String(n).padStart(3,"0"),t=doc.tracks[id];
  if(!t||!["partial_executions_documented","nav_only_or_no_actions","no_executed_actions_documented"].includes(t.status)||
      !Array.isArray(t.sessions)||!t.prices||!safePath(t.source_path)||
      ![null,"EUR","USD"].includes(t.currency)||
      t.source_sha256!==null&&!/^[a-f0-9]{64}$/.test(t.source_sha256))
   throw Error("Libro paper no verificable");
  let previous="";
  for(const session of t.sessions){
   if(!day(session.date)||session.date<=previous||!Array.isArray(session.actions)||session.actions.length>2000)
    throw Error("Secuencia de sesiones inválida");
   previous=session.date;
   for(const a of session.actions){
    if(!/^[A-Z0-9][A-Z0-9.-]{0,13}$/.test(a.ticker||"")||
       !["buy","sell","hold"].includes(a.side)||
       !["recorded","not_recorded","inferred_position_continuity"].includes(a.reason_basis)||
       typeof a.reason!=="string"||a.reason.length>1000||!safePath(a.evidence)||
       a.price!==null&&(!num(a.price)||a.price<=0)||
       a.quantity!==null&&(!num(a.quantity)||a.quantity<=0)||
       a.signal_date!==null&&!day(a.signal_date))
     throw Error("Fila de operación inválida");
    if(a.side==="hold"&&(a.price!==null||a.reason_basis!=="inferred_position_continuity"))
     throw Error("Mantenimiento atribuido como una orden");
   }
  }
  for(const [ticker,quotes] of Object.entries(t.prices)){
   if(!/^[A-Z0-9][A-Z0-9.-]{0,13}$/.test(ticker)||!Array.isArray(quotes)||quotes.length>1000||
      t.currency!=="USD"&&quotes.length)throw Error("Cotizaciones de divisa incompatible");
   for(const q of quotes)
    if(!day(q.date)||!num(q.price)||q.price<=0||q.source!=="dated_market_close"||
      !/^[a-f0-9]{64}$/.test(q.snapshot_sha256))throw Error("Cotización sin prueba");
  }
 }
 return {count:64,withExecution:Object.values(doc.tracks).filter(t=>t.status==="partial_executions_documented").length};
}
function chart(track,ticker){
 const quote=(track.prices[ticker]||[]).map(q=>({date:q.date,price:q.price,kind:"close"}));
 const trades=track.sessions.flatMap(s=>s.actions.filter(a=>a.ticker===ticker&&
  (a.side==="buy"||a.side==="sell")&&num(a.price)).map(a=>({date:s.date,price:a.price,kind:a.side})));
 const all=[...quote,...trades];
 if(!all.length)return '<p class="audit-method-note">No existen precios de ejecución o cierres verificables para este activo. No se inventa una curva histórica.</p>';
 const D=all.map(p=>stamp(p.date)),P=all.map(p=>p.price),d0=Math.min(...D),d1=Math.max(...D);
 const p0=Math.min(...P),p1=Math.max(...P),spread=Math.max(p1-p0,p1*.02,.1);
 const lo=p0-spread*.18,hi=p1+spread*.18;
 const x=date=>60+810*(stamp(date)-d0)/Math.max(86400000,d1-d0);
 const y=p=>220-165*(p-lo)/(hi-lo);
 const n=v=>Number(v.toFixed(2));
 let lines="",group=[];
 for(const q of quote.slice().sort((a,b)=>a.date.localeCompare(b.date))){
  if(group.length&&stamp(q.date)-stamp(group.at(-1).date)>4*86400000){
   if(group.length>1)lines+='<polyline class="audit-price-line" points="'+group.map(v=>n(x(v.date))+","+n(y(v.price))).join(" ")+'"/>';
   group=[];
  }
  group.push(q);
 }
 if(group.length>1)lines+='<polyline class="audit-price-line" points="'+group.map(v=>n(x(v.date))+","+n(y(v.price))).join(" ")+'"/>';
 const closeDots=quote.map(q=>'<circle class="audit-close-dot" cx="'+n(x(q.date))+'" cy="'+n(y(q.price))+
   '" r="3"><title>Cierre '+esc(q.date)+': '+fmt(q.price)+'</title></circle>').join("");
 const markers=trades.map(p=>{
  const cx=n(x(p.date)),cy=n(y(p.price));
  return '<circle class="'+(p.kind==="buy"?"audit-buy-dot":"audit-sell-dot")+'" cx="'+cx+'" cy="'+cy+
   '" r="6" stroke="#fff" stroke-width="1.5"><title>'+esc(p.date)+' '+(p.kind==="buy"?"Compra":"Venta")+
   ' a '+fmt(p.price)+'</title></circle><text class="audit-trade-symbol" x="'+cx+'" y="'+(cy-12)+
   '" text-anchor="middle">'+(p.kind==="buy"?"C":"V")+'</text>';
 }).join("");
 const start=new Date(d0).toISOString().slice(0,10),end=new Date(d1).toISOString().slice(0,10);
 const currency=esc(track.currency||"divisa sin verificar");
 return '<svg viewBox="0 0 920 270" class="audit-price-chart" role="img" aria-label="Fechas y precios observados de '+esc(ticker)+' con puntos de compra y venta">'+
  '<title>'+esc(ticker)+' · precios, compras y ventas paper</title>'+
  '<line x1="60" y1="220" x2="870" y2="220" class="audit-axis"/>'+
  '<line x1="60" y1="33" x2="60" y2="220" class="audit-axis"/>'+
  '<text x="54" y="38" text-anchor="end" class="audit-axis-label">'+fmt(hi)+'</text>'+
  '<text x="54" y="220" text-anchor="end" class="audit-axis-label">'+fmt(lo)+'</text>'+
  '<text x="60" y="247" class="audit-axis-label">'+esc(start)+'</text>'+
  '<text x="870" y="247" text-anchor="end" class="audit-axis-label">'+esc(end)+'</text>'+
  '<text x="870" y="27" text-anchor="end" class="audit-axis-label">Precio ('+currency+')</text>'+
  lines+closeDots+markers+'</svg>'+
  '<div class="audit-legend"><span class="audit-legend-buy">● Compras</span><span class="audit-legend-sell">● Ventas</span><span class="audit-legend-close">● Precio de cierre del mercado (no es una operación)</span></div>'+
  '<p class="audit-method-note">Las abscisas son fechas de sesión y las ordenadas son precios en '+currency+
  '. Los puntos azules son cierres observados de mercado, NO compras ni ventas del algoritmo. Solo se unen cierres consecutivos realmente guardados; no se interpolan fechas sin cotización. No consta la hora exacta de los fills. '+
  (quote.length<2?'No existe una serie de cierres suficiente para mostrar una trayectoria continua.':'')+'</p>';
}
export function renderOperationsAudit(doc,id,selectedTicker=null){
 const heading='<section class="algorithm-section audit-section" id="operations-audit"><h3>Operaciones por sesión y motivos</h3>';
 if(!doc)return heading+'<p>Cargando el historial verificado de órdenes…</p></section>';
 const track=doc.tracks[id];
 if(!track)return heading+'<p>Esta estrategia carece de registro individual de operaciones verificable.</p></section>';
 const sessions=track.sessions;
 const symbols=[...new Set(sessions.flatMap(s=>s.actions.map(a=>a.ticker)))].sort();
 const chosen=symbols.includes(selectedTicker)?selectedTicker:
  symbols.find(t=>sessions.some(s=>s.actions.some(a=>a.ticker===t&&a.side!=="hold")))||symbols[0];
 const totals=sessions.reduce((out,s)=>{for(const a of s.actions)out[a.side]++;return out},{buy:0,sell:0,hold:0});
 const intro=heading+
  '<p>Consulta las compras y ventas paper ejecutadas y las posiciones que continuaron abiertas. Los mantenimientos son una <strong>inferencia contable</strong>; no equivalen a una decisión explícita registrada. Un motivo sin documentar aparece como tal.</p>'+
  '<div class="audit-counts"><span>'+sessions.length+' sesiones</span><span>'+totals.buy+' compras</span>'+
  '<span>'+totals.sell+' ventas</span><span>'+totals.hold+' mantenimientos inferidos</span></div>';
 const graph=symbols.length?
  '<div class="audit-chart-area"><h4>Precio histórico del activo y ejecuciones</h4>'+
  '<label class="audit-ticker-picker">Acción <select id="audit-ticker" aria-label="Elegir ticker del gráfico">'+
  symbols.map(t=>'<option value="'+esc(t)+'"'+(t===chosen?' selected':'')+'>'+esc(t)+'</option>').join("")+'</select></label>'+
  chart(track,chosen)+'</div>':
  '<p class="audit-method-note">Los NAV globales no bastan para reconstruir operaciones. No se publican compras o ventas sin evidencias individuales.</p>';
 const rows=sessions.slice().reverse().map((session,i)=>{
  const actions=session.actions||[];
  const date=esc(session.date),n=sessions.length-i;
  const body=actions.length?
   '<div class="table-scroll audit-table-wrap"><table class="table-compact audit-operation-table"><thead><tr>'+
   '<th>Acción</th><th>Activo</th><th>Precio</th><th>Unidades</th><th>Motivo y evidencia</th></tr></thead><tbody>'+
   actions.map(a=>{
    const kind={buy:"COMPRA",sell:"VENTA",hold:"MANTENER · INFERIDO"}[a.side];
    const evidence=a.reason_basis==="recorded"?"Motivo registrado":
     a.reason_basis==="inferred_position_continuity"?"Continuidad inferida del libro":"Motivo individual no registrado";
    return '<tr><td><strong class="audit-action audit-'+a.side+'">'+esc(kind)+'</strong></td>'+
     '<td>'+esc(a.ticker)+'</td><td>'+fmt(a.price)+'</td><td>'+fmt(a.quantity)+'</td>'+
     '<td>'+esc(a.reason)+'<small class="smallline">'+esc(evidence)+
     (a.signal_date?' · señal '+esc(a.signal_date):"")+' · '+esc(a.evidence)+'</small></td></tr>';
   }).join("")+'</tbody></table></div>':
   '<p>Sin órdenes ejecutadas ni posiciones reconstruibles documentadas en esta sesión. Esto no prueba que se decidiera mantener efectivo.</p>';
  return '<details class="audit-session"'+(i===0?' open':'')+'><summary>Sesión '+n+' · '+date+
   ' · '+actions.length+' acciones documentadas o inferidas</summary>'+body+'</details>';
 }).join("");
 return intro+graph+'<h4>Registro por sesión</h4>'+rows+
  '<p class="audit-method-note">Fuente: '+esc(track.source_path||"Sin libro identificado")+
  '. Huella SHA-256: '+esc(track.source_sha256||"No disponible")+
  '. Los históricos de algunas estrategias son parciales; no se reconstruyen señales u órdenes ausentes.</p></section>';
}
