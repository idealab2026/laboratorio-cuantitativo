import {signalAtClose,methodCatalog} from "./paper-methods.mjs";
const valid=(x)=>typeof x==="number"&&Number.isFinite(x);
const key=/^SIM-[A-Z]$/;
export function validatePanel(panel){
 if(!panel||panel.source!=="generated_research_ohlc_v1"||panel.synthetic!==true||panel.currency!=="USD")
  throw Error("Only labelled synthetic paper input is supported");
 const entries=Object.entries(panel.bars||{});
 if(!entries.length||entries.length>12||entries.some(([id])=>!key.test(id)))throw Error("Invalid paper universe");
 let timeline;
 for(const [symbol,bars] of entries){
  if(!Array.isArray(bars)||bars.length<80||bars.length>1000)throw Error("Insufficient aligned OHLC history");
  const dates=bars.map(b=>b.session);
  if(dates.some((d,i)=>!/^\d{4}-\d\d-\d\d$/.test(d)||i&&d<=dates[i-1]))throw Error("Invalid ordered sessions");
  if(timeline&&JSON.stringify(dates)!==JSON.stringify(timeline))throw Error("Unaligned session calendar");
  timeline=dates;
  for(const bar of bars){
   const {open,high,low,close,volume=0,dividend=0,split=0}=bar;
   if(![open,high,low,close,volume,dividend,split].every(valid)||
      Math.min(open,high,low,close)<=0||low>Math.min(open,close)||high<Math.max(open,close)||
      volume<0||dividend<0||split<0)throw Error("Inconsistent OHLC and corporate action");
  }
 }
 if(panel.asOf!==timeline.at(-1))throw Error("As-of date does not match complete panel");
 return {symbols:entries.map(x=>x[0]),timeline};
}
export function validatePaperConfig(config,symbols){
 if(!config||config.schema!==1||config.currency!=="USD"||
   !valid(config.capital)||config.capital<=0||
   !valid(config.feeBps)||config.feeBps<0||config.feeBps>100||
   !valid(config.slippageBps)||config.slippageBps<0||config.slippageBps>100||
   !valid(config.investFraction)||config.investFraction<=0||config.investFraction>1||
   !Number.isInteger(config.maxPositions)||config.maxPositions<1||config.maxPositions>symbols.length||
   !Array.isArray(config.strategies)||config.strategies.length<1||config.strategies.length>20)
  throw Error("Invalid institutional campaign contract");
 const allowed=new Set(methodCatalog.map(x=>x.id)),names=new Set();
 for(const row of config.strategies){
  if(!row||typeof row.id!=="string"||!/^M-[A-Z0-9]{2,8}$/.test(row.id)||
     names.has(row.id)||!allowed.has(row.method)||!Array.isArray(row.symbols)||!row.symbols.length||
     row.symbols.some(x=>!symbols.includes(x))||new Set(row.symbols).size!==row.symbols.length)
   throw Error("Unknown or duplicate paper method");
  names.add(row.id);
 }
}
const stateOf=(config,panel)=>({
 schema:1,status:"SYNTHETIC_PROSPECTIVE_ACCOUNTING_SANDBOX",source:panel.source,
 synthetic:true,currency:"USD",configuration:JSON.stringify(config),
 lastSession:null,historyPrefix:null,portfolios:Object.fromEntries(config.strategies.map(m=>[m.id,{
  cash:config.capital,holdings:{},orders:{},events:[],equity:[],feeTotal:0,dividendTotal:0
 }]))
});
