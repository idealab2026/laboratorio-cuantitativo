/* Source-linked visual audit for the five full public MIDAS theses.
 * This file never recovers an absent annual time series by interpolation.
 * Each chart is a restricted comparison of explicitly documented observations
 * in data/thesis-reports.json, data/financial-sankeys.json or dated thesis cards.
 * Figures with insufficient verified observations fail visibly, never silently.
 */
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const numeric=x=>typeof x==="number"&&Number.isFinite(x)&&x>=0;
const fmt=x=>Number(x).toLocaleString("es-ES",{maximumFractionDigits:3,minimumFractionDigits:0});
const indices=(rows,periods)=>rows.map(([label,value])=>({label,value,periods}));
const cagrIndex=rate=>100*Math.pow(1+rate/100,9);
const FIXED={
 ADBE:{
  "MAIN":{title:"Crecimiento relativo FY2016–FY2025 · solo extremos",unit:"Índice FY2016=100",rows:indices([["Precio ADBE · CAGR 13,84 %",cagrIndex(13.84)],["Ingresos · CAGR 16,85 %",cagrIndex(16.85)],["Resultado neto · CAGR 22,25 %",cagrIndex(22.25)],["BPA diluido · CAGR 24,52 %",cagrIndex(24.52)]],"2016–2025"),note:"Puntos FY2025 derivados exclusivamente de los CAGR publicados (nueve intervalos). No son observaciones anuales ni rentabilidad total. Se excluye el FCF IDC legacy, no homologado.",source:"Tesis ADBE v1.3.4, CAGR FY2016–2025 y reservas QA-09."},
  "A":{title:"Ingresos, EBIT GAAP y beneficio neto · extremos",unit:"Miles de millones USD",rows:indices([["Ingresos FY2016",5.85],["Ingresos FY2025",23.77],["EBIT FY2016",1.49],["EBIT FY2025",8.71],["Beneficio neto FY2016",1.17],["Beneficio neto FY2025",7.13]],"2016/2025"),note:"Únicamente dos ejercicios, no una curva anual. FY2024 incorpora un efecto Figma en EBIT y FY2020 un efecto fiscal en NI; no se interpolan años intermedios.",source:"Tesis ADBE, magnitudes extraídas de SEC Forms 10-K FY2016 y FY2025."},
  "B":{title:"Cotización, BPA y acciones diluidas · índices extremos",unit:"Índice FY2016=100",rows:indices([["Precio · CAGR documental 13,84 %",cagrIndex(13.84)],["BPA GAAP · 2,32→16,70 USD",100*16.70/2.32],["Acciones diluidas · 504,3→427 M",100*427/504.3]],"2016–2025"),note:"Puntos finales calculados de los extremos revelados y CAGR documental; no se recrea una serie anual de cotizaciones ni se confunde cotización con retorno total.",source:"Tesis ADBE v1.3.4, BPA y diluted weighted shares SEC."},
  "C":{title:"Estadística EV/FCF IDC auditada · FY2021–FY2025",unit:"Veces",rows:indices([["Media FY2021–25",36.805693],["Mediana FY2021–25",33.175624],["Referencia Base FY2025",17.878810]],"FY2021–2025"),note:"Comparación de estadísticos, NO restauración de la serie legacy FY2016–25. Desviación típica histórica: 15,527551×; el múltiplo Base no demuestra valor intrínseco.",source:"Tesis ADBE v1.3.4, QA-09; histórico previo FY2016–20 no revalidado."},
  "D":{title:"Total Adobe ARR · coberturas y FX distintos",unit:"Miles de millones USD ARR",rows:indices([["FY2025 reportado",25.20],["FY2025 rebasado a FX FY2026",25.66],["FY2026 Q3",27.50]],"Cortes distintos"),note:"No es una serie anual homogénea ni FY2026 completo. Q3 FY2026 incluye Semrush; las definiciones y FX de los cortes difieren.",source:"Tesis ADBE, FY2025 10-K, Q4 FY2025 y Q3 FY2026."}
 },
 MSFT:{
  "1":{title:"EV/FCF IDC · resumen de estadísticos documentados",unit:"Veces",rows:indices([["Media histórica FY2017–26",29.3097],["Mediana histórica FY2017–26",28.9764],["Múltiplo Base FY2031",17.28224]],"Cortes distintos"),note:"Las diez observaciones anuales del modelo Q01/Q02 no están en la edición pública. Se muestran únicamente media, mediana y Base documentados; σ muestral 4,9227×. No se dibuja una falsa serie FY2017–26.",source:"Informe MSFT, apartado 6, reconstrucción histórica Q01/Q02."},
  "2":{title:"Objetivos económicos vigentes FY2031 · sin legado estimado",unit:"USD por acción",scenario:true,note:"La edición pública contiene los objetivos actuales Bear/Base/Bull, pero no la terna legacy v1.2 comparable. No se inventa la serie antigua.",source:"Tesis MSFT FY2031, QA04; escenarios económicos canónicos."}
 },
 META:{
  "1":{title:"Objetivos FY2031 y referencia histórica",unit:"USD por acción",scenario:true,reference:true,note:"Escenarios Bear/Base/Bull, sin probabilidades asignadas. Referencia histórica de 07/10/2026, no precio actual.",source:"Tesis META V6, QA-08 y snapshot 07/10/2026."},
  "2":{title:"Ingresos proyectados Base · hitos explícitos",unit:"Miles de millones USD",rows:indices([["FY2027 ≈",305],["FY2031",533],["FY2036",702.63]],"FY2027/FY2031/FY2036"),note:"Hipótesis MIDAS, no guidance de Meta. Márgenes EBIT divulgados en el texto: 37 % FY2031 y 36 % FY2036. No se inventan los demás años FY2028–35.",source:"Tesis META V6, modelo Base QA-08."},
  "3":{title:"Tres convenciones de flujo · Base FY2031",unit:"Miles de millones USD",rows:indices([["FCF IDC normalizado",152.69],["Cash FCF",71.69],["FCFF con SBC-COST",50.36]],"FY2031"),note:"No equivalentes contables ni una serie FY2027–36: representan tres definiciones de caja bajo un mismo escenario y año. Retenciones fiscales RSU tratadas por separado.",source:"Tesis META V6, modelo Base QA-08."},
  "4":{title:"CapEx y mantenimiento · hitos Base",unit:"Miles de millones USD",rows:indices([["FY2031 cash CapEx",178],["FY2031 mantenimiento",82],["FY2036 cash CapEx",173],["FY2036 mantenimiento",113]],"FY2031/FY2036"),note:"Hipótesis MIDAS, no información financiera futura de Meta. FY2031 growth PPE propio ≈88 BUSD; no todo el CapEx se clasifica como mantenimiento o growth PPE. No se dibujan años intermedios.",source:"Tesis META V6, modelo de reinversión QA-08."}
 },
 PLTR:{
  "1":{unavailable:"No constan cotizaciones e ingresos anuales FY2020–25 conjuntamente desglosados en esta edición. Dibujar una trayectoria 2020=100 requeriría recuperar la serie y las fechas de cierre originales, no estimarla."},
  "2":{title:"Ingresos por tipo de cliente · corte FY2025",unit:"Miles de millones USD",rows:indices([["Government FY2025",2.402287],["Commercial FY2025",2.073159]],"FY2025"),note:"Es un desglose FY2025, NO la evolución plurianual indicada en la figura histórica original. Las dos ramas concilian con 4,475446 BUSD de ingresos.",source:"Palantir 10-K FY2025, desglose consolidado y manifest del Sankey oficial."},
  "3":{title:"EBIT y convenciones FCF · FY2025",unit:"Miles de millones USD",rows:indices([["EBIT GAAP FY2025",1.414015],["Cash FCF convencional FY2025 ≈",2.10],["FCF IDC normalizado FY2025 ≈",1.14]],"FY2025"),note:"Tres métricas distintas del mismo ejercicio, no una serie histórica ni un margen bruto. Cash FCF e IDC se calculan con métodos diferentes; los ingresos por intereses no son operativos.",source:"Tesis PLTR v1.3-Q y Palantir Form 10-K FY2025 (EBIT)."},
  "4":{unavailable:"El informe público no contiene la serie conjunta FY2020–25 de beneficio neto y BPA diluido. No se sustituye por una evolución inventada ni por datos actuales no homologados."},
  "4B":{title:"Dilución histórica · extremos publicados",unit:"Índice FY2021=100",rows:indices([["Acciones diluidas FY2021",100],["Acciones diluidas FY2025",133]],"FY2021/FY2025"),note:"Incremento acumulado de acciones diluidas ≈33 % documentado en la tesis. El BPA histórico anual no está en el texto público y no se representa.",source:"Tesis PLTR v1.3-Q, interpretación de figura 4B."},
  "5":{title:"Múltiplos IDC históricos vs underwriting FY2031",unit:"Veces",rows:indices([["Histórico FY2023 ≈",303],["Histórico FY2024 ≈",629],["Histórico FY2025 ≈",368],["Legacy FY2031",35],["Base FY2031 vigente",25]],"Cortes distintos"),note:"Los años históricos tienen un denominador operativo pequeño y son aproximaciones del expediente. Legacy 35× y actual 25× son SUPUESTOS de salida, no observaciones históricas; no se promedian.",source:"Tesis PLTR v1.3-Q, apartado de múltiplos."},
  "6":{title:"Indicadores comerciales observados · Q2 2026",unit:"Miles de millones USD",rows:indices([["RPO",4.9],["U.S. Commercial RDV",6.238],["TCV trimestral",3.373]],"Q2 FY2026"),note:"RPO, remaining deal value y total contract value NO son partidas aditivas. No existe en el corpus público de la tesis una serie trimestral de RPO y NDR verificable; este gráfico no pretende reconstruirla.",source:"Tesis PLTR v1.3-Q, resultados y compromisos Q2 2026."}
 },
 CAT:{
  "1":{title:"Ventas industriales MP&E · ejercicios divulgados",unit:"Miles de millones USD",rows:indices([["FY2021",48.188],["FY2023",63.869],["FY2025",63.980]],"FY2021/FY2023/FY2025"),note:"No es una serie anual completa FY2021–25. EBIT industrial informado: 13,098 BUSD FY2024 vs 10,884 BUSD FY2025; se excluyen resultados de Financial Products.",source:"Tesis CAT, cifras oficiales consolidadas MP&E del 10-K."},
  "2":{title:"FCF IDC vs cash FCF industrial · FY2025",unit:"Miles de millones USD",rows:indices([["FCF IDC normalizado",9.557],["Cash FCF industrial",8.984]],"FY2025"),note:"Comparación únicamente de FY2025. Cash FCF excluye dividendos de Financial Products; IDC normalizado refleja convención económica de mantenimiento. No se inventan FY2021–24.",source:"Tesis CAT, anexo contable MP&E de cinco ejercicios."},
  "3":{title:"Valoración FY2031 IDC frente a DCF",unit:"USD por acción",rows:indices([["IDC Base FY2031",720.6194074],["DCF Base FY2031",458],["Referencia histórica Oct 2026",730.76]],"FY2031 vs Oct 2026"),note:"Los dos métodos son comparables solo al horizonte FY2031. La referencia es de octubre de 2026, no target; DCF valor presente ≈344 USD es otra fecha y queda fuera de estas barras.",source:"Tesis CAT, objetivos económicos y modelo del 21/10/2026."}
 }
};
const known={ADBE:["MAIN","A","B","C","D"],MSFT:["1","2"],META:["1","2","3","4"],PLTR:["1","2","3","4","4B","5","6"],CAT:["1","2","3"]};
export function figureKey(ticker,caption){
 const t=String(caption||"").trim(),id=String(ticker||"").toUpperCase();
 if(id==="ADBE"){
  if(/^GRÁFICA PRINCIPAL\b/iu.test(t))return "MAIN";
  const m=t.match(/^GRÁFICO\s+([A-D])\b/iu);return m?.[1]||null;
 }
 const m=t.match(/^Figura\s+(\d+B?)(?:[.\s]|$)/iu);return m?.[1]?.toUpperCase()||null;
}
export function isHistoricalFigure(caption){
 return /^(?:GRÁFICA\s+PRINCIPAL\b|GRÁFICO\s+[A-D]\b|Figura\s+\d+B?(?:[.\s]|$))/iu.test(String(caption||"").trim());
}
export function sourceFigureAudit(ticker,source){
 const expected=known[String(ticker||"").toUpperCase()]||[];
 const found=String(source||"").split(/\r?\n/).map(x=>figureKey(ticker,x)).filter(Boolean);
 const unique=new Set(found);
 return {ticker,expected:expected.length,found:found.length,complete:found.length===expected.length&&expected.every(k=>unique.has(k)),missing:expected.filter(k=>!unique.has(k)),figureLabels:found};
}
function chartSvg(spec){
 const rows=spec.rows||[];
 if(!rows.length||rows.length>18||rows.some(r=>!r||!numeric(r.value)))return "";
 const max=Math.max(1,...rows.map(r=>r.value));
 const height=75+rows.length*58;
 let body='<line x1="335" x2="335" y1="28" y2="'+(height-24)+'" stroke="#9eb0c3" stroke-width="1"/>';
 for(let i=0;i<rows.length;i++){
  const r=rows[i],y=33+i*58,w=Math.max(3,Math.round(615*r.value/max));
  body+='<text x="322" y="'+(y+19)+'" text-anchor="end" class="thesis-figure-label">'+esc(r.label)+'</text>'+
   '<rect x="340" y="'+y+'" width="'+w+'" height="30" rx="4" fill="'+(i%2?"#3d8d86":"#315e86")+'"/>'+
   '<text x="970" y="'+(y+20)+'" class="thesis-figure-value">'+esc(fmt(r.value))+'</text>';
 }
 return '<svg class="thesis-restored-svg" viewBox="0 0 1150 '+height+'" role="img" aria-label="'+esc(spec.title+"; "+spec.unit)+'">'+
  '<title>'+esc(spec.title)+'</title><desc>'+esc(spec.note)+'</desc>'+body+'</svg>';
}
function scenarioSpec(spec,record){
 const rows=[["Bear FY2031",record?.bearTarget],["Base FY2031",record?.baseTarget],["Bull FY2031",record?.bullTarget]];
 if(rows.some(r=>!numeric(r[1])))return null;
 if(spec.reference&&numeric(record.referencePrice))rows.push(["Referencia histórica",record.referencePrice]);
 return {...spec,rows:indices(rows,"FY2031")};
}
export function renderHistoricalFigure(ticker,caption,record){
 const id=String(ticker||"").toUpperCase(),key=figureKey(id,caption);
 const spec=FIXED[id]?.[key];
 const title=String(caption||"").trim();
 if(!spec)return '<figure class="thesis-restored-figure is-unavailable"><figcaption>'+esc(title)+'</figcaption><p>Figura histórica sin fuente tabular auditable en la edición pública; no se simula.</p></figure>';
 if(spec.unavailable)return '<figure class="thesis-restored-figure is-unavailable" data-figure="'+esc(id+"-"+key)+'"><figcaption><strong>'+esc(title)+'</strong><span>Sin reconstrucción: faltan datos de origen</span></figcaption><p>'+esc(spec.unavailable)+'</p></figure>';
 const actual=spec.scenario?scenarioSpec(spec,record):spec;
 if(!actual)return '<figure class="thesis-restored-figure is-unavailable" data-figure="'+esc(id+"-"+key)+'"><figcaption>'+esc(title)+'</figcaption><p>No hay escenarios validados para graficar.</p></figure>';
 const svg=chartSvg(actual);
 return '<figure class="thesis-restored-figure" data-figure="'+esc(id+"-"+key)+'"><figcaption><strong>'+esc(actual.title)+'</strong><span>'+esc(actual.unit)+'</span></figcaption>'+
 '<div class="thesis-restored-chart-box">'+svg+'</div>'+
 '<p class="thesis-restored-note"><b>Alcance:</b> '+esc(actual.note)+'</p>'+
 '<p class="thesis-restored-source"><b>Datos y procedencia:</b> '+esc(actual.source)+'</p>'+
 '<details><summary>Referencia de la figura en el documento original</summary><p>'+esc(title)+'</p></details></figure>';
}
