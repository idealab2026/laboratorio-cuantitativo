import {parseInstitutionalLocalArchive} from "./private-theses.mjs";
const table=document.getElementById("table");
const count=document.getElementById("count");
const message=document.getElementById("message");
const input=document.getElementById("private-file");
const clear=document.getElementById("clear");
const pct=v=>Number.isFinite(v)?
 new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2}).format(v)+" %":
 "N/D";
function erase(){
 table.replaceChildren();
 count.textContent="0 empresas";
 message.textContent="Los datos se han descartado de esta vista.";
 input.value="";
}
clear.addEventListener("click",erase);
input.addEventListener("change",async()=>{
 table.replaceChildren();
 count.textContent="0 empresas";
 const file=input.files?.[0];
 if(!file)return;
 try{
  if(file.size>1000000)throw Error("CSV demasiado grande");
  const rows=parseInstitutionalLocalArchive(await file.text());
  for(const record of rows.values()){
   const tr=document.createElement("tr");
   for(const value of [record.ticker,record.date,record.status,record.horizon,
                       pct(record.bear),pct(record.base),pct(record.bull)]){
     const td=document.createElement("td");
     td.textContent=value;
     tr.append(td);
   }
   table.append(tr);
  }
  count.textContent=rows.size+" expedientes; "+[...rows.values()].filter(x=>Number.isFinite(x.base)).length+" CAGR centrales numéricos";
  message.textContent="Consulta exclusivamente local. Valores históricos, no precios actuales ni recomendaciones. La página no envía datos al servidor.";
 }catch(err){
  table.replaceChildren();
  input.value="";
  message.textContent="Archivo rechazado: "+String(err.message||err);
 }
});
