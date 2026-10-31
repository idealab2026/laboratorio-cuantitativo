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
