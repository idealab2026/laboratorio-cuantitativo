// Pure close-only policies. No network, positions, accounts or private datasets.
export function movingMean(values, period) {
  if (!Number.isInteger(period) || period < 2 || values.length < period) return null;
  return values.slice(-period).reduce((a,b)=>a+b,0)/period;
}
export function closePolicy(method, dailyBars) {
  if (!Array.isArray(dailyBars) || dailyBars.some(b=>!Number.isFinite(b.close)||b.close<=0)) throw Error("Invalid close history");
  const n=dailyBars.length, close=dailyBars.map(b=>b.close);
  if(method==="hold") return "BUY";
  if(method==="momentum20") {
    if(n<22) return "HOLD";
    const prior=movingMean(close.slice(0,-1),20), current=movingMean(close,20);
    return close[n-2]<=prior&&close[n-1]>current?"BUY":close[n-2]>=prior&&close[n-1]<current?"SELL":"HOLD";
  }
  if(method==="breakout20") {
    if(n<22) return "HOLD";
    const priorHigh=Math.max(...dailyBars.slice(-21,-1).map(x=>x.high));
    const priorLow=Math.min(...dailyBars.slice(-11,-1).map(x=>x.low));
    return close[n-1]>priorHigh?"BUY":close[n-1]<priorLow?"SELL":"HOLD";
  }
  throw Error("Unknown paper method");
}

// Deterministic technical indicators. All arrays end at the decision close.
const exponential=(prices,period)=>{
 const alpha=2/(period+1),out=[];
 for(const value of prices)out.push(out.length?alpha*value+(1-alpha)*out.at(-1):value);
 return out;
};
const strength=(prices,length)=>{
 if(prices.length<=length)return null;
 let up=0,down=0;
 for(let i=1;i<=length;i++){const d=prices[i]-prices[i-1];up+=Math.max(d,0)/length;down+=Math.max(-d,0)/length;}
 for(let i=length+1;i<prices.length;i++){const d=prices[i]-prices[i-1];up=(up*(length-1)+Math.max(d,0))/length;down=(down*(length-1)+Math.max(-d,0))/length;}
 return down===0?(up===0?50:100):100-100/(1+up/down);
};
const upCross=(oldX,oldY,newX,newY)=>oldX<=oldY&&newX>newY;
const downCross=(oldX,oldY,newX,newY)=>oldX>=oldY&&newX<newY;
export const methodCatalog=Object.freeze([
 {id:"hold",name:"Buy & hold",family:"Referencia",parameters:"Sin señales posteriores"},
 {id:"momentum20",name:"Media móvil 20",family:"Técnicas",parameters:"Cruce sobre la media 20"},
 {id:"emaRsi",name:"EMA 12/26 + RSI 14",family:"Técnicas",parameters:"Umbrales 30 / 70"},
 {id:"geneticFixed",name:"EMA 4/22 + RSI 6",family:"Modelo congelado",parameters:"Umbrales 20 / 72; sin reentrenamiento"},
 {id:"macd",name:"MACD 12/26/9",family:"Técnicas",parameters:"Cruce de línea MACD y señal"},
 {id:"rsiReversion",name:"RSI reversión 14",family:"Técnicas",parameters:"Entrada 30 / salida 55"},
 {id:"bollinger",name:"Bandas Bollinger 20",family:"Técnicas",parameters:"Ruptura superior / salida por media"},
 {id:"breakout20",name:"Ruptura 20 / 10",family:"Técnicas",parameters:"Máximos y mínimos previos"},
 {id:"breakout55",name:"Ruptura 55 / 20",family:"Técnicas",parameters:"Máximos y mínimos previos"}
]);
const idSet=new Set(methodCatalog.map(m=>m.id));
export function signalAtClose(method,bars){
 if(!idSet.has(method))throw Error("Unrecognized strategy identifier");
 if(!Array.isArray(bars)||bars.length<1||bars.some(b=>typeof b.close!=="number"||!Number.isFinite(b.close)||b.close<=0))
  throw Error("Invalid daily series");
 const close=bars.map(b=>b.close),n=close.length;
 if(method==="hold")return "BUY";
 if(method==="momentum20"||method==="breakout20")return closePolicy(method,bars);
 if(method==="breakout55"){
  if(n<57)return "HOLD";
  const ceiling=Math.max(...bars.slice(-56,-1).map(x=>x.high));
  const floor=Math.min(...bars.slice(-21,-1).map(x=>x.low));
  return close.at(-1)>ceiling?"BUY":close.at(-1)<floor?"SELL":"HOLD";
 }
 if(method==="emaRsi"||method==="geneticFixed"){
  const p=method==="emaRsi"?[12,26,14,30,70]:[4,22,6,20,72];
  if(n<(method==="emaRsi"?78:22))return "HOLD";
  const fast=exponential(close,p[0]),slow=exponential(close,p[1]);
  const r=strength(close,p[2]);
  if(r<p[3])return "SELL";
  return (method==="geneticFixed"?fast.at(-2)<slow.at(-2)&&fast.at(-1)>=slow.at(-1):
   upCross(fast.at(-2),slow.at(-2),fast.at(-1),slow.at(-1)))&&r<p[4]?"BUY":"HOLD";
 }
 if(method==="macd"){
  if(n<78)return "HOLD";
  const x=exponential(close,12),y=exponential(close,26),diff=x.map((v,i)=>v-y[i]),smooth=exponential(diff,9);
  return upCross(diff.at(-2),smooth.at(-2),diff.at(-1),smooth.at(-1))?"BUY":
   downCross(diff.at(-2),smooth.at(-2),diff.at(-1),smooth.at(-1))?"SELL":"HOLD";
 }
 if(method==="rsiReversion"){
  if(n<30)return "HOLD";
  const previous=strength(close.slice(0,-1),14),current=strength(close,14);
  return previous>=30&&current<30?"BUY":previous<=55&&current>55?"SELL":"HOLD";
 }
 if(method==="bollinger"){
  if(n<21)return "HOLD";
  const ranges=values=>{
   const window=values.slice(-20),m=window.reduce((a,b)=>a+b,0)/20;
   const variance=window.reduce((a,b)=>a+(b-m)**2,0)/20;
   return {mean:m,upper:m+2*Math.sqrt(variance)};
  };
  const old=ranges(close.slice(0,-1)),now=ranges(close);
  return upCross(close.at(-2),old.upper,close.at(-1),now.upper)?"BUY":
   downCross(close.at(-2),old.mean,close.at(-1),now.mean)?"SELL":"HOLD";
 }
 throw Error("Strategy catalog and evaluator disagree");
}
