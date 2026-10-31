// IDEA LAB: independent, deterministic PAPER demonstration engine.
// Signals at session t use *only* observations up to t-1.
// No brokerage, external data, actual ML training or actual holdings.
export const finite = x => typeof x === "number" && Number.isFinite(x);
const MODES=new Set(["equal","cap","trend","reversion","lowvol","defensive","rank","cash","linear","direction","crossrank","perceptron","memory","ensemble","weekly","daily","cycle","value","dip","ladder","ahp","genetic","stress"]);
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
export function signal(mode,market,idx){
 const s=Object.values(market),m4=s.map(p=>returnAt(p,idx,4)),m9=s.map(p=>returnAt(p,idx,9));
 const vol=s.map(p=>Math.max(0.002,volatility(p,idx)));
 const gains=s.map(p=>p[idx]/Math.max(0.01,mean(p.slice(Math.max(0,idx-9),idx+1)))-1);
 const ranked=[0,1,2].sort((a,b)=>m4[b]-m4[a]);const top=ranked[0];
 const base=[1,1,1];
 switch(mode){
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
  case "crossrank":return [0,1,2].map(j=>j===ranked[0]?.75:j===ranked[1]?.25:0);
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
   const goal=signal(s.mode,data.market,t-1);
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
