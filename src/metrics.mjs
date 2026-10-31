// Independent mathematical functions; no connection to external systems.
export const finite = x => typeof x === "number" && Number.isFinite(x);
export function verify(data){
  if(!data || data.meta?.data_class!=="synthetic") throw new Error("Dataset not admitted: synthetic-only demo");
  if(!Array.isArray(data.dates) || data.dates.length<3 || new Set(data.dates).size!==data.dates.length) throw new Error("Invalid time axis");
  if(!Array.isArray(data.strategies) || data.strategies.length<2) throw new Error("Missing comparisons");
  if(new Set(data.strategies.map(x=>x.id)).size!==data.strategies.length) throw new Error("Duplicate strategy");
  for(const s of data.strategies){
    if(!/^P-\d+$/.test(s.id)||!s.name||!s.rule) throw new Error("Invalid strategy contract");
    if(!Array.isArray(s.nav)||s.nav.length!==data.dates.length||s.nav.some(x=>!finite(x)||x<=0)) throw new Error("Incomplete NAV");
    if(!finite(s.cost_bps)||s.cost_bps<0||!finite(s.coverage)||s.coverage<0||s.coverage>100) throw new Error("Invalid costs or coverage");
  }
  if(!Array.isArray(data.theses)||data.theses.some(t=>!t.id||!t.hypothesis||!t.counter||!t.test||!t.evidence)) throw new Error("Incomplete thesis protocol");
  return true;
}
export function cumulative(nav){if(!nav?.length||nav[0]<=0)throw Error("Invalid NAV");return (nav.at(-1)/nav[0]-1)*100;}
export function maxDrawdown(nav){let high=-Infinity, worst=0;for(const x of nav){if(!finite(x)||x<=0)throw Error("Invalid NAV");high=Math.max(high,x);worst=Math.max(worst,(high-x)/high);}return worst*100;}
export function changeSeries(nav){return nav.map((v,i)=>i===0?0:100*(v/nav[i-1]-1));}
export function table(data){verify(data);return data.strategies.map(s=>({...s,returnPct:cumulative(s.nav),drawdownPct:maxDrawdown(s.nav),sessions:s.nav.length})).sort((a,b)=>b.returnPct-a.returnPct);}
export function formatPct(value){return new Intl.NumberFormat("es-ES",{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"}).format(value)+" %";}
