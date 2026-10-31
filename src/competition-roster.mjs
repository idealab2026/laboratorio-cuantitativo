// Contract for an independently operated institutional MIDAS strategy catalogue.
// No network requests, user-account data, provider authorizations or trade simulation.
const IDENTIFIER=/^IL-\d{3}$/;
const DAY=/^\d{4}-\d\d-\d\d$/;
const HEX=/^[0-9a-f]{64}$/;
const safeNumber=v=>v===null||(typeof v==="number"&&Number.isFinite(v));
const optionalDay=v=>v===null||(typeof v==="string"&&DAY.test(v)&&Number.isFinite(Date.parse(v+"T00:00:00Z")));
const nullMetrics=entry=>entry.currency===null&&entry.first_session===null&&entry.last_session===null&&
  entry.initial_capital===null&&entry.last_equity===null&&entry.return_pct===null&&
  entry.day_return_pct===null&&Object.values(entry.risk).every(x=>x===null)&&
  entry.positions===null&&entry.pending_orders===null&&entry.history.length===0&&
  entry.comparison.eligible===false&&entry.comparison.universe_id===null;
export function verifyFullRoster(doc){
 if(!doc||doc.schema!=="idea_lab_strategy_coverage_v1"||
    doc.data_class!=="institutional_registry_without_market_results"||
    doc.notice!=="Functional slots only. No live ledger, trade, prices, inferred returns or imported private research history."||
    doc.expected!==64||!Array.isArray(doc.entries)||doc.entries.length!==64)
  throw Error("Wrong institutional strategy register");
 const seen=new Set(),groups=new Map();
 const sourceKeys=["slot","group","name","record_status","activity","currency","first_session","last_session",
  "initial_capital","last_equity","return_pct","day_return_pct","risk","positions","pending_orders","history","comparison"];
 for(const item of doc.entries){
  if(!item||Object.keys(item).sort().join("|")!==[...sourceKeys].sort().join("|")||
     !IDENTIFIER.test(item.slot||"")||seen.has(item.slot)||
     typeof item.name!=="string"||item.name.length<2||item.name.length>100||
     typeof item.group!=="string"||item.group.length<2||item.group.length>100||
     !["not_migrated","verified_institutional"].includes(item.record_status)||
     !["unavailable","pending","cash","active","paused","error"].includes(item.activity))
    throw Error("Unknown strategy identity or lifecycle");
  seen.add(item.slot);groups.set(item.group,(groups.get(item.group)||0)+1);
  if(!item.risk||Object.keys(item.risk).sort().join("|")!==
      ["volatility_pct","max_drawdown_pct","sharpe_0rf"].sort().join("|")||
     !Object.values(item.risk).every(safeNumber)||
     !item.comparison||Object.keys(item.comparison).sort().join("|")!==["eligible","universe_id"].sort().join("|")||
     typeof item.comparison.eligible!=="boolean"||
     !(item.comparison.universe_id===null||typeof item.comparison.universe_id==="string")||
     !optionalDay(item.first_session)||!optionalDay(item.last_session)||
     !["USD","EUR",null].includes(item.currency)||
     ![item.initial_capital,item.last_equity,item.return_pct,item.day_return_pct].every(safeNumber)||
     !(item.positions===null||Number.isInteger(item.positions)&&item.positions>=0)||
     !(item.pending_orders===null||Number.isInteger(item.pending_orders)&&item.pending_orders>=0)||
     !Array.isArray(item.history)||item.history.length>2000)
    throw Error("Untrusted or non-finite portfolio fields");
  if(item.record_status==="not_migrated"){
   if(item.activity!=="unavailable"||!nullMetrics(item))throw Error("Unmigrated strategy cannot report returns or positions");
  }else{
   // Prevent false verification through a static fixture: production operation
   // requires a separate signed institutional ledger and effective data rights.
   throw Error("Verified live ledgers require an independent source adapter; not supported by this public-only file");
  }
 }
 const required=[9,9,9,9,1,1,1,2,2,1,4,16].sort((a,b)=>a-b);
 const found=[...groups.values()].sort((a,b)=>a-b);
 if(JSON.stringify(required)!==JSON.stringify(found))throw Error("Incomplete strategy-family coverage");
 return {count:seen.size,groups:[...groups].map(([name,count])=>({name,count})),
  migrated:0,active:0,withReturns:0};
}
export function filterRoster(doc,{group="",query=""}={}){
 verifyFullRoster(doc);
 const q=String(query).trim().toLocaleLowerCase("es");
 return doc.entries.filter(x=>(!group||x.group===group)&&
  (!q||[x.slot,x.group,x.name].some(v=>v.toLocaleLowerCase("es").includes(q))));
}

/* Technical readiness is a separate axis from source-attested economic activity.
 * Counts describe installed code paths only; no positions or returns are inferred.
 */
export function technicalStage(slot){
 if(!IDENTIFIER.test(slot)||Number(slot.slice(3))<1||Number(slot.slice(3))>64)
  throw Error("Unknown institutional strategy slot");
 const id=Number(slot.slice(3));
 if(id<=2||(id>=10&&id<=18)||id===38||id===39)
  return {id:"book_unstarted",label:"Motor paper preparado · sin iniciar"};
 if(id>=19&&id<=27)
  return {id:"signal_contract",label:"Contrato semanal · sin modelos certificados"};
 return {id:"pending",label:"Implementación pendiente"};
}
export function technicalCoverage(roster){
 verifyFullRoster(roster);
 const totals={book_unstarted:0,signal_contract:0,pending:0};
 for(const x of roster.entries)totals[technicalStage(x.slot).id]++;
 if(totals.book_unstarted!==13||totals.signal_contract!==9||
    totals.pending!==42)throw Error("Unexpected 64-line technical readiness");
 return totals;
}
