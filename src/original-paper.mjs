const finite=x=>typeof x==="number"&&Number.isFinite(x);
const day=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&new Date(x+"T00:00:00Z").toISOString().slice(0,10)===x;
export function verifyOriginalPaper(doc,mapping){
 if(doc?.schema_version!==1||!Array.isArray(doc.tracks)||doc.tracks.length!==64||Object.keys(mapping).length!==64||!Number.isFinite(Date.parse(doc.generated_at_utc)))throw Error("Diario original incompleto");
 const seen=new Set(),bySlot=new Map(),labels=new Map();let latest="";
 for(const t of doc.tracks){
  const slot=mapping[t.id];if(!/^IL-\d{3}$/.test(slot||"")||seen.has(slot))throw Error("Identidad de estrategia no válida");seen.add(slot);
  if(typeof t.label!=="string"||!t.label.trim()||t.label.length>160)throw Error("Missing original strategy label");
  labels.set(slot,t.label);
  if(!Array.isArray(t.equity_history))throw Error("Histórico ausente");
  if(!t.equity_history.length){if(t.return_pct!==null||t.last_equity!==null)throw Error("Resultado atribuido sin diario");continue;}
  if(!["USD","EUR"].includes(t.currency)||!finite(t.initial_capital)||t.initial_capital<=0||!finite(t.last_equity)||t.last_equity<0||!finite(t.return_pct))throw Error("Contabilidad incompleta");
  let previous="";for(const p of t.equity_history){if(!day(p.date)||p.date<=previous||!finite(p.nav)||p.nav<0)throw Error("Curva no verificable");previous=p.date;}
  const last=t.equity_history.at(-1);
  if(t.first_session!==t.equity_history[0].date||t.last_session!==last.date||Math.abs(last.nav-t.last_equity)>0.00001||Math.abs(100*(t.last_equity/t.initial_capital-1)-t.return_pct)>0.0002)throw Error("NAV y rentabilidad no coinciden");
  for(const v of [t.day_return_pct,t.annualized_volatility_pct,t.max_drawdown_pct,t.sharpe_0rf])if(v!==null&&!finite(v))throw Error("Riesgo no finito");
  if(t.last_session>latest)latest=t.last_session;
  bySlot.set(slot,{activity:"Paper · "+(t.activity_label||"Diario registrado"),currency:t.currency,last_session:t.last_session,return_pct:t.return_pct,day_return_pct:t.day_return_pct,positions:t.open_positions_count,pending_orders:t.pending_orders_count,risk:{volatility_pct:t.annualized_volatility_pct,max_drawdown_pct:t.max_drawdown_pct,sharpe_0rf:t.sharpe_0rf},comparison:{eligible:t.comparison_eligible===true,universe_id:t.comparison_universe_id},history:t.equity_history,original:true});
 }
 if(seen.size!==64)throw Error("Inventario incompleto");
 return {bySlot,labels,count:bySlot.size,latest,generatedAt:doc.generated_at_utc};
}
