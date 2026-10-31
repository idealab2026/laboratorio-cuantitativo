import {signalAtClose,methodCatalog,artificialMethodBars} from "./paper-methods.mjs";
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

const riskOf=method=>method==="geneticFixed"?{stop:.0903,target:.2367}:
 ["hold","breakout20","breakout55"].includes(method)?{stop:null,target:null}:{stop:.08,target:.15};
function recordFill(book,symbol,side,bar,reference,config,reason,signalAt=null){
 const slip=config.slippageBps/10000,commission=config.feeBps/10000;
 const price=reference*(side==="BUY"?1+slip:1-slip);
 if(price<bar.low-0.00001||price>bar.high+0.00001)throw Error("Model fill outside OHLC");
 if(side==="SELL"){
  const position=book.holdings[symbol];
  if(!position)return;
  const gross=position.units*price,fee=gross*commission;
  book.cash+=gross-fee;book.feeTotal+=fee;
  book.events.push({type:"FILL",side,symbol,date:bar.session,signalAt,price,
   units:position.units,fee,reason});
  delete book.holdings[symbol];
 }else{
  const n=Object.keys(book.holdings).length;
  if(book.holdings[symbol]||n>=config.maxPositions)return;
  const budget=book.cash*config.investFraction/
   Math.max(1,config.maxPositions-n);
  const units=budget/(price*(1+commission)),fee=units*price*commission;
  if(units<=0)return;
  book.cash-=units*price+fee;book.feeTotal+=fee;
  book.holdings[symbol]={units,entry:price};
  book.events.push({type:"FILL",side,symbol,date:bar.session,signalAt,price,
   units,fee,reason});
 }
}
function settleSession(book,methodRow,panel,config){
 const day=panel.asOf,barOf=s=>panel.bars[s].at(-1),risk=riskOf(methodRow.method);
 const exited=new Set();
 for(const symbol of Object.keys(book.holdings).sort()){
  const bar=barOf(symbol),holding=book.holdings[symbol];
  if(bar.split>0){
   holding.units*=bar.split;
   holding.entry/=bar.split;
   book.events.push({type:"SPLIT",date:day,symbol,factor:bar.split});
  }
  if(bar.dividend>0){
   const amount=holding.units*bar.dividend;
   book.cash+=amount;book.dividendTotal+=amount;
   book.events.push({type:"DIVIDEND",date:day,symbol,amount});
  }
  const stop=risk.stop===null?null:holding.entry*(1-risk.stop);
  const target=risk.target===null?null:holding.entry*(1+risk.target);
  if(stop!==null&&bar.open<=stop){
   recordFill(book,symbol,"SELL",bar,bar.open,config,"STOP_GAP");exited.add(symbol);
  }else if(target!==null&&bar.open>=target){
   recordFill(book,symbol,"SELL",bar,bar.open,config,"TARGET_GAP");exited.add(symbol);
  }
 }
 // The previous close is the only allowed origin of executable paper decisions.
 for(const symbol of Object.keys(book.orders).sort()){
  const order=book.orders[symbol],bar=barOf(symbol);
  if(order.side==="SELL"&&book.holdings[symbol]&&!exited.has(symbol))
   recordFill(book,symbol,"SELL",bar,bar.open,config,"PRIOR_CLOSE",order.signalAt);
 }
 for(const symbol of Object.keys(book.orders).sort()){
  const order=book.orders[symbol],bar=barOf(symbol);
  if(order.side==="BUY"&&!book.holdings[symbol]&&!exited.has(symbol))
   recordFill(book,symbol,"BUY",bar,bar.open,config,"PRIOR_CLOSE",order.signalAt);
 }
 book.orders={};
 for(const symbol of Object.keys(book.holdings).sort()){
  const bar=barOf(symbol),holding=book.holdings[symbol];
  const stop=risk.stop===null?null:holding.entry*(1-risk.stop);
  const target=risk.target===null?null:holding.entry*(1+risk.target);
  if(stop!==null&&bar.low<=stop){
   recordFill(book,symbol,"SELL",bar,stop,config,"STOP_INTRADAY_FIRST");
   exited.add(symbol);
  }else if(target!==null&&bar.high>=target){
   recordFill(book,symbol,"SELL",bar,target,config,"TARGET_INTRADAY");
   exited.add(symbol);
  }
 }
 return exited;
}

export function advancePaperCampaign(config,panel,previous=null){
 const {symbols,timeline}=validatePanel(panel);
 validatePaperConfig(config,symbols);
 let state=previous?structuredClone(previous):stateOf(config,panel);
 if(state.schema!==1||state.status!=="SYNTHETIC_PROSPECTIVE_ACCOUNTING_SANDBOX"||
   state.configuration!==JSON.stringify(config)||state.source!==panel.source||state.synthetic!==true||
   Object.keys(state.portfolios||{}).join(",")!==config.strategies.map(m=>m.id).join(","))
  throw Error("Changed campaign identity or strategy specification");
 const previousIndex=state.lastSession?timeline.indexOf(state.lastSession):-1;
 if(state.lastSession&&previousIndex<0)throw Error("Recorded session is missing from new source");
 if(state.lastSession===panel.asOf){
  const current=JSON.stringify(symbols.map(s=>panel.bars[s]));
  if(state.historyPrefix!==current)throw Error("Already registered bars were revised");
  return {state,changed:false};
 }
 if(previous&&previousIndex!==timeline.length-2)
  throw Error("Missing daily decisions: refuse retroactive entry signals");
 const currentIndex=timeline.length-1;
 if(previous){
  const old=JSON.stringify(symbols.map(s=>panel.bars[s].slice(0,currentIndex)));
  if(state.historyPrefix!==old)throw Error("Historical OHLC revised after decision");
 }
 for(const method of config.strategies){
  const book=state.portfolios[method.id];
  if(previous)settleSession(book,method,panel,config);
  const holdings=book.holdings;
  const nav=book.cash+Object.entries(holdings)
    .reduce((sum,[symbol,pos])=>sum+pos.units*panel.bars[symbol].at(-1).close,0);
  if(!valid(nav)||nav<=0||book.cash<-.0001)throw Error("Invalid paper balance");
  book.equity.push({session:panel.asOf,nav,cash:book.cash,positions:Object.keys(holdings).length});
  for(const symbol of method.symbols){
   const action=signalAtClose(method.method,panel.bars[symbol]);
   if(action==="BUY"&&!holdings[symbol]){
    book.orders[symbol]={side:"BUY",signalAt:panel.asOf};
    book.events.push({type:"SIGNAL",date:panel.asOf,symbol,side:action});
   }else if(action==="SELL"&&holdings[symbol]){
    book.orders[symbol]={side:"SELL",signalAt:panel.asOf};
    book.events.push({type:"SIGNAL",date:panel.asOf,symbol,side:action});
   }
  }
 }
 state.lastSession=panel.asOf;
 state.historyPrefix=JSON.stringify(symbols.map(s=>panel.bars[s]));
 return {state,changed:true};
}
export function campaignRanking(config,state){
 if(!state||state.status!=="SYNTHETIC_PROSPECTIVE_ACCOUNTING_SANDBOX"||
    state.configuration!==JSON.stringify(config))throw Error("Invalid campaign provenance");
 return config.strategies.map(method=>{
  const book=state.portfolios[method.id],latest=book.equity.at(-1);
  if(!latest)throw Error("No paper session");
  let peak=config.capital,worst=0;
  for(const point of book.equity){
   peak=Math.max(peak,point.nav);
   worst=Math.min(worst,100*(point.nav/peak-1));
  }
  return {id:method.id,method:method.method,status:"SYNTHETIC_ONLY",lastSession:latest.session,
   capital:config.capital,cash:book.cash,equity:latest.nav,
   returnPct:100*(latest.nav/config.capital-1),drawdownPct:worst,
   active:Object.keys(book.holdings),pending:Object.keys(book.orders),
   fills:book.events.filter(x=>x.type==="FILL").length,
   fees:book.feeTotal,dividends:book.dividendTotal};
 });
}

export function artificialCampaignComparison(){
 const observations=artificialMethodBars().map(b=>({...b,volume:100000,dividend:0,split:0}));
 const config={schema:1,currency:"USD",capital:100000,feeBps:10,slippageBps:5,
  investFraction:.95,maxPositions:1,
  strategies:methodCatalog.map((method,index)=>({id:"M-"+(index+10),method:method.id,symbols:["SIM-A"]}))};
 let state=null;
 for(let n=80;n<=observations.length;n++){
  const panel={source:"generated_research_ohlc_v1",synthetic:true,currency:"USD",
   asOf:observations[n-1].session,bars:{"SIM-A":observations.slice(0,n)}};
  state=advancePaperCampaign(config,panel,state).state;
 }
 return {class:"ARTIFICIAL_REPLAY_NOT_PROSPECTIVE",symbol:"SIM-A",
  sampleSessions:observations.length,measuredSessions:observations.length-79,
  config,ranking:campaignRanking(config,state),state};
}
