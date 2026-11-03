// Read-only audit UI. No unrecorded fills, reasons or quote history are invented.
const esc=s=>String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
const num=v=>typeof v==="number"&&Number.isFinite(v);
const day=v=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v);
const stamp=v=>Date.parse(v+"T00:00:00Z");
const fmt=v=>num(v)?new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:3}).format(v):"No verificable";
const fmtUnits=v=>num(v)?new Intl.NumberFormat("es-ES",{maximumFractionDigits:6}).format(v):"No verificable";
function valueCell(a,currency){
 const unit=esc(currency||"");
 if(a.side==="corporate_action")return '<span class="audit-corporate-note">Conversión corporativa; no hubo precio de compraventa</span>';
 if(num(a.price))return '<span class="audit-price-execution">'+esc(fmt(a.price))+' '+unit+
  '<small class="smallline">'+
  (a.price_basis==="corporate_original_entry"?"Precio de compra original acreditado por la conversión":
   a.price_basis==="trade_entry_cost_derived"?"Precio reconstruido: coste registrado / unidades / (1 + comisión)":
   a.price_basis==="trade_net_proceeds_derived"?"Precio reconstruido: cobro registrado / unidades / (1 − comisión)":
   a.price_basis==="position_entry"?"Precio de entrada conservado de la posición":
   "Precio de ejecución conservado")+'</small></span>';
 if(num(a.reference_close))return '<span class="audit-price-market">'+esc(fmt(a.reference_close))+' '+unit+
  '<small class="smallline">Cierre de mercado de esta sesión (no es precio de orden)</small></span>';
 if(num(a.entry_price))return '<span class="audit-price-entry">'+esc(fmt(a.entry_price))+' '+unit+
  '<small class="smallline">Precio de entrada ('+esc(a.entry_date||"")+
  '). No es un cierre de esta sesión</small></span>';
 return '<span class="audit-missing-source">No se conserva el precio de esta sesión</span>';
}
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
       !["buy","sell","hold","corporate_action"].includes(a.side)||
       !["recorded","not_recorded","inferred_position_continuity","engine_rule"].includes(a.reason_basis)||
       typeof a.reason!=="string"||a.reason.length>1000||!safePath(a.evidence)||
       a.price!==null&&(!num(a.price)||a.price<=0)||
       a.quantity!==null&&(!num(a.quantity)||a.quantity<=0)||
       a.signal_date!==null&&!day(a.signal_date)||
       a.entry_price!==undefined&&a.entry_price!==null&&(!num(a.entry_price)||a.entry_price<=0)||
       a.entry_date!==undefined&&!day(a.entry_date)||
       a.reference_close!==undefined&&(!num(a.reference_close)||a.reference_close<=0)||
       a.reference_sha256!==undefined&&!/^[a-f0-9]{64}$/.test(a.reference_sha256)||
       a.rule_source!==undefined&&a.rule_source!=="classic_sp500/run.py"||
       a.price_basis!==undefined&&
        !["book_fill","position_entry","corporate_original_entry","trade_entry_cost_derived",
          "trade_net_proceeds_derived","not_recorded","not_applicable"].includes(a.price_basis))
     throw Error("Fila de operación inválida");
    if(a.side==="hold"&&(a.price!==null||a.reason_basis!=="inferred_position_continuity"))
     throw Error("Mantenimiento atribuido como una orden");
    if(a.side==="corporate_action"&&(
      a.price!==null||a.price_basis!=="not_applicable"||
      !/^[A-Z0-9][A-Z0-9.-]{0,13}$/.test(a.successor_ticker||"")||
      !num(a.successor_quantity)||a.successor_quantity<=0||
      !num(a.receivable_cash)||a.receivable_cash<0||
      typeof a.recorded_at_utc!=="string"||!a.recorded_at_utc.endsWith("+00:00")||
      typeof a.action_id!=="string"||a.action_id.length>100))
     throw Error("Conversión corporativa sin procedencia verificada");
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
/**
 * Position a visible price label above EVERY documented market close and fill.
 * Executed trades receive priority; collisions are staggered vertically and
 * then horizontally. All layout coordinates are within the SVG viewBox.
 * No price values are modified or inferred.
 */
export function layoutAuditPriceLabels(points){
 const prioritized=[...points].sort((a,b)=>
  Number(b.kind!=="close")-Number(a.kind!=="close")||
  a.x-b.x||a.y-b.y);
 const placed=[];
 for(const point of prioritized){
  const value=fmt(point.price);
  const text=point.kind==="buy"?"Compra "+value:
   point.kind==="sell"?"Venta "+value:value;
  const width=text.length*(point.kind==="close"?6.4:6.75)+5;
  let selected=null;
  for(const dx of [0,16,-16,36,-36,65,-65,95,-95]){
   for(let level=0;level<7;level++){
    const y=point.y-12-level*15;
    if(y<43)continue;
    const desiredX=point.x+(point.x<120?9:point.x>810?-9:0)+dx;
    const anchor=point.x<120?"start":point.x>810?"end":"middle";
    const x=Math.max(anchor==="start"?55:anchor==="end"?55+width:55+width/2,
      Math.min(anchor==="start"?884-width:anchor==="end"?884:884-width/2,desiredX));
    const left=anchor==="start"?x:anchor==="end"?x-width:x-width/2;
    const rect={left,right:left+width,top:y-12,bottom:y+3};
    const overlaps=placed.some(p=>rect.left<p.rect.right+4&&rect.right>p.rect.left-4&&
       rect.top<p.rect.bottom+3&&rect.bottom>p.rect.top-3);
    if(!overlaps){selected={x,y,anchor,rect};break;}
   }
   if(selected)break;
  }
  if(!selected){
   // Dense overlaps remain explicit; avoid dropping a documented point.
   const x=Math.max(55+width/2,Math.min(884-width/2,point.x));
   selected={x,y:Math.max(43,point.y-12),anchor:"middle",
    rect:{left:x-width/2,right:x+width/2,top:point.y-24,bottom:point.y-9}};
  }
  placed.push({...selected,kind:point.kind,text,date:point.date,price:point.price});
 }
 return placed;
}
function chart(track,ticker){
 const quote=(track.prices[ticker]||[]).map(q=>({date:q.date,price:q.price,kind:"close"}));
 const trades=track.sessions.flatMap(s=>s.actions.filter(a=>a.ticker===ticker&&
  (a.side==="buy"||a.side==="sell")&&num(a.price)).map(a=>({date:s.date,price:a.price,kind:a.side})));
 const other=track.sessions.flatMap(session=>session.actions.filter(a=>a.ticker===ticker&&
  (a.side==="corporate_action"||
   (a.side==="buy"||a.side==="sell")&&!num(a.price)))
  .map(a=>({date:session.date,kind:a.side,price:null,successor:a.successor_ticker})));
 const all=[...quote,...trades];
 const dated=[...all,...other];
 if(!dated.length)return '<p class="audit-method-note">No existen ejecuciones o cierres con fecha para este activo.</p>';
 const D=dated.map(p=>stamp(p.date)),P=all.map(p=>p.price),d0=Math.min(...D),d1=Math.max(...D);
 if(!P.length){
  const min=60,max=870,range=Math.max(d1-d0,86400000);
  return '<div class="audit-standalone-timeline"><p>Las operaciones tienen fecha, pero no un precio de ejecución o cierre conservado. Sus marcadores se sitúan únicamente sobre el eje temporal.</p>'+
   '<svg viewBox="0 0 920 130" class="audit-price-chart" role="img" aria-label="Operaciones con fecha y precio no conservado">'+
   '<line class="audit-axis" x1="60" x2="870" y1="95" y2="95"/>'+
   other.map(p=>'<g><line class="audit-undocumented-guide" x1="'+(min+(stamp(p.date)-d0)/range*(max-min))+
   '" x2="'+(min+(stamp(p.date)-d0)/range*(max-min))+'" y1="52" y2="95"/>'+
   '<text x="'+(min+(stamp(p.date)-d0)/range*(max-min))+'" y="44" class="audit-gap-label" text-anchor="middle">'+
   (p.kind==="buy"?"Compra":p.kind==="sell"?"Venta":"Conversión")+' sin precio de mercado</text></g>').join("")+
   '</svg></div>';
 }

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
 const firstTrade=[...trades,...other.filter(p=>p.kind==="buy"||p.kind==="sell")].length?Math.min(...[...trades,...other.filter(p=>p.kind==="buy"||p.kind==="sell")].map(p=>stamp(p.date))):null;
 const firstClose=quote.length?Math.min(...quote.map(p=>stamp(p.date))):null;
 const gapDays=firstTrade!==null&&firstClose!==null?
  Math.round((firstClose-firstTrade)/86400000):0;
 const gapHighlight=gapDays>=5?
  '<rect class="audit-unobserved-gap" x="'+n(x(new Date(firstTrade).toISOString().slice(0,10)))+
  '" y="34" width="'+n(x(new Date(firstClose).toISOString().slice(0,10))-
   x(new Date(firstTrade).toISOString().slice(0,10)))+'" height="186"/>'+
  '<text class="audit-gap-label" x="'+n((x(new Date(firstTrade).toISOString().slice(0,10))+
   x(new Date(firstClose).toISOString().slice(0,10)))/2)+
  '" y="61" text-anchor="middle">Sin cierres de mercado archivados</text>':"";
 const tradeGuides=trades.map(p=>'<line class="'+(p.kind==="buy"?"audit-buy-guide":"audit-sell-guide")+
  '" x1="'+n(x(p.date))+'" y1="'+n(y(p.price)+8)+'" x2="'+n(x(p.date))+'" y2="220">'+
  '<title>'+esc(p.date)+' '+(p.kind==="buy"?"Compra":"Venta")+' a '+esc(fmt(p.price))+'</title></line>').join("");
 const undatedPrices=other.filter(p=>p.kind==="buy"||p.kind==="sell").map(p=>{
  const cx=n(x(p.date));
  return '<g class="audit-undocumented-operation"><line class="audit-undocumented-guide" x1="'+cx+
   '" x2="'+cx+'" y1="72" y2="220"/><circle class="'+(p.kind==="buy"?"audit-buy-undocumented":"audit-sell-undocumented")+
   '" cx="'+cx+'" cy="72" r="6"><title>'+esc(p.date)+' '+(p.kind==="buy"?"Compra":"Venta")+
   ': operación documentada sin precio de ejecución verificable</title></circle>'+
   '<text class="audit-unpriced-label" x="'+cx+'" y="58" text-anchor="'+(cx>790?"end":cx<140?"start":"middle")+
   '">'+(p.kind==="buy"?"Compra":"Venta")+' · precio no registrado</text></g>';
 }).join("");
 const corporateAnnotations=other.filter(p=>p.kind==="corporate_action").map(p=>{
  const cx=n(x(p.date));
  return '<g class="audit-corporate-marker"><line x1="'+cx+'" x2="'+cx+'" y1="80" y2="220" class="audit-corporate-guide"/>'+
   '<text x="'+cx+'" y="72" text-anchor="'+(cx>790?"end":"middle")+'" class="audit-corporate-label">'+
   'Conversión → '+esc(p.successor||"sucesora")+'</text>'+
   '<title>'+esc(p.date)+' · conversión corporativa, sin compraventa</title></g>';
 }).join("");
 const closeDots=quote.map(q=>'<circle class="audit-close-dot" cx="'+n(x(q.date))+'" cy="'+n(y(q.price))+
   '" r="3.5"><title>Cierre '+esc(q.date)+': '+fmt(q.price)+'</title></circle>').join("");
 const markers=trades.map(p=>{
  const cx=n(x(p.date)),cy=n(y(p.price));
  return '<circle class="'+(p.kind==="buy"?"audit-buy-dot":"audit-sell-dot")+'" cx="'+cx+'" cy="'+cy+
   '" r="7" stroke="#fff" stroke-width="1.5"><title>'+esc(p.date)+' '+(p.kind==="buy"?"Compra":"Venta")+
   ' a '+fmt(p.price)+'</title></circle>';
 }).join("");
 const labels=layoutAuditPriceLabels([...trades,...quote].map(p=>({
  date:p.date,kind:p.kind,price:p.price,x:n(x(p.date)),y:n(y(p.price))
 }))).map(a=>'<text class="audit-point-price audit-price-'+a.kind+
   '" x="'+n(a.x)+'" y="'+n(a.y)+'" text-anchor="'+a.anchor+'">'+esc(a.text)+'</text>').join("");
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
  gapHighlight+lines+tradeGuides+corporateAnnotations+undatedPrices+closeDots+markers+labels+'</svg>'+
  '<div class="audit-legend"><span class="audit-legend-buy">● Compras</span><span class="audit-legend-sell">● Ventas</span><span class="audit-legend-close">● Precio de cierre del mercado (no es una operación)</span><span class="audit-legend-corporate">│ Conversión corporativa, no venta</span></div>'+
  '<p class="audit-method-note">Las abscisas son fechas de sesión y las ordenadas son precios en '+currency+
  '. Los precios aparecen sobre cada punto. Los puntos azules son cierres observados de mercado, NO compras ni ventas del algoritmo. La compra verde está colocada en su fecha y precio reales; el área sombreada indica un periodo sin cierres archivados, no un movimiento supuesto. Si no hay punto rojo, no consta una venta ejecutada con precio confirmado en estas sesiones; un evento corporativo puede transformar la posición sin ser una venta. Las operaciones sin precio se señalan por su fecha, sin inventar su cotización. Solo se unen cierres consecutivos realmente guardados; no se interpolan fechas sin cotización. No consta la hora exacta de los fills. '+
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
 const totals=sessions.reduce((out,s)=>{for(const a of s.actions)out[a.side]++;return out},{buy:0,sell:0,hold:0,corporate_action:0});
 const missingExecutionPrices=sessions.reduce((n,session)=>n+session.actions.filter(a=>
  (a.side==="buy"||a.side==="sell")&&!num(a.price)).length,0);
 const intro=heading+
  '<p>Consulta las compras y ventas paper ejecutadas y las posiciones que continuaron abiertas. Los mantenimientos son una <strong>inferencia contable</strong>; no equivalen a una decisión explícita registrada. Cuando el libro no guarda la señal individual, se describe la regla acreditada del motor y se diferencia de una decisión histórica comprobada.</p>'+
  '<div class="audit-counts"><span>'+sessions.length+' sesiones</span><span>'+totals.buy+' compras</span>'+
  '<span>'+totals.sell+' ventas</span><span>'+totals.hold+' mantenimientos inferidos</span>'+
  (totals.corporate_action?'<span>'+totals.corporate_action+' conversiones corporativas (no ventas)</span>':"")+
  (missingExecutionPrices?'<span class="audit-warning">'+missingExecutionPrices+
   ' ejecuciones sin precio original trazable (marcadas por fecha)</span>':"")+
  '</div>';
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
   '<th>Acción</th><th>Activo</th><th>Precio / referencia</th><th>Unidades</th><th>Motivo y evidencia</th></tr></thead><tbody>'+
   actions.map(a=>{
    const kind={buy:"COMPRA",sell:"VENTA",hold:"MANTENER · INFERIDO",
     corporate_action:"CONVERSIÓN CORPORATIVA"}[a.side];
    const evidence=a.side==="corporate_action"?
      "Transformación societaria acreditada; NO es una compraventa ni mantenimiento de la acción anterior":
     a.reason_basis==="recorded"?"Motivo guardado en libro de órdenes":
     a.reason_basis==="engine_rule"?"Regla acreditada por código; indicador individual no archivado":
     a.reason_basis==="inferred_position_continuity"?"Posición y unidades reconstruidas de ejecuciones; regla explicada cuando existe":
     "Sin motivo individual conservado";
    return '<tr><td><strong class="audit-action audit-'+a.side+'">'+esc(kind)+'</strong></td>'+
     '<td>'+esc(a.ticker)+(a.side==="corporate_action"?' → '+esc(a.successor_ticker):"")+
     '</td><td>'+valueCell(a,track.currency)+'</td><td>'+fmtUnits(a.quantity)+'</td>'+
     '<td>'+esc(a.reason)+(a.side==="corporate_action"?'<small class="smallline">Derecho societario: '+
       fmtUnits(a.successor_quantity)+' '+esc(a.successor_ticker)+' + '+
       fmt(a.receivable_cash)+' '+esc(track.currency||"")+
       ' de cobro pendiente. Registrado: '+esc(a.recorded_at_utc)+
       '. Sin ejecución de compra o venta.</small>':"")+
     '<small class="smallline">'+esc(evidence)+
     (a.signal_date?' · señal '+esc(a.signal_date):"")+
     (a.rule_source?' · regla: '+esc(a.rule_source):"")+' · libro: '+esc(a.evidence)+'</small></td></tr>';
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
