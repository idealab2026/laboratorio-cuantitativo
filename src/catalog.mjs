// IDEA LAB public issuer catalogue: identities only, no imported financial analysis.
const isBlank=x=>x===null||x===undefined;
const financialFields=["price","priceAsOf","bearCagr","baseCagr","bullCagr","bearTarget","baseTarget","bullTarget","buyPrice15","nextEarnings","reportUrl"];
export function verifyIssuerCatalog(data){
 if(data?.meta?.data_class!=="public_issuer_catalog")throw Error("Invalid catalogue classification");
 if(data.meta.price_status!=="NO_MARKET_FEED"||data.meta.valuation_status!=="NOT_INDEPENDENTLY_VALIDATED")throw Error("Misleading catalogue source");
 if(!Array.isArray(data.issuers)||data.issuers.length<1||data.issuers.length>100)throw Error("Invalid issuer set");
 const seen=new Set();
 for(const issuer of data.issuers){
  if(!/^[A-Z0-9]{1,5}(?:\.[A-Z]{1,2})?$/.test(issuer.ticker||""))throw Error("Ticker outside allowed representation");
  if(seen.has(issuer.ticker))throw Error("Duplicate issuer");
  seen.add(issuer.ticker);
  if(!issuer.company||typeof issuer.company!=="string"||issuer.company.length>100||!issuer.sector||!issuer.market)throw Error("Incomplete public company identity");
  if(!financialFields.every(field=>isBlank(issuer[field])))throw Error("Unverified financial claims in public catalogue");
  if(issuer.status!=="Pendiente de investigación pública")throw Error("Unverified editorial status");
 }
 return true;
}
export function filterIssuers(data,query="",sort="ticker"){
 verifyIssuerCatalog(data);
 const q=String(query).trim().toLocaleLowerCase("es");
 const selected=data.issuers.filter(i=>[i.ticker,i.company,i.sector,i.market].join(" ").toLocaleLowerCase("es").includes(q));
 const field=["ticker","company","market","sector"].includes(sort)?sort:"ticker";
 return [...selected].sort((a,b)=>a[field].localeCompare(b[field],"es")||a.ticker.localeCompare(b.ticker,"es"));
}
