// Public, author-approved historical thesis extract. No private Google links.
const esc=x=>String(x??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
const num=v=>typeof v==="number"&&Number.isFinite(v);
const fmt=v=>v===null||!num(v)?"N/D":new Intl.NumberFormat("es-ES",{maximumFractionDigits:2,minimumFractionDigits:2}).format(v);
const percent=v=>num(v)?(v>0?"+":"")+fmt(v)+" %":"N/D";
const money=(v,r)=>num(v)?fmt(v)+(r.currency?" "+esc(r.currency):""):"N/D";
const date=v=>typeof v==="string"&&(/^\d{4}-\d{2}-\d{2}$/.test(v)||v==="");
const TITLES=["ticker","company","theme","lastReview","studyDate","market","currency","priceDate","earningsRecord","thesisStatus","valuationStatus","summary","drivers","risks"];
const AMOUNTS=["recordedPrice","referencePrice","bearCagr","baseCagr","bullCagr","bearTarget","baseTarget","bullTarget","priceFor15"];
const PRIVATE=/(?:https?:\/\/|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|segundo[\s_-]*cerebro|personal_mamg|mamg97|github_pat_|ghp_|refresh_token|private_key|iban)/i;
export function verifyPublicTheses(doc){
 if(!doc||doc.schema!=="midas_public_theses_v1"||
    doc.data_class!=="author_approved_public_research_snapshot"||
    !date(doc.published_as_of)||!Array.isArray(doc.records)||doc.records.length!==25)
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
export function orderedThesisRows(rows,records,local,sort,ascending){
 const value=({issuer:i})=>{
  const r=records.get(i.ticker),l=local.get(i.ticker);
  if(["base","bear","bull"].includes(sort))return l?.[sort]??r?.[sort+"Cagr"]??null;
  if(sort==="price")return r?.recordedPrice??null;
  if(sort==="entry")return r?.priceFor15??null;
  if(sort==="target")return r?.baseTarget??null;
  if(sort==="earnings")return r?.earningsRecord||null;
  if(sort==="report")return r?.summary?"Sí":null;
  if(sort==="company")return r?.company||i.company;
  if(sort==="market")return r?.market||i.market;
  return i.ticker;
 };
 const texts=new Set(["ticker","company","market","earnings","report"]);
 return rows.sort((a,b)=>{
  const x=value(a),y=value(b),aNull=x===null||x===undefined||x==="",bNull=y===null||y===undefined||y==="";
  if(aNull!==bNull)return aNull?1:-1;
  const delta=aNull?0:texts.has(sort)?String(x).localeCompare(String(y),"es",{numeric:true}):x-y;
  return (ascending?delta:-delta)||a.issuer.ticker.localeCompare(b.issuer.ticker,"es");
 });
}
export function publicThesisTableRows(rows,records,local,selected){
 return rows.map(({issuer:i})=>{
  const r=records.get(i.ticker),l=local.get(i.ticker);
  const field=k=>l?.[k]??r?.[k+"Cagr"]??null;
  const price=r?.recordedPrice!==null&&r?money(r.recordedPrice,r)+" · "+esc(r.priceDate):"N/D";
  return '<tr class="interactive-table-row '+(selected===i.ticker?"is-selected":"")+'" data-issuer-id="'+esc(i.ticker)+'" tabindex="0">'+
   '<td><strong>'+esc(i.ticker)+'</strong></td><td><strong>'+esc(r?.company||i.company)+'</strong><small class="smallline">'+esc(r?.theme||i.sector)+'</small></td>'+
   '<td>'+esc(r?.market||i.market)+'</td><td class="number">'+price+'</td>'+
   '<td class="number">'+percent(field("bull"))+'</td><td class="number">'+percent(field("bear"))+'</td><td class="number">'+percent(field("base"))+'</td>'+
   '<td class="number">'+(r?money(r.priceFor15,r):"N/D")+'</td><td class="number">'+(r?money(r.baseTarget,r):"N/D")+'</td>'+
   '<td><small>'+esc(r?.earningsRecord||"N/D")+'</small></td>'+
   '<td><button type="button" class="smallbtn" data-action="issuer-select" data-value="'+esc(i.ticker)+'">'+(r?"Ver tesis":"Ficha")+'</button>'+
   (r?'<small class="smallline">'+esc(r.valuationStatus||r.thesisStatus)+'</small>':"")+'</td></tr>';
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
  '<p class="small-note">Extracto público de la tesis original. Los documentos internos y sus enlaces no se publican. CAGR, hipótesis y precios proceden de diferentes fechas históricas; no hay actualización bursátil en tiempo real ni recomendación de inversión.</p></article>';
}
export function publicThesisCsv(rows,records,local){
 return [["ticker","empresa","mercado","precio_registrado","fecha_precio","divisa","precio_referencia_estudio","bull_2031_cagr","bear_2031_cagr","central_2031_cagr","precio_15pct","objetivo_central_2031","estado","fecha_estudio","resultados_registrados"],
  ...rows.map(({issuer:i})=>{const r=records.get(i.ticker),l=local.get(i.ticker);
  return r?[i.ticker,r.company,r.market,r.recordedPrice??"N/D",r.priceDate,r.currency||"N/D",r.referencePrice??"N/D",l?.bull??r.bullCagr??"N/D",l?.bear??r.bearCagr??"N/D",l?.base??r.baseCagr??"N/D",r.priceFor15??"N/D",r.baseTarget??"N/D",r.valuationStatus,r.studyDate,r.earningsRecord]:
  [i.ticker,i.company,i.market,"N/D","N/D","N/D","N/D","N/D","N/D","N/D","N/D","N/D","Sin tesis pública","N/D","N/D"];})];
}
