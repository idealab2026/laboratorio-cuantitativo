// Reviewed institutional research preserves historical assumptions and dates.
const esc=x=>String(x??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
const num=v=>typeof v==="number"&&Number.isFinite(v);
const fmt=v=>v===null||!num(v)?"N/D":new Intl.NumberFormat("es-ES",{maximumFractionDigits:2,minimumFractionDigits:2}).format(v);
const percent=v=>num(v)?(v>0?"+":"")+fmt(v)+" %":"N/D";
const money=(v,r)=>num(v)?fmt(v)+(r.currency?" "+esc(r.currency):""):"N/D";
const date=v=>typeof v==="string"&&(/^\d{4}-\d{2}-\d{2}$/.test(v)||v==="");
const TITLES=["ticker","company","theme","lastReview","studyDate","market","currency","priceDate","earningsRecord","thesisStatus","valuationStatus","summary","drivers","risks"];
const AMOUNTS=["recordedPrice","referencePrice","bearCagr","baseCagr","bullCagr","bearTarget","baseTarget","bullTarget","priceFor15"];
const PRIVATE=/(?:https?:\/\/|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|github_pat_|ghp_|refresh_token|private_key|iban)/i;
export function verifyPublicTheses(doc){
 if(!doc||doc.schema!=="midas_public_theses_v1"||
    !["independent_public_research_only","author_approved_public_research_snapshot"].includes(doc.data_class)||
    !date(doc.published_as_of)||!Array.isArray(doc.records)||doc.records.length>1000)
  throw Error("Catálogo publicado ausente o alterado");
 const ids=new Set();
 for(const r of doc.records){
  if(!r||Object.keys(r).sort().join("|")!==[...TITLES,...AMOUNTS].sort().join("|")||
     !/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/.test(r.ticker||"")||ids.has(r.ticker))
   throw Error("Identidad de tesis no válida");
  ids.add(r.ticker);
  for(const key of TITLES)
   if(r[key]!==null&&(typeof r[key]!=="string"||r[key].length>1100||PRIVATE.test(r[key])))
    throw Error("Contenido de ficha no autorizado");
  for(const key of ["lastReview","studyDate","priceDate"])
   if(!date(r[key]))throw Error("Fecha de ficha no válida");
  if(r.currency!==null&&!["USD","EUR","GBP","JPY"].includes(r.currency))
   throw Error("Divisa no admitida");
  for(const key of AMOUNTS)
   if(r[key]!==null&&(!num(r[key])||Math.abs(r[key])>1e9))
    throw Error("Cantidad fuera de contrato");
  for(const key of ["recordedPrice","referencePrice","bearTarget","baseTarget","bullTarget","priceFor15"])
   if(r[key]!==null&&r[key]<0)throw Error("Cotización negativa");
  if(r.recordedPrice!==null&&(!r.priceDate||!r.currency))
   throw Error("Precio histórico sin fecha o divisa");
 }
 return {count:doc.records.length,withCagr:doc.records.filter(r=>r.baseCagr!==null).length,withPrice:doc.records.filter(r=>r.recordedPrice!==null).length};
}

/* Only independently licensed, already-closed public quotes may replace the table's
   last-close column; historical thesis anchors are never recalculated here. */
export function verifyPublicCloseFeed(doc,allowedTickers,now=Date.now()){
 if(!doc||doc.schema!=="midas.public_closes.v1"||!Array.isArray(doc.quotes)||
    !["not_configured","verified"].includes(doc.status)||doc.quotes.length>1000)
  throw Error("Feed de cierres no válido");
 if(doc.status==="not_configured"){
  if(doc.quotes.length||doc.source!==null||doc.collected_at!==null)throw Error("Feed no habilitado con precios");
  return {status:"not_configured",quotes:new Map(),source:null};
 }
 const source=doc.source;
 if(!source||source.display_rights!=="confirmed_public_redistribution"||
    typeof source.name!=="string"||source.name.length<2||source.name.length>90||
    !/^https:\/\//.test(source.url||"")||/[@<>]/.test(source.url))
   throw Error("Derechos públicos o procedencia no acreditados");
 const stamp=Date.parse(doc.collected_at);
 if(!Number.isFinite(stamp)||stamp>now+60000||stamp<now-14*86400000)
   throw Error("Fecha de obtención de los cierres no válida");
 const quotes=new Map();
 const day=new Date(now).toISOString().slice(0,10);
 for(const q of doc.quotes){
  if(!q||typeof q.ticker!=="string"||!allowedTickers.has(q.ticker)||quotes.has(q.ticker)||
     !/^\d{4}-\d{2}-\d{2}$/.test(q.session)||q.session>day||
     !Number.isFinite(Date.parse(q.session+"T00:00:00Z"))||
     !Number.isFinite(q.close)||q.close<=0||q.close>1e9||
     !["USD","EUR","GBP","JPY"].includes(q.currency))
   throw Error("Cotización sin fecha, símbolo o valor admisibles");
  quotes.set(q.ticker,{close:q.close,currency:q.currency,session:q.session});
 }
 return {status:"verified",quotes,source,updatedAt:doc.collected_at};
}

function thesisValues(row,records,local){
 const i=row.issuer,r=records.get(i.ticker),l=local.get(i.ticker),s=row.screen;
 return {ticker:i.ticker,company:r?.company||i.company,market:r?.market||i.market,
  theme:r?.theme||i.sector,currency:r?.currency||i.currency,record:r,
  status:l?"Archivo local":r?r.valuationStatus||r.thesisStatus:s?"Screening exploratorio":"Sin tesis pública",
  date:l?l.date||"":r?r.studyDate:s?.asOf||"",
  price:l?null:r?r.recordedPrice:s?.quote.close??null,
  priceDate:l?l.date||"":r?r.priceDate:s?.quote.closeDate||"",
  reference:l?null:r?r.referencePrice:s?.quote.close??null,
  base:l?l.base??null:r?r.baseCagr:s?.scenarios.base.cagrPct??null,
  bear:l?l.bear??null:r?r.bearCagr:s?.scenarios.bear.cagrPct??null,
  bull:l?l.bull??null:r?r.bullCagr:s?.scenarios.bull.cagrPct??null,
  entry:l?null:r?r.priceFor15:s?.buyPrice15??null,
  target:l?null:r?r.baseTarget:s?.scenarios.base.target??null,
  earnings:r?.earningsRecord||null,report:r?.summary?"Sí":s?"Modelo exploratorio":null};
}
export function orderedThesisRows(rows,records,local,sort,ascending,verifiedCloses=new Map()){
 const values=new Map(rows.map(row=>{
  const values=thesisValues(row,records,local);
  if(sort==="price")values.price=verifiedCloses.get(row.issuer.ticker)?.close??null;
  return [row.issuer.ticker,values];
 }));
 const texts=new Set(["ticker","company","market","earnings","report"]);
 return rows.sort((a,b)=>{
  const x=values.get(a.issuer.ticker)[sort],y=values.get(b.issuer.ticker)[sort];
  const aNull=x===null||x===undefined||x==="",bNull=y===null||y===undefined||y==="";
  if(aNull!==bNull)return aNull?1:-1;
  const delta=aNull?0:texts.has(sort)?String(x).localeCompare(String(y),"es",{numeric:true}):x-y;
  return (ascending?delta:-delta)||a.issuer.ticker.localeCompare(b.issuer.ticker,"es");
 });
}
export function publicThesisTableRows(rows,records,local,selected,verifiedCloses=new Map()){
 return rows.map(row=>{
  const v=thesisValues(row,records,local);
  const q=verifiedCloses.get(v.ticker);
  const price=q?'<strong class="thesis-close">'+money(q.close,q)+'</strong><small class="thesis-quote-date">Cierre '+esc(q.session)+'</small>':
   '<span class="thesis-close">N/D</span><small class="thesis-quote-date">Sin cierre público verificado</small>';
  return '<tr class="interactive-table-row '+(selected===v.ticker?"is-selected":"")+'" data-issuer-id="'+esc(v.ticker)+'" tabindex="0">'+
   '<td><strong>'+esc(v.ticker)+'</strong></td><td><strong>'+esc(v.company)+'</strong><small class="smallline">'+esc(v.theme)+'</small></td>'+
   '<td>'+esc(v.market)+'</td><td class="number">'+price+'</td>'+
   '<td class="number">'+percent(v.bull)+'</td><td class="number">'+percent(v.bear)+'</td><td class="number">'+percent(v.base)+'</td>'+
   '<td class="number">'+money(v.entry,v)+'</td><td class="number">'+money(v.target,v)+'</td>'+
   '<td><span class="thesis-earnings" title="'+esc(v.earnings||"N/D")+'">'+esc(v.earnings||"N/D")+'</span></td>'+
   '<td><a class="smallbtn" href="./index.html?view=thesis&amp;ticker='+encodeURIComponent(v.ticker)+'" target="_blank" rel="noopener noreferrer" aria-label="Abrir análisis de '+esc(v.ticker)+' en nueva pestaña">'+(v.record?"Abrir análisis":row.screen?"Ver modelo":"Ver ficha")+'</a>'+
   '<small class="smallline" title="'+esc(v.status)+'">'+esc(v.status)+'</small></td></tr>';
 }).join("");
}
export function publicThesisDetail(r,l){
 const local=k=>l?.[k]??r[k+"Cagr"];
 const scenarios=["bear","base","bull"].map((key,index)=>
  '<div class="scenario-tile"><span class="label">'+["Bajista","Central","Alcista"][index]+'</span>'+
  '<strong>'+money(r[key+"Target"],r)+'</strong><span>CAGR '+percent(local(key))+'</span></div>').join("");
 return '<article class="panel"><div class="panel-top"><div><span class="label">'+esc(r.ticker)+' · '+esc(r.market||"Mercado sin verificar")+'</span><h3>'+esc(r.company)+'</h3></div>'+
  '<span class="status-chip">Ficha pública · '+esc(r.valuationStatus||"Pendiente")+'</span></div>'+
  '<p>'+esc(r.theme)+'</p><div class="metric-strip">'+
  '<div class="metric"><span>CAGR central 2031</span><strong>'+percent(local("base"))+'</strong></div>'+
  '<div class="metric"><span>Precio registrado</span><strong>'+money(r.recordedPrice,r)+'</strong><small>'+esc(r.priceDate||"Sin fecha")+'</small></div>'+
  '<div class="metric"><span>Precio referencia estudio</span><strong>'+money(r.referencePrice,r)+'</strong></div>'+
  '<div class="metric"><span>Precio para generar 15 % anual</span><strong>'+money(r.priceFor15,r)+'</strong></div></div>'+
  '<p><strong>Estado de la tesis:</strong> '+esc(r.thesisStatus)+' · <strong>Revisión:</strong> '+esc(r.lastReview||"N/D")+' · <strong>Fecha del escenario:</strong> '+esc(r.studyDate||"N/D")+'</p>'+
  '<h3>Resumen del análisis</h3><p>'+esc(r.summary||"Sin resumen")+'</p></article>'+
  '<article class="panel"><h3>Escenarios documentados a 2031</h3><div class="scenario-grid">'+scenarios+'</div>'+
  (r.drivers?'<h3>Hipótesis y catalizadores</h3><p>'+esc(r.drivers)+'</p>':"")+
  (r.risks?'<h3>Riesgos</h3><p>'+esc(r.risks)+'</p>':"")+
  '<p><strong>Resultados (registro documental):</strong> '+esc(r.earningsRecord||"No documentados")+'</p>'+
  '<p class="small-note">Esta vista es un extracto de la tesis original. El informe ejecutivo completo, con sus gráficas y anexos, todavía no está incorporado a esta web. CAGR, hipótesis y precios conservan sus fechas históricas; no hay actualización bursátil en tiempo real.</p></article>';
}
export function publicThesisCsv(rows,records,local){
 return [["ticker","empresa","mercado","precio_registrado","fecha_precio","divisa","precio_referencia_estudio","bull_2031_cagr","bear_2031_cagr","central_2031_cagr","precio_15pct","objetivo_central_2031","estado","fecha_estudio","resultados_registrados"],
  ...rows.map(row=>{const v=thesisValues(row,records,local);
   return [v.ticker,v.company,v.market,v.price??"N/D",v.priceDate||"N/D",v.currency||"N/D",v.reference??"N/D",v.bull??"N/D",v.bear??"N/D",v.base??"N/D",v.entry??"N/D",v.target??"N/D",v.status,v.date||"N/D",v.earnings||"N/D"];
  })];
}

export function publicResearchRows(catalogRows,records,{query="",sort="base",ascending=false}={}){
 const all=new Map(catalogRows.map(row=>[row.issuer.ticker,row]));
 for(const r of records.values())if(!all.has(r.ticker))all.set(r.ticker,{issuer:{ticker:r.ticker,company:r.company,market:r.market,currency:r.currency,sector:r.theme},screen:null});
 const q=String(query).trim().toLocaleLowerCase("es");
 return orderedThesisRows([...all.values()].filter(row=>{const r=records.get(row.issuer.ticker);return !q||[row.issuer.ticker,r?.company||row.issuer.company,r?.theme||row.issuer.sector].some(x=>String(x||"").toLocaleLowerCase("es").includes(q));}),records,new Map(),sort,ascending);
}
