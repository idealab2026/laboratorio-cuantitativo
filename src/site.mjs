import {verify,table,formatPct} from "./metrics.mjs";
const $=id=>document.getElementById(id),NS="http://www.w3.org/2000/svg";
const svgEl=(tag,attributes={},content)=>{const e=document.createElementNS(NS,tag);Object.entries(attributes).forEach(([k,v])=>e.setAttribute(k,String(v)));if(content!==undefined)e.textContent=content;return e;};
const node=(tag,content,cls)=>{const e=document.createElement(tag);if(content!==undefined)e.textContent=content;if(cls)e.className=cls;return e;};
function chart(strategy,dates){
 const svg=$("nav-chart");svg.replaceChildren();
 const all=strategy.nav,lo=Math.min(...all)-2,hi=Math.max(...all)+2;
 const x=i=>55+i*(680/(all.length-1)),y=v=>240-(v-lo)*190/(hi-lo);
 for(let n=0;n<4;n++){const val=lo+(hi-lo)*n/3,yy=y(val);svg.append(svgEl("line",{x1:55,y1:yy,x2:735,y2:yy,stroke:"#e2e7ed"}),svgEl("text",{x:12,y:yy+4,"font-size":12,fill:"#677992"},val.toFixed(1)));}
 const points=all.map((v,i)=>x(i)+","+y(v)).join(" ");
 svg.append(svgEl("polyline",{points,stroke:"#19376d","stroke-width":3,fill:"none","stroke-linejoin":"round","stroke-linecap":"round"}));
 all.forEach((v,i)=>{svg.append(svgEl("circle",{cx:x(i),cy:y(v),r:3.7,fill:"#19376d"}));svg.append(svgEl("text",{x:x(i),y:267,"text-anchor":"middle","font-size":12,fill:"#657790"},dates[i]));});
 $("chart-title").textContent=strategy.name+" · NAV hipotético";
 $("chart-note").textContent="Eje horizontal: sesiones ficticias. Eje vertical: unidades simuladas. No son cotizaciones observadas.";
}
function detail(item,data){
 $("detail-name").textContent=item.name;$("detail-rule").textContent=item.rule;
 $("detail-return").textContent=formatPct(item.returnPct);
 $("detail-dd").textContent=new Intl.NumberFormat("es-ES",{maximumFractionDigits:2}).format(item.drawdownPct)+" %";
 $("detail-coverage").textContent=item.coverage+" %";
 chart(item,data.dates);
}
function makeTable(data,sort){
 const items=table(data);if(sort==="drawdown")items.sort((a,b)=>a.drawdownPct-b.drawdownPct);
 if(sort==="name")items.sort((a,b)=>a.name.localeCompare(b.name,"es"));
 const body=$("strategies-body");body.replaceChildren();
 for(const item of items){
  const tr=node("tr");
  for(const [val,cls] of [[item.name,""],[item.category,""],[formatPct(item.returnPct),"number"],[item.drawdownPct.toFixed(2)+" %","number"],[item.coverage+" %","number"]])tr.append(node("td",val,cls));
  const t=node("td"),b=node("button","Examinar","smallbtn");b.type="button";b.addEventListener("click",()=>detail(item,data));t.append(b);tr.append(t);body.append(tr);
 }
}
function makeTheses(data){
 const grid=$("theses-grid");grid.replaceChildren();
 for(const thesis of data.theses){
  const card=node("article",undefined,"panel"),top=node("div",undefined,"panel-top");top.append(node("span",thesis.kind,"label"),node("span",thesis.status,"chip"));card.append(top,node("h3",thesis.subject));
  for(const [title,value] of [["Hipótesis",thesis.hypothesis],["Posible refutación",thesis.counter],["Prueba",thesis.test],["Evidencia",thesis.evidence]]){
   const p=node("p");p.append(node("strong",title+": "),document.createTextNode(value));card.append(p);
  } grid.append(card);
 }
}
async function main(){
 const res=await fetch("./data/demo.json",{cache:"no-store"});if(!res.ok)throw new Error("No se pudo leer la muestra");
 const data=await res.json();verify(data);const stats=table(data);
 $("stat-strategies").textContent=stats.length;$("stat-theses").textContent=data.theses.length;$("stat-sessions").textContent=data.dates.length;
 makeTable(data,"return");makeTheses(data);detail(stats[0],data);
 $("sort-strategies").addEventListener("change",e=>makeTable(data,e.target.value));
}
main().catch(()=>{$("chart-note").textContent="El conjunto demostrativo no está disponible o no supera el control de integridad.";});
