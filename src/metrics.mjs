// IDEA LAB: independent, deterministic PAPER demonstration engine.
// Signals at session t use *only* observations up to t-1.
// No brokerage, external data, actual ML training or actual holdings.
export const finite = x => typeof x === "number" && Number.isFinite(x);
const MODES=new Set(["equal","cap","trend","reversion","lowvol","defensive","rank","cash","linear","direction","crossrank","perceptron","memory","ensemble","weekly","daily","cycle","value","dip","ladder","ahp","genetic","stress","manual"]);
export function verify(data){
 if(data?.meta?.data_class!=="synthetic")throw Error("Only synthetic sources admitted");
 if(!Array.isArray(data.dates)||data.dates.length<12||new Set(data.dates).size!==data.dates.length)throw Error("Invalid sessions");
 const symbols=Object.keys(data.market||{});
 if(symbols.length!==3||symbols.some(k=>!/^SIM-[A-Z]$/.test(k)))throw Error("Unsupported fictitious universe");
 for(const key of symbols){
  const p=data.market[key];
  if(!Array.isArray(p)||p.length!==data.dates.length||p.some(v=>!finite(v)||v<=0))throw Error("Incomplete fictitious prices");
 }
 if(!Array.isArray(data.strategies)||data.strategies.length<5)throw Error("Insufficient strategies");
 if(new Set(data.strategies.map(x=>x.id)).size!==data.strategies.length)throw Error("Duplicate strategy IDs");
 for(const s of data.strategies){
  if(!/^P-\d{2}$/.test(s.id)||!s.name||!s.rule||!s.group||!MODES.has(s.mode))throw Error("Incomplete strategy");
  if(!finite(s.cost_bps)||s.cost_bps<0||s.cost_bps>1000)throw Error("Invalid cost assumption");
 }
 if(!Array.isArray(data.theses)||new Set(data.theses.map(x=>x.id)).size!==data.theses.length)throw Error("Invalid theses");
 for(const t of data.theses){
  if(!t.id||!t.company||!t.thesis||!t.counter||!t.evidence||!t.catalysts||!t.method)throw Error("Incomplete thesis");
  if(!finite(t.price)||t.price<=0||!finite(t.cashflow)||t.cashflow<=0||!finite(t.requiredReturn)||t.requiredReturn<=0)throw Error("Invalid valuation inputs");
  for(const k of ["bear","base","bull"])if(!finite(t.growth?.[k])||!finite(t.multiples?.[k])||t.multiples[k]<=0)throw Error("Invalid valuation scenario");
 }
 return true;
}
export function cumulative(nav){if(!nav.length||!finite(nav[0])||nav[0]<=0||nav.some(x=>!finite(x)||x<=0))throw Error("Invalid NAV");return 100*(nav.at(-1)/nav[0]-1);}
export function maxDrawdown(nav){let peak=0,worst=0;for(const x of nav){if(!finite(x)||x<=0)throw Error("Invalid NAV");peak=Math.max(peak,x);worst=Math.max(worst,100*(1-x/peak));}return worst;}
export function changeSeries(nav){return nav.map((v,i)=>i===0?0:100*(v/nav[i-1]-1));}
export function formatPct(n){return finite(n)?new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"}).format(n)+" %":"N/D";}
export function money(n){return finite(n)?new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2}).format(n)+" ud.":"N/D";}
const clip=(x,lo=0,hi=1)=>Math.min(hi,Math.max(lo,x));
const mean=a=>a.reduce((s,x)=>s+x,0)/Math.max(a.length,1);
const deviations=a=>a.length>1?Math.sqrt(a.reduce((s,x)=>s+(x-mean(a))**2,0)/(a.length-1)):0;
function returnAt(prices,idx,lookback){
 if(idx-lookback<0)return 0;
 return prices[idx]/prices[idx-lookback]-1;
}
function volatility(prices,idx,lookback=8){
 const values=[];for(let i=Math.max(1,idx-lookback+1);i<=idx;i++)values.push(prices[i]/prices[i-1]-1);
 return deviations(values);
}
function weighted(raw,exposure=1){
 const positive=raw.map(x=>Math.max(0,finite(x)?x:0)),sum=positive.reduce((a,b)=>a+b,0);
 return sum>0?positive.map(x=>clip(exposure)*x/sum):[0,0,0];
}
export function signal(mode,market,idx,manualWeights=null){
 const s=Object.values(market),m4=s.map(p=>returnAt(p,idx,4)),m9=s.map(p=>returnAt(p,idx,9));
 const vol=s.map(p=>Math.max(0.002,volatility(p,idx)));
 const gains=s.map(p=>p[idx]/Math.max(0.01,mean(p.slice(Math.max(0,idx-9),idx+1)))-1);
 const ranked=[0,1,2].sort((a,b)=>m4[b]-m4[a]);const top=ranked[0];
 const base=[1,1,1];
 switch(mode){
  case "manual":{if(!Array.isArray(manualWeights)||manualWeights.length!==3||manualWeights.some(x=>!finite(x)||x<0)||manualWeights.reduce((a,b)=>a+b,0)>1.000001)throw Error("Invalid manual exposure");return [...manualWeights];}
  case "equal":return [1/3,1/3,1/3];
  case "cap":return [.65,.25,.10];
  case "trend":return weighted(m4.map(v=>Math.max(0,v+.008)));
  case "reversion":return weighted(m4.map(v=>Math.max(0,.018-v)));
  case "lowvol":return weighted(vol.map(v=>1/v));
  case "defensive":return weighted(vol.map(v=>1/v),.48);
  case "rank":return [0,1,2].map(j=>j===top?1:0);
  case "cash":return [0,0,0];
  case "linear":return weighted(m4.map((v,i)=>Math.max(0,.7*v+.3*m9[i]+.01)));
  case "direction":return weighted(m4.map(v=>v>0?1:0),.85);
  case "crossrank":return [0,1,2].map(j=>j===ranked[0] ? 0.75 : j===ranked[1] ? 0.25 : 0);
  case "perceptron":return weighted(m4.map((v,i)=>clip((1+Math.tanh(v*28-m9[i]*9))/2)));
  case "memory":return weighted(m9.map((v,i)=>Math.max(0,1+v*15+m4[i]*7)));
  case "ensemble":return weighted(m4.map((v,i)=>Math.max(0,1+v*8-m9[i]*3+1/(vol[i]*100))));
  case "weekly":return weighted(m9.map((v,i)=>Math.max(0,v+.3*m4[i]+.01)));
  case "daily":return weighted(m4.map(v=>Math.max(0,.02+v*.4)));
  case "cycle":return weighted(base.map((_,i)=>1+.6*Math.sin((idx+i*3)/9)));
  case "value":return weighted(gains.map(v=>Math.max(0,.025-v)));
  case "dip":return weighted(m4.map(v=>v<-.009?1:0),.7);
  case "ladder":return weighted(m9.map(v=>v<-.035?2:v<-.01?1:0),.8);
  case "ahp":return weighted(vol.map((v,i)=>.5/(v*100)+.3*(1+m4[i])+.2));
  case "genetic":return [.48,.32,.20]; // Fixed parameters, not trained evolutionary search.
  case "stress":return weighted(vol.map(v=>1/v),Math.max(...vol)>.03?.35:.8);
  default:throw Error("Unsupported mode");
 }
}
export function absentQuote(quote,requestedWeight){
 return !finite(quote)||quote<=0?{status:"PENDING_NO_VERIFIED_PRICE",executed:false,requestedWeight}:{
 status:"ELIGIBLE_SYNTHETIC",executed:true,requestedWeight};
}
export function simulate(data,strategy){
 verify(data);
 const s=typeof strategy==="string"?data.strategies.find(x=>x.id===strategy):strategy;
 if(!s||!data.strategies.some(x=>x.id===s.id))throw Error("Strategy absent");
 const symbols=Object.keys(data.market),cash=[];
 let equity=data.meta.initialCapital??100000;
 if(!finite(equity)||equity<=0)throw Error("Invalid starting capital");
 let weights=[0,0,0],fees=0;
 const points=[{session:data.dates[0],nav:100,equity}],orders=[];
 const initial=equity;
 const weeklyModes=new Set(["linear","direction","crossrank","perceptron","memory","ensemble","weekly","cycle","genetic"]);
 for(let t=1;t<data.dates.length;t++){
  const prev=Object.values(data.market).map(p=>p[t-1]);
  const current=Object.values(data.market).map(p=>p[t]);
  if([...prev,...current].some(x=>!finite(x)||x<=0))throw Error("Missing market quote: do not fabricate a NAV");
  if(t===1||!weeklyModes.has(s.mode)||(t-1)%5===0){
   const goal=signal(s.mode,data.market,t-1,s.manualWeights);
   if(goal.some(x=>!finite(x)||x<0)||goal.reduce((a,b)=>a+b,0)>1.000001)throw Error("Invalid target portfolio");
   const turnover=goal.reduce((a,w,i)=>a+Math.abs(w-weights[i]),0);
   if(turnover>1e-6){
    const cost=equity*turnover*s.cost_bps/10000;
    equity-=cost;fees+=cost;
    goal.forEach((w,i)=>{
     const delta=w-weights[i];
     if(Math.abs(delta)>1e-5){
      const mark=absentQuote(prev[i],w);
      if(!mark.executed)throw Error("Missing executable quote");
      orders.push({session:data.dates[t],symbol:symbols[i],action:delta>0?"BUY":"SELL",notional:Math.abs(delta)*equity,units:Math.abs(delta)*equity/prev[i],referencePrice:prev[i],status:"SIMULATED",cost:cost*Math.abs(delta)/turnover});
     }
    });
   }
   weights=goal;
  }
  const returns=prev.map((p,i)=>current[i]/p-1);
  const gross=weights.reduce((total,w,i)=>total+w*returns[i],0);
  const before=weights;const factor=1+gross;
  if(factor<=0)throw Error("Insolvent synthetic portfolio");
  equity*=factor;
  weights=before.map((w,i)=>w*(1+returns[i])/factor);
  const nav=100*equity/initial;
  cash.push(1-weights.reduce((a,b)=>a+b,0));
  points.push({session:data.dates[t],nav,equity});
 }
 const nav=points.map(p=>p.nav),returns=changeSeries(nav).slice(1).map(v=>v/100);
 const volatilityPct=returns.length>1?deviations(returns)*Math.sqrt(252)*100:null;
 const sharpe=returns.length>1&&deviations(returns)>0?mean(returns)/deviations(returns)*Math.sqrt(252):null;
 return {...s,nav,points,orders,weights,cash:cash.at(-1)??1,fees,returnPct:cumulative(nav),drawdownPct:maxDrawdown(nav),volatilityPct,sharpe,sessions:points.length,coverage:100,status:"SIMULATED_ONLY"};
}
export function rank(data,sortKey="returnPct",ascending=false,group=""){
 verify(data);
 const all=data.strategies.filter(s=>!group||s.group===group).map(s=>simulate(data,s));
 const numeric=new Set(["returnPct","drawdownPct","volatilityPct","sharpe","fees","sessions","coverage"]);
 return all.sort((a,b)=>{
  const va=a[sortKey],vb=b[sortKey];
  if(numeric.has(sortKey))return ((finite(va)?va:Infinity)-(finite(vb)?vb:Infinity))*(ascending?1:-1)||a.name.localeCompare(b.name,"es");
  return (String(va??"").localeCompare(String(vb??""),"es"))*(ascending?1:-1)||a.name.localeCompare(b.name,"es");
 });
}
export function valuation(thesis){
 if(!thesis||!finite(thesis.price)||thesis.price<=0||!finite(thesis.cashflow)||thesis.cashflow<=0)throw Error("Invalid thesis");
 const v={};
 for(const key of ["bear","base","bull"]){
  const g=thesis.growth[key]/100,m=thesis.multiples[key],r=thesis.requiredReturn/100;
  if(!finite(g)||g<=-1||!finite(m)||m<=0||!finite(r)||r<=0)throw Error("Invalid scenario");
  const fair=thesis.cashflow*(1+g)**5*m/(1+r)**5;
  const compound=((fair/thesis.price)**(1/5)-1)*100;
  v[key]={fair,compound,marginPct:100*(fair/thesis.price-1)};
 }
 return {...thesis,valuation:v,central:v.base.compound,discountPct:v.base.marginPct};
}
export function thesisRank(data,key="central",direction="desc",query=""){
 verify(data);
 const q=query.trim().toLocaleLowerCase("es");
 const result=data.theses.map(valuation).filter(t=>!q||[t.company,t.sector,t.method,t.status,t.id,t.thesis].join(" ").toLocaleLowerCase("es").includes(q));
 result.sort((a,b)=>{
  const va=a[key],vb=b[key];
  let score=(finite(va)&&finite(vb)?va-vb:String(va??"").localeCompare(String(vb??""),"es"));
  return (direction==="asc"?score:-score)||a.company.localeCompare(b.company,"es");
 });
 return result;
}


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
  if(issuer.secCik!==undefined&&!/^\d{10}$/.test(issuer.secCik))throw Error("Invalid source registry identifier");
  if(!financialFields.every(field=>isBlank(issuer[field])))throw Error("Unverified financial claims in public catalogue");
  if(issuer.status!=="Pendiente de investigación pública")throw Error("Unverified editorial status");
 }
 if(data.publicScreens!==undefined){
  if(!Array.isArray(data.publicScreens)||data.publicScreens.length>3)throw Error("Invalid independent-screen list");
  const covered=new Set();
  for(const screen of data.publicScreens){
   if(covered.has(screen.ticker)||!seen.has(screen.ticker))throw Error("Unknown or duplicate public issuer screen");
   covered.add(screen.ticker);
   evaluateIssuerScreen(screen);
  }
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


// Separate, experimental next-session-open paper ledger. Never execute at the signal close.
// Public research demonstration only: bars are explicitly generated from synthetic inputs.
export function syntheticBarsFromDemo(data){
 verify(data);
 const symbols=Object.keys(data.market);
 return symbols.map((symbol,i)=>({
  symbol,
  bars:data.dates.map((session,t)=>{
   const close=data.market[symbol][t];
   const open=t===0?close:data.market[symbol][t-1]*(1+0.0018*Math.sin((t+1)*(i+2)));
   return {session,open,high:Math.max(open,close)*1.005,low:Math.min(open,close)*.995,close};
  })
 }));
}
function checkedBar(b){
 return b&&["open","high","low","close"].every(key=>finite(b[key])&&b[key]>0)
  && b.low<=Math.min(b.open,b.close) && b.high>=Math.max(b.open,b.close)
  && b.high>=b.low && typeof b.session==="string" && b.session.length>0;
}
export function nextOpenPaper(input,{rule="equal",initialCapital=100000,feeBps=10,slippageBps=5,lookback=4}={}){
 if(!Array.isArray(input)||input.length<1||input.length>20)throw Error("Invalid instrument count");
 if(!["equal","trend","cash"].includes(rule)||!Number.isInteger(lookback)||lookback<2||lookback>90)throw Error("Invalid strategy policy");
 if(!finite(initialCapital)||initialCapital<=0||!finite(feeBps)||feeBps<0||feeBps>100||!finite(slippageBps)||slippageBps<0||slippageBps>20)throw Error("Invalid cash or costs");
 const size=input[0]?.bars?.length;
 if(!Number.isInteger(size)||size<3||size>5000)throw Error("Invalid market history");
 const symbols=input.map(row=>row.symbol);
 if(new Set(symbols).size!==symbols.length||symbols.some(x=>typeof x!=="string"||!/^SIM-[A-Z]$/.test(x)))throw Error("Only independent synthetic symbols are allowed");
 const dates=input[0].bars.map(b=>b.session);
 if(new Set(dates).size!==size)throw Error("Duplicate sessions");
 for(const stream of input){
  if(!Array.isArray(stream.bars)||stream.bars.length!==size)throw Error("Unequal histories");
  stream.bars.forEach((bar,t)=>{
   if(!checkedBar(bar)||bar.session!==dates[t])throw Error("Missing, inconsistent or untradeable OHLC");
  });
 }
 let cash=initialCapital,shares=Array(input.length).fill(0),totalFees=0,totalSlippage=0;
 const orders=[],points=[{session:dates[0],nav:100,equity:initialCapital,cash,signalAt:null}];
 for(let t=1;t<size;t++){
  const signalAt=dates[t-1],fillAt=dates[t];
  const target=Array(input.length).fill(0);
  if(rule==="equal")target.fill(1/input.length);
  if(rule==="trend"&&t-1>=lookback){
   const strengths=input.map(row=>Math.max(0,row.bars[t-1].close/row.bars[t-1-lookback].close-1));
   const total=strengths.reduce((a,b)=>a+b,0);
   if(total>0)strengths.forEach((v,i)=>target[i]=v/total);
  }
  const open=input.map(row=>row.bars[t].open);
  const preEquity=cash+shares.reduce((sum,qty,i)=>sum+qty*open[i],0);
  if(!finite(preEquity)||preEquity<=0)throw Error("Invalid pretrade value");
  const desired=target.map((w,i)=>preEquity*w/open[i]);
  function record(i,side,qty){
   if(qty<=1e-10)return;
   const sign=side==="BUY"?1:-1,fill=open[i]*(1+sign*slippageBps/10000);
   if(fill<input[i].bars[t].low-1e-8||fill>input[i].bars[t].high+1e-8)throw Error("Synthetic fill outside OHLC bounds");
   const notional=qty*fill,fee=notional*feeBps/10000,slip=qty*Math.abs(fill-open[i]);
   if(side==="BUY"){shares[i]+=qty;cash-=notional+fee;}
   else{shares[i]-=qty;cash+=notional-fee;}
   totalFees+=fee;totalSlippage+=slip;
   orders.push({signalAt,fillAt,symbol:symbols[i],side,units:qty,openPrice:open[i],fillPrice:fill,notional,fee,slippage:slip,status:"PAPER_NEXT_OPEN"});
  }
  // Disposals precede purchases, to make a cash-only portfolio feasible.
  shares.forEach((qty,i)=>{if(qty>desired[i]+1e-10)record(i,"SELL",qty-desired[i]);});
  const needs=shares.map((qty,i)=>Math.max(0,desired[i]-qty));
  const required=needs.reduce((sum,qty,i)=>sum+qty*open[i]*(1+slippageBps/10000)*(1+feeBps/10000),0);
  const scale=required>0?Math.min(1,Math.max(0,cash)/required):0;
  needs.forEach((qty,i)=>record(i,"BUY",qty*scale));
  if(cash<-1e-7)throw Error("Insufficient cash or hidden leverage");
  if(cash<0)cash=0;
  const equity=cash+shares.reduce((sum,qty,i)=>sum+qty*input[i].bars[t].close,0);
  if(!finite(equity)||equity<=0)throw Error("Invalid closing equity");
  points.push({session:fillAt,nav:100*equity/initialCapital,equity,cash,signalAt});
 }
 const nav=points.map(x=>x.nav);
 const gains=changeSeries(nav).slice(1).map(x=>x/100);
 const sd=deviations(gains);
 return {status:"PAPER_SYNTHETIC_NEXT_OPEN",rule,feeBps,slippageBps,
  signalTiming:"PREVIOUS_SESSION_CLOSE",fillTiming:"NEXT_SESSION_OPEN",
  points,orders,shares,cash,fees:totalFees,slippage:totalSlippage,
  returnPct:cumulative(nav),drawdownPct:maxDrawdown(nav),
  volatilityPct:gains.length>1?sd*Math.sqrt(252)*100:null,
  sharpe:sd>0?mean(gains)/sd*Math.sqrt(252):null};
}


// Narrow, separately sourced public screening. Do not convert an exploratory
// EPS sensitivity into a ratified DCF, independent price target or live quote.
export function evaluateIssuerScreen(screen){
 if(!screen||screen.ticker!=="MSFT"||screen.status!=="EXPLORATORY_NOT_RATIFIED"||screen.horizonYears!==5)
  throw Error("Unratified or unsupported issuer research");
 const mustBe=[
  ["quote.close",screen.quote?.close],["metric.adjustedEpsFY2026",screen.metric?.adjustedEpsFY2026],
  ["catalyst.q1FY2027RevenueBillion",screen.catalyst?.q1FY2027RevenueBillion],
  ["catalyst.azureGrowthYoyPct",screen.catalyst?.azureGrowthYoyPct]
 ];
 if(mustBe.some(([,value])=>!finite(value)||value<=0))throw Error("Invalid public screening input");
 if(screen.quote.currency!=="USD"||screen.quote.closeDate!=="2026-10-30"||screen.asOf!=="2026-10-31"||screen.catalyst.date!=="2026-10-28")
  throw Error("Missing dated source");
 if(screen.quote.source!=="https://stockanalysis.com/stocks/msft/history/"
   ||screen.metric.source!=="https://www.microsoft.com/investor/reports/ar26/"
   ||screen.catalyst.source!=="https://www.microsoft.com/en-us/Investor/earnings/FY-2027-Q1/press-release-webcast")
  throw Error("Unexpected screening evidence");
 if(typeof screen.method!=="string"||screen.method.length<30||typeof screen.limitations!=="string"||screen.limitations.length<120)
  throw Error("Incomplete model disclosure");
 const output={};
 for(const key of ["bear","base","bull"]){
  const assumptions=screen.assumptions?.[key],growth=assumptions?.annualEpsGrowthPct,multiple=assumptions?.terminalPe;
  if(!finite(growth)||growth<0||growth>30||!finite(multiple)||multiple<5||multiple>60)throw Error("Invalid screening assumptions");
  const estimatedEps=screen.metric.adjustedEpsFY2026*(1+growth/100)**screen.horizonYears;
  const target=estimatedEps*multiple;
  output[key]={growthPct:growth,terminalPe:multiple,estimatedEps,target,cagrPct:100*((target/screen.quote.close)**(1/screen.horizonYears)-1)};
 }
 if(!(output.bear.target<output.base.target&&output.base.target<output.bull.target))
  throw Error("Unordered public scenarios");
 return {...screen,scenarios:output,buyPrice15:output.base.target/1.15**screen.horizonYears};
}


// Public read-model only. All returns are artificial, and different histories
// must never be compared as if they shared the same calendar.
export function competitionReadModel(data,filters={}){
 const sort=filters.sort||"returnPct",ascending=filters.ascending===true,group=filters.group||"";
 const allowed=new Set(["name","group","activity","assets","returnPct","dayReturnPct","sessions","lastSession","drawdownPct","volatilityPct","sharpe"]);
 if(!allowed.has(sort))throw Error("Unsupported competition sort");
 const rows=rank(data,"name",true,group).map(item=>{
  const active=Object.keys(data.market).filter((k,i)=>item.weights[i]>0.005);
  const dayReturnPct=item.nav.length>1?100*(item.nav.at(-1)/item.nav.at(-2)-1):null;
  const windowPct=(period)=>item.nav.length>period?100*(item.nav.at(-1)/item.nav.at(-1-period)-1):null;
  return {...item,activity:item.orders.length===0?"Sin órdenes":"Órdenes paper: "+item.orders.length,
   assets:active.join(", "),activeAssets:active,dayReturnPct,
   lastSession:data.dates.at(-1),periodReturns:{five:windowPct(5),twentyOne:windowPct(21),sixtyThree:windowPct(63)},
   experimentStatus:"SIMULACION_SINTETICA",executionVerified:false,marketDataVerified:false};
 });
 const numeric=new Set(["returnPct","dayReturnPct","sessions","drawdownPct","volatilityPct","sharpe"]);
 const value=r=>sort==="name"?r.name:sort==="group"?r.group:sort==="activity"?r.orders.length:sort==="assets"?r.activeAssets.length:r[sort];
 const sortNumeric=numeric.has(sort)||["activity","assets"].includes(sort);
 return rows.sort((a,b)=>{
  const x=value(a),y=value(b);
  const missingA=x===null||x===undefined||x===""||sortNumeric&&!finite(x);
  const missingB=y===null||y===undefined||y===""||sortNumeric&&!finite(y);
  if(missingA!==missingB)return missingA?1:-1;
  const comparison=missingA?0:sortNumeric?x-y:String(x).localeCompare(String(y),"es",{numeric:true,sensitivity:"base"});
  return (ascending?comparison:-comparison)||a.name.localeCompare(b.name,"es");
 });
}
export function publicIssuerReadModel(data,{query="",sort="base",ascending=false}={}){
 verifyIssuerCatalog(data);
 const columns=new Set(["ticker","company","market","price","bear","base","bull","entry","target","earnings","report"]);
 if(!columns.has(sort))throw Error("Unsupported issuer sort");
 const matched=data.issuers.filter(i=>[i.ticker,i.company,i.market,i.sector].join(" ").toLocaleLowerCase("es").includes(String(query).trim().toLocaleLowerCase("es")));
 const rows=matched.map(i=>({issuer:i,screen:data.publicScreens?.find(s=>s.ticker===i.ticker)||null}))
  .map(row=>({...row,screen:row.screen?evaluateIssuerScreen(row.screen):null}));
 const value=r=>{
  const i=r.issuer,s=r.screen;
  switch(sort){
   case "ticker":return i.ticker;
   case "company":return i.company;
   case "market":return i.market;
   case "price":return s?.quote.close??null;
   case "bear":return s?.scenarios.bear.cagrPct??null;
   case "base":return s?.scenarios.base.cagrPct??null;
   case "bull":return s?.scenarios.bull.cagrPct??null;
   case "entry":return s?.buyPrice15??null;
   case "target":return s?.scenarios.base.target??null;
   case "earnings":return null; // No verified future financial-reporting dates in public feed.
   case "report":return null; // No institutional company reports approved for publication.
   default:throw Error("Sort out of bounds");
  }
 };
 const textual=new Set(["ticker","company","market","earnings"]);
 return rows.sort((a,b)=>{
  const x=value(a),y=value(b);
  const emptyA=x===null||x===undefined||x==="",emptyB=y===null||y===undefined||y==="";
  if(emptyA!==emptyB)return emptyA?1:-1;
  const diff=emptyA?0:textual.has(sort)?String(x).localeCompare(String(y),"es",{numeric:true}):x-y;
  return (ascending?diff:-diff)||a.issuer.ticker.localeCompare(b.issuer.ticker,"es");
 });
}


// Public ECB observations are informational. They are not tradable execution marks,
// equity OHLC candles, portfolio valuations, or broker evidence.
export function verifyOfficialFx(doc,now=new Date()){
 const source="https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=80&format=csvdata";
 if(doc?.status!=="verified_observations" || doc.data_class!=="official_fx_reference_only" ||
    doc.series!=="D.USD.EUR.SP00.A" || doc.source!=="European Central Bank (ECB statistics)" ||
    doc.source_url!==source || doc.quote_currency!=="USD" || doc.base_currency!=="EUR" ||
    doc.not_tradable!==true || typeof doc.notice!=="string" || !doc.notice.includes("NOT a transaction"))
  throw Error("No independently verified ECB reference-data contract");
 if(!/^[a-f0-9]{64}$/.test(doc.source_sha256||"") || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(doc.received_at_utc||""))
  throw Error("Missing ECB provenance, source digest or arrival time");
 if(!Array.isArray(doc.observations) || doc.count!==doc.observations.length || doc.count<15||doc.count>100)
  throw Error("Invalid ECB observation coverage");
 const at=Date.parse(doc.received_at_utc),time=now.getTime();
 if(!Number.isFinite(at)||at>time+60_000)throw Error("ECB observations stamped in the future");
 let previous=null;
 for(const row of doc.observations){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(row.date||"") || !/^\d+\.\d{1,8}$/.test(row.usd_per_eur||""))
   throw Error("Invalid ECB observation literal");
  const d=Date.parse(row.date+"T00:00:00Z"),rate=Number(row.usd_per_eur);
  if(!Number.isFinite(d)||d>time||![1,2,3,4,5].includes(new Date(d).getUTCDay())||rate<.6||rate>2)
   throw Error("Unverified ECB daily fixing");
  if(previous!==null&&(d<=previous||d-previous>8*86400000))throw Error("ECB gaps or duplicates");
  previous=d;
 }
 if(doc.latest_observation!==doc.observations.at(-1).date)throw Error("ECB latest date differs");
 return {rate:Number(doc.observations.at(-1).usd_per_eur),date:doc.latest_observation,
  count:doc.count,receivedAt:doc.received_at_utc,
  ageDays:Math.floor((time-previous)/86400000),referenceOnly:true};
}


// Read-model for source-gated, explicitly non-tradable prospective forecast events.
// The stronger SHA-256 event-chain audit runs in CI using scripts/advance_fx.py.
export function summarizeFxForecastLedger(data){
 if(!data||data.schema!=="idea_lab_fx_forecast_events_v1"||
   data.data_class!=="prospective_reference_forecasts_not_trades"||
   data.series!=="D.USD.EUR.SP00.A"||
   data.source!=="European Central Bank (ECB statistics)"||
   data.notice!=="Prospective forecasts of ECB reference fixings only. No executable fills, investment P&L or broker positions."||
   !Array.isArray(data.events)||data.events.length>10000)
  throw Error("No independently verified FX forecast ledger");
 const models=["unchanged","momentum_1","reversal_1"];
 const seen=new Set(),issued=new Map(),resolutions=new Map(),invalidations=new Map(),inconsistent=new Set();
 let previous="0".repeat(64);
 for(const event of data.events){
  if(!event||!["issued","resolved","invalidated"].includes(event.event_type)||
     !/^[a-f0-9]{64}$/.test(event.hash||"")||
     !/^[a-f0-9]{64}$/.test(event.source_sha256||"")||
     event.previous_hash!==previous||
     !/^\d{4}-\d\d-\d\d$/.test(event.fixing_date||"")||
     !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(event.recorded_at_utc||""))
    throw Error("Forecast lineage absent or malformed");
  if(event.event_type==="issued"){
   if(seen.has(event.fixing_date)||!event.predictions||
      !/^\d+\.\d{1,8}$/.test(event.observed_rate||"")||
      !models.every(k=>/^\d+\.\d{1,8}$/.test(event.predictions[k]||""))||
      Object.keys(event.predictions).length!==3)throw Error("Invalid issued forecast");
   seen.add(event.fixing_date);issued.set(event.hash,event);
   const reference=Number(event.observed_rate),b=Number(event.predictions.unchanged);
   if(Math.abs(reference-b)>0.0000005 ||
      Math.abs(Number(event.predictions.momentum_1)+Number(event.predictions.reversal_1)-2*reference)>0.0000021)
     inconsistent.add(event.hash);
  }else if(event.event_type==="invalidated"){
   const original=issued.get(event.signal_hash);
   if(!original||original.fixing_date!==event.fixing_date||invalidations.has(event.signal_hash)||
      resolutions.has(event.signal_hash)||!inconsistent.has(event.signal_hash)||
      event.reason!=="prediction_input_order_bug_v1")
    throw Error("Unsupported prospective forecast invalidation");
   invalidations.set(event.signal_hash,event);
  }else{
   const original=issued.get(event.signal_hash);
   if(!original||resolutions.has(event.signal_hash)||invalidations.has(event.signal_hash)||
     original.fixing_date!==event.fixing_date||!(event.realized_fixing_date>event.fixing_date)||
     !/^\d+\.\d{1,8}$/.test(event.realized_rate||"")||
     !event.absolute_errors||Object.keys(event.absolute_errors).length!==3||
     !models.every(k=>Math.abs(Number(event.absolute_errors[k])-Math.abs(Number(original.predictions[k])-Number(event.realized_rate)))<.0000011))
    throw Error("Invalid forecast score or duplicate settlement");
   resolutions.set(event.signal_hash,event);
  }
  previous=event.hash;
 }
 if(inconsistent.size!==invalidations.size || [...inconsistent].some(x=>!invalidations.has(x)))
  throw Error("Distorted signals must be explicitly invalidated");
 const rows=[...issued.values()].map(i=>({issued:i,settled:resolutions.get(i.hash)||null,invalidated:invalidations.has(i.hash)}));
 const scored=[...resolutions.values()];
 const mae=Object.fromEntries(models.map(k=>[k,scored.length?scored.reduce((sum,e)=>sum+Number(e.absolute_errors[k]),0)/scored.length:null]));
 return {rows,modelMAE:mae,issuedCount:rows.length,validCount:rows.length-invalidations.size,
  invalidatedCount:invalidations.size,resolvedCount:scored.length,
  unresolvedCount:rows.length-invalidations.size-scored.length,headHash:previous};
}


// Public issuer filings are SEC metadata, NOT prices, investment theses, or earnings forecasts.
export function verifySecFilings(doc,catalog){
 verifyIssuerCatalog(catalog);
 const fixed={"schema":"sec_filing_catalog_v1","data_class":"official_sec_filings_only",
  "source":"U.S. Securities and Exchange Commission (EDGAR submissions)",
  "notice":"Official filing metadata only. NOT audited financial calculations, a stock price, or an approved investment thesis."};
 if(!doc||Object.entries(fixed).some(([k,v])=>doc[k]!==v))throw Error("Invalid SEC source category");
 if(doc.status==="not_collected"){
  if(doc.generated_at_utc!==null||!Array.isArray(doc.issuers)||doc.issuers.length!==0)
   throw Error("Uncollected SEC metadata cannot include issuer documents");
  return {status:"not_collected",byTicker:new Map(),count:0,generatedAt:null};
 }
 if(doc.status!=="verified_filings"||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(doc.generated_at_utc||""))
  throw Error("No source-verified SEC collection");
 const mapped=catalog.issuers.filter(i=>i.secCik);
 if(!Array.isArray(doc.issuers)||doc.issuers.length!==mapped.length)
  throw Error("Unverified SEC collection coverage");
 const byTicker=new Map();
 let count=0;
 for(const issuer of doc.issuers){
  const source=mapped.find(i=>i.ticker===issuer.ticker);
  if(!source||source.secCik!==issuer.cik||byTicker.has(issuer.ticker)||
     issuer.source_url!=="https://data.sec.gov/submissions/CIK"+issuer.cik+".json"||
     !/^[a-f0-9]{64}$/.test(issuer.source_sha256||"")||
     !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(issuer.retrieved_at_utc||"")||
     !Array.isArray(issuer.filings)||issuer.filings.length<2||issuer.filings.length>12)
    throw Error("SEC issuer identity or provenance invalid");
  const seen=new Set();
  for(const filing of issuer.filings){
   if(!["10-K","10-Q","8-K"].includes(filing.form)||
      !/^\d{10}-\d\d-\d{6}$/.test(filing.accession||"")||
      !/^\d{4}-\d\d-\d\d$/.test(filing.filed||"")||
      (filing.report_date!==null&&!/^\d{4}-\d\d-\d\d$/.test(filing.report_date||""))||
      !/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/.test(filing.primary_document||"")||
      filing.primary_document.includes("..")||seen.has(filing.accession))
     throw Error("Unsafe SEC filing metadata");
   seen.add(filing.accession);
   const url="https://www.sec.gov/Archives/edgar/data/"+Number(issuer.cik)+"/"+filing.accession.replaceAll("-","")+"/"+filing.primary_document;
   if(filing.url!==url)throw Error("SEC document URL outside official archive");
  }
  if(!issuer.filings.some(x=>x.form==="10-K")||!issuer.filings.some(x=>x.form==="10-Q"))
   throw Error("Missing required source forms");
  byTicker.set(issuer.ticker,issuer);
  count+=issuer.filings.length;
 }
 return {status:"verified_filings",byTicker,count,generatedAt:doc.generated_at_utc};
}
