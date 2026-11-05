/* Structured public research appendix and explanatory SVG figures.
   Data are taken from the dated MIDAS thesis record, not current prices.
   Historical source prose is kept verbatim apart from visual grouping. */
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number=x=>typeof x==="number"&&Number.isFinite(x);
const fmt=(x,d=2)=>number(x)?new Intl.NumberFormat("es-ES",{minimumFractionDigits:d,maximumFractionDigits:d}).format(x):"N/D";
const percent=x=>(number(x)?(x>0?"+":"")+fmt(x):"N/D")+" %";
const dollar=(x,c)=>number(x)?fmt(x)+" "+esc(c||"USD"):"N/D";
const cases=r=>[
 {name:"Bajista",target:r.bearTarget,cagr:r.bearCagr,color:"#aa5465"},
 {name:"Central",target:r.baseTarget,cagr:r.baseCagr,color:"#1a4674"},
 {name:"Alcista",target:r.bullTarget,cagr:r.bullCagr,color:"#168c7b"}
];
const svg=(title,description,content,viewBox)=>'<svg viewBox="'+viewBox+'" class="thesis-explainer-svg" role="img" aria-label="'+esc(title)+'"><title>'+esc(title)+'</title><desc>'+esc(description)+'</desc>'+content+'</svg>';
const card=(title,description,graphic,note,classname="")=>'<figure class="thesis-insight-card '+classname+'"><figcaption><strong>'+esc(title)+'</strong><span>'+esc(description)+'</span></figcaption><div class="thesis-insight-graphic">'+graphic+'</div><p>'+esc(note)+'</p></figure>';
const note='Calculado a partir de los escenarios y del precio de referencia históricos. No es una cotización actual ni una previsión de precios intermedios.';
function pathsChart(r){
 const reference=r.referencePrice;
 const ok=cases(r).filter(x=>number(x.target)&&x.target>0);
 if(!number(reference)||reference<=0||!ok.length)return '<p class="thesis-report-muted">Sin datos suficientes para construir la trayectoria matemática.</p>';
 const x0=75,x1=910,y0=38,y1=295;
 const max=Math.max(reference,...ok.map(z=>z.target))*1.13;
 const y=v=>y1-(v/max)*(y1-y0),x=t=>x0+t*(x1-x0)/5;
 let markup='';
 for(let i=0;i<=4;i++){
  const amount=max*i/4,yy=y(amount);
  markup+='<line x1="'+x0+'" x2="'+x1+'" y1="'+yy.toFixed(2)+'" y2="'+yy.toFixed(2)+'" class="insight-grid"/><text x="66" y="'+(yy+4).toFixed(2)+'" text-anchor="end" class="insight-tick">'+esc(fmt(amount,0))+'</text>';
 }
 for(let i=0;i<=5;i++){
  markup+='<text x="'+x(i)+'" y="319" text-anchor="middle" class="insight-tick">'+(2026+i)+'</text>';
 }
 for(const c of ok){
  const points=Array.from({length:6},(_,i)=>[x(i),y(reference*Math.pow(c.target/reference,i/5))]);
  markup+='<polyline points="'+points.map(p=>p.map(n=>n.toFixed(1)).join(",")).join(" ")+'" stroke="'+c.color+'" fill="none" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>';
  for(const [xp,yp] of points)markup+='<circle cx="'+xp.toFixed(1)+'" cy="'+yp.toFixed(1)+'" r="3.6" fill="'+c.color+'"/>';
 }
 const legend=ok.map(c=>'<span><i style="background:'+c.color+'"></i>'+esc(c.name)+' · '+esc(dollar(c.target,r.currency))+'</span>').join("");
 return svg("Trayectorias geométricas ilustrativas 2026–2031","Cada curva une el precio de referencia con el objetivo del escenario mediante interpolación geométrica, sin crear estimaciones anuales intermedias.",markup,"0 0 950 340")+'<div class="thesis-insight-legend">'+legend+'</div>';
}
function accumulatedChart(r){
 if(!number(r.referencePrice)||r.referencePrice<=0)return '<p class="thesis-report-muted">Falta el precio de referencia.</p>';
 const values=cases(r).map(z=>({...z,total:number(z.target)?(z.target/r.referencePrice-1)*100:null}));
 const ok=values.filter(z=>number(z.total));if(!ok.length)return '<p class="thesis-report-muted">Escenarios no calculables.</p>';
 const neg=Math.min(0,...ok.map(x=>x.total)),pos=Math.max(0,...ok.map(x=>x.total));
 const x0=220,x1=860,zero=x0+(-neg)/(pos-neg||1)*(x1-x0);
 let markup='<line x1="'+zero.toFixed(1)+'" x2="'+zero.toFixed(1)+'" y1="12" y2="239" stroke="#7f93a9" stroke-width="2"/>';
 values.forEach((v,i)=>{
  const yy=24+i*73;
  markup+='<text x="15" y="'+(yy+26)+'" class="insight-label">'+esc(v.name)+'</text>';
  if(number(v.total)){
   const end=zero+v.total/(pos-neg||1)*(x1-x0);
   markup+='<rect x="'+Math.min(zero,end).toFixed(1)+'" y="'+yy+'" width="'+Math.max(2,Math.abs(end-zero)).toFixed(1)+'" height="31" rx="4" fill="'+v.color+'"/>';
   const labelX=v.total>=0?Math.min(end+8,880):Math.max(end-7,180);
   markup+='<text x="'+labelX.toFixed(1)+'" y="'+(yy+23)+'" text-anchor="'+(v.total>=0?"start":"end")+'" class="insight-value">'+esc(percent(v.total))+'</text>';
  }else markup+='<text x="230" y="'+(yy+23)+'" class="insight-value">N/D</text>';
 });
 return svg("Rentabilidad acumulada por escenario en cinco años","Diferencia porcentual entre el objetivo de cada escenario para 2031 y el precio histórico de referencia, sin dividendos.",markup,"0 0 960 255");
}
function entryChart(r){
 if(!number(r.referencePrice)||r.referencePrice<=0||!number(r.priceFor15)||r.priceFor15<=0)
  return '<p class="thesis-report-muted">El expediente no documenta el precio de entrada P15 o el precio de referencia.</p>';
 const data=[["Referencia",r.referencePrice,"#b28d4e"],["Entrada P15",r.priceFor15,"#1a4674"],["Objetivo central",r.baseTarget,"#168c7b"]].filter(x=>number(x[1])&&x[1]>0);
 const max=Math.max(...data.map(x=>x[1]))*1.15,base=130,width=660;
 const markup=data.map(([label,v,color],i)=>{
  const y=15+i*73,end=base+width*v/max;
  return '<text x="12" y="'+(y+27)+'" class="insight-label">'+esc(label)+'</text><rect x="'+base+'" y="'+y+'" width="'+(end-base).toFixed(1)+'" height="34" rx="5" fill="'+color+'"/><text x="'+Math.min(end+12,840).toFixed(1)+'" y="'+(y+24)+'" class="insight-value">'+esc(dollar(v,r.currency))+'</text>';
 }).join("");
 const variation=(r.priceFor15/r.referencePrice-1)*100;
 return svg("Referencia, umbral P15 y objetivo central","Comparación de tres precios del estudio histórico expresados en la misma moneda.",markup,"0 0 980 235")+
 '<p class="thesis-insight-difference">El umbral P15 está <strong>'+esc(fmt(Math.abs(variation)))+' % '+(variation<=0?"por debajo":"por encima")+'</strong> del precio de referencia del estudio.</p>';
}
export function renderExplanatoryCharts(record){
 const rows=cases(record).filter(x=>number(x.target)&&x.target>0);
 if(!rows.length)return '<p class="thesis-report-muted">No hay escenarios fechados suficientes para construir gráficos.</p>';
 return '<div class="thesis-insight-grid">'+
 card("1. Evolución ilustrativa 2026–2031","Cómo se conectarían matemáticamente el precio histórico y cada objetivo",pathsChart(record),note,"thesis-insight-wide")+
 card("2. Rentabilidad total del periodo","Cambio de precio acumulado a cinco años, sin dividendos",accumulatedChart(record),note)+
 card("3. Disciplina de entrada","Referencia del estudio frente al precio para 15 % anual",entryChart(record),"El umbral P15 utiliza el objetivo central documentado. No representa una orden de compra.")+
 '</div>';
}
function heading(line){
 const t=line.trim();
 if(!t||t.length>115)return false;
 if(/^\d{1,2}(?:\.\d+)?[.)]\s+[^\d]/u.test(t))return true;
 if(/^(Investment Committee Snapshot|Investment conclusion|Executive summary|Resumen ejecutivo|Conclusi[oó]n|Riesgos|Catalizadores|Por qu[eé] invertir|Escenarios|Sensibilidades|Fuente[s]? y m[eé]todo|Auditor[ií]a adversarial)$/i.test(t))return true;
 return t.length>11&&/^[A-ZÁÉÍÓÚÑ0-9\s·:—–/\-()]+$/u.test(t)&&!t.includes("USD")&&t.split(" ").length<=12;
}
const blank=l=>!l.trim();
const decoration=l=>/^[\s_━─═\-]{7,}$/u.test(l.trim());
const figure=l=>/^(Figura|Gr[aá]fico|Figure|Chart)\s*\d+[.:]/iu.test(l);
const bullet=l=>/^\s*(?:[•▪◦]|[-*]\s)\s*/u.test(l);
const sanitizeLines=source=>source.replace(/\r/g,"").split("\n").map(x=>x.replace(/\t/g," ").trim());
const startsScenario=(a,i)=>i+3<a.length&&(/^(FY2031|Indicador|Escenario|M[eé]trica)$/i.test(a[i])||/FY2031.*ESCENARIOS/i.test(a[i]))&&/Bear|Bajista/i.test(a[i+1])&&/Base|Central/i.test(a[i+2])&&/Bull|Alcista/i.test(a[i+3]);
function scenarioTable(lines,start){
 if(!startsScenario(lines,start))return null;
 let i=start+4;const headings=lines.slice(start+1,start+4);
 const body=[];
 while(i+3<lines.length&&body.length<16){
  const label=lines[i],values=lines.slice(i+1,i+4);
  if(!label||heading(label)||decoration(label)||figure(label)||values.some(x=>!x||x.length>80)||label.length>83)break;
  body.push([label,...values]);i+=4;
 }
 if(body.length<2)return null;
 const rows=body.map(r=>'<tr>'+r.map((cell,j)=>j===0?'<th scope="row">'+esc(cell)+'</th>':'<td>'+esc(cell)+'</td>').join("")+'</tr>').join("");
 return {next:i,html:'<div class="thesis-source-table-wrap"><table class="thesis-source-table"><caption>'+esc(lines[start])+' · tabla del documento original</caption><thead><tr><th>Indicador</th>'+headings.map(x=>'<th>'+esc(x)+'</th>').join("")+'</tr></thead><tbody>'+rows+'</tbody></table></div>'};
}
function keyValueTable(lines,start){
 if(lines[start]!=="Parámetro"||!/^Referencia del informe$/i.test(lines[start+1]||""))return null;
 let i=start+2;const body=[];
 while(i+1<lines.length&&body.length<24){
  const k=lines[i],v=lines[i+1];
  if(!k||!v||decoration(k)||heading(k)||figure(k)||k.length>88||v.length>180)break;
  body.push([k,v]);i+=2;
 }
 if(body.length<3)return null;
 return {next:i,html:'<div class="thesis-source-table-wrap"><table class="thesis-source-table"><caption>Ficha de parámetros del informe original</caption><thead><tr><th>Parámetro</th><th>Referencia del informe</th></tr></thead><tbody>'+body.map(([k,v])=>'<tr><th scope="row">'+esc(k)+'</th><td>'+esc(v)+'</td></tr>').join("")+'</tbody></table></div>'};
}
function dataParagraph(text){return '<p class="thesis-source-paragraph">'+esc(text)+'</p>';}
export function renderCanonicalSource(source){
 if(!source)return '<p class="thesis-report-muted">El informe ejecutivo íntegro no está disponible en la edición pública. Esta vista conserva exclusivamente las hipótesis documentadas.</p>';
 const lines=sanitizeLines(String(source).normalize("NFC"));
 let i=0,out=[],items=[];
 const closeList=()=>{if(items.length){out.push('<ul class="thesis-source-list">'+items.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul>');items=[];}};
 while(i<lines.length){
  const t=lines[i];if(blank(t)||decoration(t)){closeList();i++;continue;}
  const tab=scenarioTable(lines,i)||keyValueTable(lines,i);
  if(tab){closeList();out.push(tab.html);i=tab.next;continue;}
  if(figure(t)){closeList();out.push('<aside class="thesis-source-figure-reference"><span>REFERENCIA DEL DOCUMENTO ORIGINAL</span><p>'+esc(t)+'</p><small>La figura original se cita aquí, pero no se reconstruye sin su serie de datos verificable.</small></aside>');i++;continue;}
  if(heading(t)){closeList();out.push('<h3 class="thesis-source-heading">'+esc(t)+'</h3>');i++;continue;}
  if(bullet(t)){items.push(t.replace(/^\s*(?:[•▪◦]|[-*]\s)\s*/u,""));i++;continue;}
  closeList();
  let paragraph=t;
  while(i+1<lines.length){
    const next=lines[i+1];
    if(!next||decoration(next)||heading(next)||figure(next)||bullet(next)||startsScenario(lines,i+1)||next==="Parámetro")break;
    // Merge hard-wrapped PDF lines, never join already complete long paragraphs.
    if(paragraph.length>850||paragraph.length>145||/[.!?:;”"]$/u.test(paragraph))break;
    paragraph+=" "+next;i++;
  }
  out.push(dataParagraph(paragraph));i++;
 }
 closeList();
 return '<div class="thesis-source-body" aria-label="Texto canónico editado para lectura en la web">'+out.join("")+'</div>';
}
