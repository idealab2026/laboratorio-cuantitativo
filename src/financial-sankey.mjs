/* MIDAS · Sankey financiero de fuentes oficiales, independiente de valoraciones históricas.
   Conservación estricta: suma de fuentes = ingresos = costes operativos + resultado operativo.
   El resultado neto se presenta fuera del Sankey: incluye partidas no operativas. */
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const TICKER=/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/;
const DOMAINS=new Set(["microsoft.com","adobe.com","investor.atmeta.com","investors.palantir.com","investors.caterpillar.com","ir.netflix.net","ir.aboutamazon.com","www.sec.gov"]);
const COLORS={cogs:"#b77b59",rnd:"#567bb1",marketing:"#9b75ac",gna:"#b39a63",amort:"#a18e83",finance:"#8e879a",other:"#8c9ba9",tech:"#668ab0",fulfill:"#c39763",result:"#2a8876"};
const allowedSource=url=>{
 try{
  const value=new URL(url);
  if(value.protocol!=="https:"||value.username||value.password)return false;
  const host=value.hostname.toLowerCase();
  return DOMAINS.has(host)||host==="www.adobe.com"||host==="www.microsoft.com";
 }catch{return false;}
};
export function verifyFinancialSankeys(document,allowed){
 if(document?.schema!=="midas_official_financial_sankeys_v2"||!Array.isArray(document.companies))throw Error("Catálogo Sankey no válido");
 const required=new Set(allowed),found=new Set(),result=new Map();
 if(document.companies.length!==required.size)throw Error("Cobertura incompleta del catálogo de empresas");
 for(const c of document.companies){
  if(!TICKER.test(c?.ticker||"")||!required.has(c.ticker)||found.has(c.ticker)||!Array.isArray(c.periods)||c.periods.length>12)throw Error("Emisor sin cobertura o duplicado");
  found.add(c.ticker);
  if(!["verified_official","awaiting_official_statement"].includes(c.status))throw Error("Estado documental inválido");
  if(c.status==="verified_official"&&!c.periods.length)throw Error("Sin respaldo de cifras");
  if(c.status!=="verified_official"&&c.periods.length)throw Error("Cifras no verificadas");
  const ids=new Set();
  for(const p of c.periods){
   if(!/^\d{4}-\d{2}-\d{2}$/.test(p.period_end||"")||p.period_end>document.as_of||
    !/^(annual_audited|annual_reported|quarterly_unaudited)$/.test(p.kind||"")||
    p.unit!=="USD millions"||p.basis!=="reported GAAP"||
    typeof p.id!=="string"||!/^[0-9A-Za-z]{4,16}$/.test(p.id)||ids.has(p.id)||
    !allowedSource(p.source?.url)||!finite(p.revenue)||p.revenue<=0||
    !finite(p.operating_income)||p.operating_income<0||!Array.isArray(p.expenses)||
    p.expenses.length<2||p.expenses.length>16||
    !Array.isArray(p.revenue_sources)||p.revenue_sources.length<2||p.revenue_sources.length>16||
    typeof p.revenue_source_basis!=="string"||p.revenue_source_basis.length<3||p.revenue_source_basis.length>120||
    (p.revenue_source_url&&!allowedSource(p.revenue_source_url)))throw Error("Periodo de fuente no válido: "+c.ticker);
   ids.add(p.id);
   const codes=new Set();
   let sum=0;
   for(const e of p.expenses){
    if(typeof e.label!=="string"||!e.label||e.label.length>75||typeof e.code!=="string"||
       !/^[a-z]{3,12}$/.test(e.code)||codes.has(e.code)||!finite(e.value)||e.value<0)
      throw Error("Partida inválida: "+c.ticker);
    codes.add(e.code);sum+=e.value;
   }
   let inSum=0;
   const sourceLabels=new Set();
   for(const origin of p.revenue_sources){
    if(!origin||Object.keys(origin).sort().join("|")!=="label|value"||
       typeof origin.label!=="string"||!origin.label.trim()||origin.label.length>75||
       sourceLabels.has(origin.label.toLowerCase())||!finite(origin.value)||origin.value<=0)
      throw Error("Origen de ingresos inválido: "+c.ticker+" "+p.id);
    sourceLabels.add(origin.label.toLowerCase());inSum+=origin.value;
   }
   if(Math.abs(inSum-p.revenue)>0.006)throw Error("Descuadre de ingresos por origen: "+c.ticker+" "+p.id);
   if(Math.abs(sum+p.operating_income-p.revenue)>0.006)throw Error("Descuadre financiero: "+c.ticker+" "+p.id);
   if(p.net_income!=null&&!finite(p.net_income))throw Error("Resultado neto no válido");
   if(typeof p.notes!=="string"||p.notes.length>500)throw Error("Notas sin validar");
  }
  result.set(c.ticker,c);
 }
 if(found.size!==required.size)throw Error("Emisores no publicados");
 return result;
}
const fmt=n=>new Intl.NumberFormat("es-ES",{maximumFractionDigits:3,minimumFractionDigits:0}).format(n);
const value=n=>fmt(n)+" M USD";
const metric=(name,amount,detail)=>'<div class="financial-metric"><span>'+esc(name)+'</span><strong>'+esc(value(amount))+'</strong>'+(detail?'<small>'+esc(detail)+'</small>':"")+'</div>';
const percent=(n,d)=>d>0?new Intl.NumberFormat("es-ES",{minimumFractionDigits:1,maximumFractionDigits:1}).format(n/d*100)+" %":"N/D";
function diagram(period){
 const sources=period.revenue_sources;
 const targets=[...period.expenses.map(e=>({...e,type:"expense"})),{code:"result",label:"Resultado operativo",value:period.operating_income,type:"result"}].filter(x=>x.value>0);
 const total=period.revenue,top=108,totalHeight=356,scale=totalHeight/total,sourceGap=27,targetGap=17;
 const sourceLeft=259,midLeft=613,targetLeft=924;
 const sourceTop=sources.map((_,i)=>top+sources.slice(0,i).reduce((a,x)=>a+x.value*scale+sourceGap,0));
 const targetTop=targets.map((_,i)=>top+targets.slice(0,i).reduce((a,x)=>a+x.value*scale+targetGap,0));
 const graphHeight=Math.ceil(Math.max(600,top+totalHeight+sourceGap*(sources.length-1)+55,top+totalHeight+targetGap*(targets.length-1)+60));
 let pathsIn="",pathsOut="",rects="",labelsIn="",labelsOut="",leftCursor=top,rightCursor=top;
 const sourceColors=["#3f7d91","#6089b5","#8492bb","#4f9b91","#9a8aaf","#718f9b","#c09774"];
 let prevLabel=-1e9;
 for(let i=0;i<sources.length;i++){
  const origin=sources[i],ht=origin.value*scale,sy=sourceTop[i],cy=leftCursor;
  const color=sourceColors[i%sourceColors.length];leftCursor+=ht;
  pathsIn+='<path fill="'+color+'" fill-opacity=".44" d="M '+(sourceLeft+14)+' '+sy.toFixed(2)+' C 389 '+sy.toFixed(2)+' 484 '+cy.toFixed(2)+' '+midLeft+' '+cy.toFixed(2)+' L '+midLeft+' '+(cy+ht).toFixed(2)+' C 484 '+(cy+ht).toFixed(2)+' 389 '+(sy+ht).toFixed(2)+' '+(sourceLeft+14)+' '+(sy+ht).toFixed(2)+' Z"><title>'+esc(origin.label)+' · '+esc(value(origin.value))+' · '+esc(percent(origin.value,total))+'</title></path>';
  rects+='<rect x="'+sourceLeft+'" y="'+sy.toFixed(2)+'" width="14" height="'+Math.max(.6,ht).toFixed(2)+'" fill="'+color+'" rx="1"></rect>';
  const labelY=Math.max(sy+ht/2-8,prevLabel+38);prevLabel=labelY;
  labelsIn+='<text class="financial-sankey-origin-name" x="244" text-anchor="end" y="'+labelY.toFixed(2)+'">'+esc(origin.label)+'</text>'+
            '<text class="financial-sankey-origin-amount" x="244" text-anchor="end" y="'+(labelY+17).toFixed(2)+'">'+esc(value(origin.value))+' · '+esc(percent(origin.value,total))+'</text>';
 }
 for(let i=0;i<targets.length;i++){
  const e=targets[i],ht=e.value*scale,tgt=targetTop[i],color=COLORS[e.code]||COLORS.other;
  const sy=rightCursor;rightCursor+=ht;
  pathsOut+='<path fill="'+color+'" fill-opacity="'+(e.type==="result"?.56:.36)+'" d="M '+(midLeft+17)+' '+sy.toFixed(2)+' C 749 '+sy.toFixed(2)+' 810 '+tgt.toFixed(2)+' '+targetLeft+' '+tgt.toFixed(2)+' L '+targetLeft+' '+(tgt+ht).toFixed(2)+' C 810 '+(tgt+ht).toFixed(2)+' 749 '+(sy+ht).toFixed(2)+' '+(midLeft+17)+' '+(sy+ht).toFixed(2)+' Z"><title>'+esc(e.label)+' · '+esc(value(e.value))+' · '+esc(percent(e.value,total))+'</title></path>';
  rects+='<rect x="'+targetLeft+'" y="'+tgt.toFixed(2)+'" width="15" height="'+Math.max(.6,ht).toFixed(2)+'" rx="1" fill="'+color+'"></rect>';
  labelsOut+='<text class="financial-sankey-name" x="951" y="'+(tgt+Math.max(14,ht/2)).toFixed(2)+'">'+esc(e.label)+'</text>'+
            '<text class="financial-sankey-amount" x="951" y="'+(tgt+Math.max(14,ht/2)+17).toFixed(2)+'">'+esc(value(e.value))+' · '+esc(percent(e.value,total))+'</text>';
 }
 const desc="Origen de ingresos: "+sources.map(s=>s.label+" "+value(s.value)).join("; ")+". Total "+value(total)+". Destino: "+targets.map(t=>t.label+" "+value(t.value)).join("; ")+". Resultado operativo separado del neto.";
 return '<div class="financial-sankey-canvas" tabindex="0" aria-label="Sankey completo, desplaza horizontalmente en pantallas pequeñas">'+
 '<svg role="img" aria-label="'+esc(desc)+'" viewBox="0 0 1380 '+graphHeight+'" xmlns="http://www.w3.org/2000/svg">'+
 '<text x="30" y="30" class="financial-sankey-caption">ORIGEN DE LOS INGRESOS</text><text x="560" y="30" class="financial-sankey-caption">INGRESOS TOTALES</text><text x="930" y="30" class="financial-sankey-caption">DESTINO DE LOS INGRESOS</text>'+
 '<text x="'+(midLeft+8)+'" y="61" text-anchor="middle" class="financial-sankey-revenue-amount">'+esc(value(total))+'</text>'+
 pathsIn+pathsOut+rects+
 '<rect x="'+midLeft+'" y="'+top+'" width="17" height="'+totalHeight+'" fill="#153d63" rx="2"></rect>'+
 labelsIn+labelsOut+'</svg></div>';
}
function originsBreakdown(p){
 return '<div class="financial-breakdown financial-breakdown-origins"><table><caption>Conciliación de ingresos por '+esc(p.revenue_source_basis)+'</caption><thead><tr><th>Origen oficial</th><th>Millones USD</th><th>% de ingresos</th></tr></thead><tbody>'+
 p.revenue_sources.map(x=>'<tr><th>'+esc(x.label)+'</th><td>'+esc(fmt(x.value))+'</td><td>'+esc(percent(x.value,p.revenue))+'</td></tr>').join("")+
 '<tr class="financial-breakdown-total"><th>Ingresos consolidados</th><td>'+esc(fmt(p.revenue))+'</td><td>100,0 %</td></tr></tbody></table></div>';
}
function breakdown(p){
 const rows=[...p.expenses,{code:"result",label:"Resultado operativo",value:p.operating_income}];
 return '<div class="financial-breakdown"><table><caption>Conciliación exacta del resultado operativo</caption><thead><tr><th>Partida oficial</th><th>Millones USD</th><th>% de ingresos</th></tr></thead><tbody>'+
 rows.map(x=>'<tr><th>'+esc(x.label)+'</th><td>'+esc(fmt(x.value))+'</td><td>'+esc(percent(x.value,p.revenue))+'</td></tr>').join("")+
 '<tr class="financial-breakdown-total"><th>Ingresos consolidados</th><td>'+esc(fmt(p.revenue))+'</td><td>100,0 %</td></tr></tbody></table></div>';
}
export function renderFinancialSankey(company,selectedId=null){
 if(!company||!company.periods?.length){
  return '<div class="financial-sankey-empty"><div class="financial-sankey-empty-graphic" aria-hidden="true"><span>Ingresos</span><i></i><span>Gastos / resultado</span></div><p><strong>Desglose oficial pendiente de verificar.</strong> El gráfico se activará cuando consten ingresos, costes y resultado operativo del mismo periodo y fuente primaria. No se usan estimaciones ni importes procedentes de tesis históricas.</p></div>';
 }
 const periods=[...company.periods].sort((a,b)=>b.period_end.localeCompare(a.period_end));
 const p=periods.find(x=>x.id===selectedId)||periods[0];
 const selector=periods.length>1?
 '<label class="financial-sankey-period-label" for="financial-sankey-period">Periodo</label><select id="financial-sankey-period" class="financial-sankey-period">'+periods.map(x=>'<option value="'+esc(x.id)+'"'+(x.id===p.id?" selected":"")+'>'+esc(x.label)+'</option>').join("")+'</select>':
 '<span class="financial-sankey-single">'+esc(p.label)+'</span>';
 return '<div class="financial-sankey-panel"><div class="financial-sankey-toolbar">'+selector+
 '<span class="financial-sankey-kind">'+(p.kind==="annual_audited"?"Anual auditado":p.kind==="quarterly_unaudited"?"Trimestral no auditado":"Anual publicado por emisor")+'</span></div>'+
 '<div class="financial-sankey-metrics">'+metric("Ingresos",p.revenue)+metric("Costes operativos",p.expenses.reduce((s,e)=>s+e.value,0))+metric("Resultado operativo",p.operating_income,percent(p.operating_income,p.revenue)+" de margen")+
 (p.net_income!=null?metric("Resultado neto",p.net_income,"No forma parte de los flujos del Sankey"):"")+'</div>'+
 diagram(p)+originsBreakdown(p)+breakdown(p)+
 '<p class="financial-sankey-interpretation">El Sankey muestra el origen de ingresos por desglose oficial y su distribución hacia gastos y beneficio operativo, con idéntica masa total a ambos lados. El beneficio neto aparece por separado porque intervienen intereses, partidas no operativas e impuestos. No mezclar con flujos de caja ni con CAGR de las tesis.</p>'+
 '<div class="financial-sankey-source"><strong>Fuente primaria:</strong> <a href="'+esc(p.source.url)+'" target="_blank" rel="noopener noreferrer">Documento oficial ↗</a><span>Periodo: '+esc(p.period_start||"N/D")+' a '+esc(p.period_end)+'</span><span>Unidad: millones de USD · datos GAAP</span></div>'+
 (p.notes?'<p class="financial-sankey-notes">'+esc(p.notes)+'</p>':"")+'</div>';
}