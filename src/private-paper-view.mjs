import {parseLocalPaperResults,parseLocalPaperCurves,summarizePrivatePaper} from "./private-paper.mjs";
let rows=null,curves=null,selected="";
const $=id=>document.getElementById(id);
const money=(n,c)=>n==null?"—":new Intl.NumberFormat("es-ES",
 {minimumFractionDigits:2,maximumFractionDigits:2}).format(n)+" "+(c||"");
const pct=n=>n==null?"—":new Intl.NumberFormat("es-ES",
 {minimumFractionDigits:2,maximumFractionDigits:2}).format(n)+" %";
const results=$("paper-results"),nav=$("paper-curves"),clear=$("clear");
function mark(status){$("status").textContent=status;}
function clean(){
 rows=null;curves=null;selected="";
 results.value="";nav.value="";nav.disabled=true;clear.disabled=true;
 $("group").replaceChildren();$("summary").textContent="No se ha importado un registro.";
 $("body").replaceChildren();$("detail").replaceChildren();
 mark("Sin datos privados en memoria.");
}
clear.addEventListener("click",clean);
function render(){
 const box=$("body");box.replaceChildren();
 if(!rows)return;
 const search=$("query").value.trim().toLowerCase(),group=$("group").value;
 const show=[...rows.values()].filter(r=>(!group||r.family===group)&&
  (!search||(r.id+" "+r.model+" "+r.family).toLowerCase().includes(search)));
 for(const r of show){
  const tr=document.createElement("tr");
  for(const s of [r.id,r.model,r.family,r.last||"Sin histórico",
                  r.positions==null?"—":r.positions,
                  r.pending==null?"—":r.pending,pct(r.pct),
                  money(r.nav,r.currency)]){
   const cell=document.createElement("td");
   cell.textContent=String(s);tr.append(cell);
  }
  tr.tabIndex=0;
  tr.title="Ver detalles y curva registrada";
  tr.addEventListener("click",()=>draw(r.id));
  tr.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();draw(r.id);}});
  box.append(tr);
 }
 $("summary").textContent=show.length+" estrategias visibles de "+rows.size+
  " · 47 con NAV documentado · 17 sin diario comparable · archivo histórico no sincronizado";
 if(selected&&rows.has(selected))draw(selected);
}
function textNode(tag,value,parent){
 const e=document.createElement(tag);e.textContent=value;parent.append(e);return e;
}
function draw(id){
 selected=id;const r=rows.get(id),detail=$("detail");detail.replaceChildren();
 textNode("h3",r.id+" · "+r.model,detail);
 textNode("p",r.family+" · "+(r.active?"Paper registrado":"Sin diario económico")+
  " · "+(r.last||"sin fecha")+" · "+(r.currency||"sin divisa"),detail);
 const summary=document.createElement("p");
 summary.textContent="Rentabilidad histórica: "+pct(r.pct)+" · NAV: "+
  money(r.nav,r.currency)+" · posiciones: "+(r.positions??"—")+
  " · órdenes pendientes: "+(r.pending??"—")+
  " · drawdown: "+pct(r.drawdown);
 detail.append(summary);
 const pts=curves?.get(id);
 if(!pts){textNode("p",r.active?"Carga el CSV «Curvas NAV» para visualizar las sesiones.":"No existen sesiones verificadas para este slot.",detail);return;}
 const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
 svg.setAttribute("viewBox","0 0 960 230");svg.setAttribute("role","img");
 svg.setAttribute("aria-label","Serie histórica NAV de "+r.model+" desde "+pts[0].date+" hasta "+pts.at(-1).date);
 svg.style.width="100%";svg.style.maxHeight="265px";
 const low=Math.min(...pts.map(x=>x.nav)),high=Math.max(...pts.map(x=>x.nav));
 const spread=Math.max(high-low,high*.002,1);
 const coords=pts.map((p,i)=>[(40+880*i/Math.max(pts.length-1,1)).toFixed(1),
 (195-160*(p.nav-low)/spread).toFixed(1)]);
 const line=document.createElementNS("http://www.w3.org/2000/svg","polyline");
 line.setAttribute("points",coords.map(p=>p.join(",")).join(" "));
 line.setAttribute("fill","none");line.setAttribute("stroke","#1f567b");
 line.setAttribute("stroke-width","2.5");
 svg.append(line);
 detail.append(svg);
 textNode("p",pts.length+" sesiones · "+pts[0].date+" → "+pts.at(-1).date+
  " · mínimo "+money(low,r.currency)+" · máximo "+money(high,r.currency),detail);
}
results.addEventListener("change",async()=>{
 rows=null;curves=null;selected="";nav.disabled=true;nav.value="";
 $("body").replaceChildren();$("detail").replaceChildren();
 try{
  const file=results.files?.[0];
  if(!file||file.size>1200000)throw Error("Selecciona un CSV inferior a 1,2 MB");
  rows=parseLocalPaperResults(await file.text());
  const group=$("group");group.replaceChildren();
  for(const [value,label]of [["","Todas las familias"],
    ...[...new Set([...rows.values()].map(r=>r.family))].sort().map(x=>[x,x])]){
    const option=document.createElement("option");option.value=value;
    option.textContent=label;group.append(option);
  }
  nav.disabled=false;clear.disabled=false;
  mark("64 estrategias históricas validadas localmente. Curvas pendientes de importar.");
  render();
 }catch(e){clean();mark("Archivo rechazado: "+(e.message||String(e)));}
});
nav.addEventListener("change",async()=>{
 curves=null;selected="";
 try{
  const file=nav.files?.[0];
  if(!file||file.size>1200000)throw Error("Selecciona un CSV inferior a 1,2 MB");
  curves=parseLocalPaperCurves(await file.text(),rows);
  const s=summarizePrivatePaper(rows,curves);
  mark(s.algorithms+" estrategias; "+s.curveObservations+
   " NAV contrastados · último cierre de referencia "+s.latest+
   ". No son resultados en directo.");
  render();
 }catch(e){nav.value="";mark("Curvas rechazadas: "+(e.message||String(e)));render();}
});
$("query").addEventListener("input",render);
$("group").addEventListener("change",render);
clean();
