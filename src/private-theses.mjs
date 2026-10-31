// Local-only private research archive reader; no network, storage or outbound links.
// Public issuer data and certified public estimates remain independent.
const REQUIRED=["Ticker","Empresa","Última revisión","Estado documental recuperado",
 "Horizonte","CAGR Bear (%)","CAGR Base (%)","CAGR Bull (%)"];

function rowsOf(text) {
 if(typeof text!=="string"||text.length>1000000)throw Error("Archivo ausente o demasiado grande");
 text=text.replace(/^\uFEFF/,"");
 const first=text.split(/\r?\n/,1)[0]||"";
 const delim=(first.match(/;/g)||[]).length>(first.match(/,/g)||[]).length?";":",";
 let cell="",row=[],rows=[],quoted=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"'){
   if(quoted&&text[i+1]==='"'){cell+='"';i++;}
   else quoted=!quoted;
  } else if(c===delim&&!quoted){row.push(cell);cell="";}
  else if((c==="\n"||c==="\r")&&!quoted){
   if(c==="\r"&&text[i+1]==="\n")i++;
   row.push(cell);rows.push(row);row=[];cell="";
   if(rows.length>210)throw Error("Límite de filas del archivo superado");
  } else cell+=c;
 }
 if(quoted)throw Error("Comillas CSV sin cerrar");
 if(row.length||cell){row.push(cell);rows.push(row);}
 return rows.filter(r=>r.some(x=>x.trim()));
}

function percent(value){
 const s=String(value??"").trim().replace(/\u2212/g,"-");
 if(!s)return null;
 if(!/^[+-]?\d{1,4}(?:[.,]\d{1,2})?\s*%?$/.test(s))
  throw Error("Formato CAGR inesperado");
 const n=Number(s.replace("%","").replace(",","."));
 if(!Number.isFinite(n)||n< -100||n>1000)throw Error("CAGR fuera de límites");
 return n;
}

export function parseInstitutionalLocalArchive(text,allowedTickers){
 if(!(allowedTickers instanceof Set)||allowedTickers.size<1)
  throw Error("No hay catálogo institucional verificado");
 const rows=rowsOf(text);
 if(rows.length<2)throw Error("Archivo CSV sin filas");
 const h=rows[0].map(x=>x.trim());
 for(const key of REQUIRED)if(!h.includes(key))throw Error("Falta la columna "+key);
 const field=(row,key)=>String(row[h.indexOf(key)]??"").trim();
 const seen=new Map();
 for(const row of rows.slice(1)){
  const ticker=field(row,"Ticker");
  if(!allowedTickers.has(ticker)||seen.has(ticker))throw Error("Ticker extraño o duplicado");
  const date=field(row,"Última revisión");
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date+"T00:00:00Z")))
   throw Error("Revisión no fechada");
  const status=field(row,"Estado documental recuperado");
  if(status.length<2||status.length>220)throw Error("Estado de tesis inválido");
  seen.set(ticker,{
   ticker,date,status,
   horizon:field(row,"Horizonte").slice(0,40),
   bear:percent(field(row,"CAGR Bear (%)")),
   base:percent(field(row,"CAGR Base (%)")),
   bull:percent(field(row,"CAGR Bull (%)"))
  });
 }
 return seen;
}
