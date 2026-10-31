// Browser-side shape/consistency checks. Authenticity is verified server-side
// in GitHub Actions with a secret NOT shipped to this public web application.
import {verifyFullRoster} from "./competition-roster.mjs";
const clean=(n)=>typeof n==="number"&&Number.isFinite(n);
const hex=s=>typeof s==="string"&&/^[a-f0-9]{64}$/.test(s);
const day=s=>typeof s==="string"&&/^\d{4}-\d\d-\d\d$/.test(s)&&
 Number.isFinite(Date.parse(s+"T00:00:00Z"));
export function verifyPaperFeed(doc,roster){
 verifyFullRoster(roster);
 if(!doc||doc.schema!=="idealab_institutional_paper_feed_v1")throw Error("Wrong institutional paper feed");
 if(doc.status==="not_connected"){
  if(doc.producer!=="institutional_core_pending"||doc.generated_at_utc!==null||doc.source!==null||
   !Array.isArray(doc.tracks)||doc.tracks.length!==0||doc.signature!==null)
   throw Error("Disconnected feed cannot contain results");
  return {status:"not_connected",bySlot:new Map(),count:0,session:null};
 }
 if(doc.status!=="source_verified"||doc.producer!=="idealab_institutional_core"||
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(doc.generated_at_utc||"")||
    !hex(doc.signature))throw Error("Unattested institutional paper feed");
 const source=doc.source;
 if(!source||source.identity?.vendor!=="Yahoo Finance"||source.identity.client!=="yfinance"||
    source.identity.market!=="XNYS"||source.identity.auto_adjust!==false||
    source.identity.actions!==true||source.rights_attested!==true||
    !day(source.session)||!hex(source.sha256)||
    source.requested!==504||!Number.isInteger(source.observed)||!Number.isInteger(source.missing)||
    !Number.isInteger(source.constituents_observed)||
    source.observed+source.missing!==504||source.constituents_observed<453||
    source.observed!==source.constituents_observed+1||
    !Array.isArray(doc.tracks)||doc.tracks.length<1||doc.tracks.length>64)
  throw Error("Missing authenticated source contract");
 const permitted=new Set(roster.entries.map(x=>x.slot)),bySlot=new Map();
 for(const record of doc.tracks){
  if(!permitted.has(record.slot)||bySlot.has(record.slot)||
    !["active","pending","cash","paused","error"].includes(record.activity)||
    !["USD","EUR"].includes(record.currency)||
    !day(record.first_session)||!day(record.last_session)||
    record.first_session>record.last_session||record.last_session>source.session||
    !hex(record.config_sha256)||record.source_snapshot_sha256!==source.sha256||
    !clean(record.initial_capital)||record.initial_capital<=0||
    !clean(record.last_equity)||record.last_equity<0||
    !clean(record.return_pct)||
    !Number.isInteger(record.positions)||record.positions<0||
    !Number.isInteger(record.pending_orders)||record.pending_orders<0||
    !record.risk||
    !Array.isArray(record.history)||record.history.length<1||record.history.length>520||
    !record.comparison||typeof record.comparison.eligible!=="boolean")
   throw Error("Invalid verified strategy row");
  let last=null,peak=record.initial_capital,worst=0;
  for(const p of record.history){
   if(!day(p.date)||!clean(p.nav)||p.nav<0||p.date<record.first_session||
      p.date>record.last_session||(last!==null&&p.date<=last))
    throw Error("Invalid NAV time series");
   last=p.date;peak=Math.max(peak,p.nav);worst=Math.min(worst,100*(p.nav/peak-1));
  }
  if(last!==record.last_session||Math.abs(record.history.at(-1).nav-record.last_equity)>1e-6||
     Math.abs(record.return_pct-100*(record.last_equity/record.initial_capital-1))>1e-5||
     !clean(record.risk.max_drawdown_pct)||Math.abs(record.risk.max_drawdown_pct-worst)>1e-4)
   throw Error("Unreconciled recorded NAV/risk");
  if(record.history.length>=2){
   const earlier=record.history.at(-2).nav;
   const d=earlier?100*(record.last_equity/earlier-1):null;
   if(d===null?record.day_return_pct!==null:!clean(record.day_return_pct)||Math.abs(record.day_return_pct-d)>1e-5)
    throw Error("Unreconciled daily return");
  }else if(record.day_return_pct!==null)throw Error("Daily performance without second NAV");
  bySlot.set(record.slot,record);
 }
 return {status:"source_verified",bySlot,count:bySlot.size,session:source.session,
  receivedAt:doc.generated_at_utc,coverage:source.constituents_observed};
}
