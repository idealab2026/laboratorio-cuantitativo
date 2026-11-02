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
 if(allowedTickers!==undefined&&(!(allowedTickers instanceof Set)||allowedTickers.size<1))
  throw Error("Conjunto de emisores inválido");
 const rows=rowsOf(text);
 if(rows.length<2)throw Error("Archivo CSV sin filas");
 const h=rows[0].map(x=>x.trim());
 for(const key of REQUIRED)if(!h.includes(key))throw Error("Falta la columna "+key);
 const field=(row,key)=>String(row[h.indexOf(key)]??"").trim();
 const seen=new Map();
 for(const row of rows.slice(1)){
  const ticker=field(row,"Ticker");
  if(!/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/.test(ticker)||
     (allowedTickers&&!allowedTickers.has(ticker))||seen.has(ticker))
    throw Error("Ticker extraño o duplicado");
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

/** Read a user-selected CAGR2031 CSV entirely in RAM; never transmit or persist. */
export function parseLocalCagr2031(text,allowedTickers){
 const rows=rowsOf(text);
 if(rows.length<2)throw Error("CSV sin filas de empresas");
 const headers=rows[0].map(x=>x.trim().toLowerCase());
 const fields=["ticker","cagr_bear_2031","cagr_base_2031","cagr_bull_2031","estado"];
 for(const name of fields)if(!headers.includes(name))throw Error("Falta columna "+name+" de CAGR2031");
 const pick=(row,key)=>String(row[headers.indexOf(key)]??"").trim();
 const out=new Map();
 for(const row of rows.slice(1)){
  const ticker=pick(row,"ticker").toUpperCase();
  if(!/^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$/.test(ticker)||
     (allowedTickers&&!allowedTickers.has(ticker))||out.has(ticker))
   throw Error("Ticker no reconocido o duplicado");
  const status=pick(row,"estado").slice(0,180);
  if(!status)throw Error("Estado documental ausente");
  const date=headers.includes("fecha_estudio")?pick(row,"fecha_estudio"):"";
  if(date&&!/^\d{4}-\d{2}-\d{2}$/.test(date))throw Error("Fecha de estudio inválida");
  out.set(ticker,{ticker,date,status,
   bear:percent(pick(row,"cagr_bear_2031")),
   base:percent(pick(row,"cagr_base_2031")),
   bull:percent(pick(row,"cagr_bull_2031"))});
 }
 return out;
}
