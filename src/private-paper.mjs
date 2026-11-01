// Self-contained strict CSV validation for institutional, local-memory-only archives.
// No network calls, local storage, origin URLs, or private data are bundled.
const RESULT_FIELDS=["ID institucional","Algoritmo","Familia","Resultado","Estado original",
  "Divisa","Primera sesión","Última sesión","Capital inicial paper","NAV último",
  "Rentabilidad acumulada (%)","Cambio último día (%)","Sesiones registradas",
  "Posiciones abiertas","Órdenes pendientes","Drawdown máximo (%)","Actualización del extracto"];
const CURVE_FIELDS=["ID institucional","Sesión","NAV del cierre","Capital inicial"];
const SLOT=/^IL-(0[0-5]\d|06[0-4])$/;
const datePattern=/^\d{4}-\d{2}-\d{2}$/;
const MAX_BYTES=1200000;
function date(s){
 if(!datePattern.test(s))throw Error("Fecha incorrecta: "+s.slice(0,25));
 const d=new Date(s+"T00:00:00Z");
 if(!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==s)
   throw Error("Fecha inexistente");
 return s;
}
function number(s,{nullable=false,nonnegative=false}={}){
 s=String(s??"").trim().replace(/\u2212/g,"-").replace(/\u00a0/g,"").replace(/ /g,"");
 if(!s){if(nullable)return null;throw Error("Falta una cifra obligatoria");}
 if(s.endsWith("%"))s=s.slice(0,-1);
 if(!/^[+-]?[\d.,]+$/.test(s))throw Error("Cifra inválida");
 if(s.includes(",")&&s.includes("."))s=s.replace(/\./g,"").replace(",",".");
 else if(s.includes(","))s=s.replace(",",".");
 else if(/^\d{1,3}(?:\.\d{3})+$/.test(s))s=s.replace(/\./g,"");
 const n=Number(s);
 if(!Number.isFinite(n)||Math.abs(n)>1e13||(nonnegative&&n<0))
  throw Error("Cantidad no finita o fuera de límites");
 return n;
}
function parseCSV(input){
 if(typeof input!=="string"||!input||input.length>MAX_BYTES)
  throw Error("CSV ausente o demasiado grande");
 const text=input.replace(/^\uFEFF/,"");
 const first=text.split(/\r?\n/,1)[0];
 const sep=(first.match(/;/g)||[]).length>(first.match(/,/g)||[]).length?";":",";
 let inside=false,cell="",row=[],rows=[];
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"'){
   if(inside&&text[i+1]==='"'){cell+='"';i++;}
   else inside=!inside;
  }else if(c===sep&&!inside){row.push(cell);cell="";}
  else if((c==="\r"||c==="\n")&&!inside){
    if(c==="\r"&&text[i+1]==="\n")i++;
    row.push(cell);if(row.some(x=>x.trim()))rows.push(row);
    if(rows.length>1050)throw Error("Demasiadas filas");
    row=[];cell="";
  }else cell+=c;
 }
 if(inside)throw Error("CSV con comillas mal cerradas");
 if(cell||row.length){row.push(cell);if(row.some(x=>x.trim()))rows.push(row);}
 if(rows.length<2)throw Error("CSV sin registros");
 const headers=rows.shift().map(x=>x.trim().replace(/^\uFEFF/,""));
 if(new Set(headers).size!==headers.length)throw Error("Cabeceras duplicadas");
 return {headers,rows};
}
function reader(text,fields){
 const {headers,rows}=parseCSV(text);
 for(const f of fields)if(!headers.includes(f))throw Error("Falta columna: "+f);
 const at=(r,f)=>String(r[headers.indexOf(f)]??"").trim();
 return {rows,at};
}
export function parseLocalPaperResults(text){
 const {rows,at}=reader(text,RESULT_FIELDS);
 if(rows.length!==64)throw Error("Se necesitan 64 estrategias; recibidas: "+rows.length);
 const found=new Map();
 for(const row of rows){
  const id=at(row,"ID institucional");
  if(!SLOT.test(id)||found.has(id))throw Error("Identificador ausente, duplicado o fuera de catálogo");
  const model=at(row,"Algoritmo"),family=at(row,"Familia"),status=at(row,"Resultado");
  if(!model||!family||model.length>120||family.length>120)throw Error("Nombre o familia inválida");
  const active=status==="PAPER REGISTRADO · CORTE HISTÓRICO";
  if(!active&&status!=="SIN HISTÓRICO COMPARABLE")throw Error("Estado desconocido");
  let capital=number(at(row,"Capital inicial paper"),{nullable:true,nonnegative:true});
  let nav=number(at(row,"NAV último"),{nullable:true,nonnegative:true});
  let pct=number(at(row,"Rentabilidad acumulada (%)"),{nullable:true});
  const sessions=number(at(row,"Sesiones registradas"),{nonnegative:true});
  if(!Number.isInteger(sessions)||sessions>600)throw Error("Sesiones fuera de rango");
  const first=at(row,"Primera sesión"),last=at(row,"Última sesión");
  if(active){
   if(!first||!last||date(first)>date(last)||!(capital>0)||nav===null||pct===null||sessions<1)
    throw Error("Diario sin capital, fechas o NAV");
   // CSV exporters may round displayed EUR/USD and percent cells differently.
   // Use the original displayed precision as the tightest defensible tolerance.
   const decimals=value=>{
     const s=String(value??"").trim().replace(/[% ]/g,"");
     const m=s.match(/[.,](\d+)$/);
     return m?Math.min(m[1].length,10):0;
   };
   const pText=at(row,"Rentabilidad acumulada (%)");
   const nText=at(row,"NAV último");
   const pctRound=0.5*Math.pow(10,-decimals(pText));
   const navRound=0.5*Math.pow(10,-decimals(nText));
   const maxError=pctRound+100*navRound/capital+0.000001;
   if(Math.abs(100*(nav/capital-1)-pct)>maxError)
    throw Error("NAV y retorno inconsistentes");
  }else if(capital!==null||nav!==null||pct!==null||sessions!==0||first||last){
   throw Error("Una estrategia sin diario contiene rentabilidad atribuida");
  }
  const currency=at(row,"Divisa");
  if(active&&!["EUR","USD"].includes(currency))throw Error("Divisa no permitida");
  found.set(id,{id,model,family,status,active,currency,first,last,capital,nav,pct,sessions,
    positions:number(at(row,"Posiciones abiertas"),{nullable:true,nonnegative:true}),
    pending:number(at(row,"Órdenes pendientes"),{nullable:true,nonnegative:true}),
    drawdown:number(at(row,"Drawdown máximo (%)"),{nullable:true}),
    activity:at(row,"Estado original"),cutoff:at(row,"Actualización del extracto")});
 }
 for(let i=1;i<=64;i++)if(!found.has("IL-"+String(i).padStart(3,"0")))
  throw Error("Falta una estrategia del inventario");
 return found;
}
export function parseLocalPaperCurves(text,results){
 if(!(results instanceof Map)||results.size!==64)throw Error("Importa primero Resultados 64");
 const {rows,at}=reader(text,CURVE_FIELDS);
 if(rows.length>900||rows.length<1)throw Error("El archivo de curvas está vacío o es demasiado grande");
 const groups=new Map();
 for(const row of rows){
  const id=at(row,"ID institucional"),r=results.get(id);
  if(!r?.active)throw Error("Sesión para una estrategia desconocida o no activa");
  const d=date(at(row,"Sesión")),nav=number(at(row,"NAV del cierre"),{nonnegative:true});
  const initial=number(at(row,"Capital inicial"),{nonnegative:true});
  const arr=groups.get(id)||[];
  if(arr.length&&d<=arr.at(-1).date)throw Error("Fechas de una curva fuera de orden");
  if(Math.abs(initial-r.capital)>0.01)throw Error("Capital de la curva no coincide");
  arr.push({date:d,nav});groups.set(id,arr);
 }
 for(const r of results.values()){
  const arr=groups.get(r.id)||[];
  if(arr.length!==r.sessions)throw Error("Sesiones incompletas: "+r.id);
  if(r.active&&(arr[0].date!==r.first||arr.at(-1).date!==r.last||
     Math.abs(arr.at(-1).nav-r.nav)>0.01))
   throw Error("La curva no coincide con el NAV final: "+r.id);
 }
 return groups;
}
export function summarizePrivatePaper(rows,curves){
 return {
  algorithms:rows.size,
  withNav:[...rows.values()].filter(x=>x.active).length,
  pending:[...rows.values()].filter(x=>!x.active).length,
  curveObservations:curves?[...curves.values()].reduce((a,x)=>a+x.length,0):null,
  latest:[...rows.values()].reduce((a,x)=>x.last&&x.last>a?x.last:a,"")
 };
}
