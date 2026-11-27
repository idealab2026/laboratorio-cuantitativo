import {paperLeaderboard,economicRecordFor} from '../src/algorithm-detail.mjs?v=202611270002';
import {verifyOriginalPaper} from '../src/original-paper.mjs';
import {verifyPaperFeed} from '../src/paper-feed.mjs';
import {parseLocalPaperResults,parseLocalPaperCurves} from '../src/private-paper.mjs';
import {verifyFullRoster, partitionCompetitionRows} from '../src/competition-roster.mjs';

export function isCompetitionListQuestion(question) {
  const q=String(question).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  if (/\bil-\d{3}\b|\bgs-\d{2}\b|\b(mejor|peor|gana\w*|lider|rentab\w*|rendimiento|ranking|clasificacion)\b/.test(q)) return false;
  return /\b(algoritmos|estrategias|modelos|competicion)\b/.test(q) &&
    /\b(compit\w*|compet\w*|particip\w*|actual\w*|activos|vigentes|cuales|list\w*)\b/.test(q);
}

export function competitionAnswer(roster, labels, gs) {
  verifyFullRoster(roster);
  const active=partitionCompetitionRows(roster.entries).active;
  const groups=new Map();
  for (const entry of active) {
    if (!groups.has(entry.group)) groups.set(entry.group, []);
    groups.get(entry.group).push(`${entry.slot} ${labels?.get(entry.slot) || entry.name}`);
  }
  const lines=[`En la pestaña «Activos» de la competición figuran ${active.length} estrategias y referencias de la cohorte vigente:`, ''];
  for (const [group, entries] of groups) lines.push(`${group}:\n${entries.join('\n')}`, '');
  lines.push('La pestaña «Activos» incluye referencias de comparación. Pertenecer a esta cohorte no garantiza que una estrategia haya operado hoy ni que sus resultados sean comparables.');
  const ids=['GS-01','GS-02','GS-03','GS-04','GS-05','GS-SPY'];
  if (gs?.schema==='midas.gs_quant_research.v1' && gs.currency==='USD' &&
      gs.initial_capital===100000 && gs.campaign_start==='2026-11-25' &&
      Object.keys(gs.books || {}).sort().join('|')===ids.join('|') &&
      ids.every(id=>typeof gs.books[id]?.name==='string' && gs.books[id].name.length>0 && gs.books[id].name.length<=160)) {
    lines.push('', 'Además, la web muestra por separado la cohorte prospectiva GS Quant:');
    for (const id of ids) lines.push(`${id} ${gs.books[id].name}`);
    lines.push('Es una cohorte paper separada: no debe mezclarse automáticamente con la clasificación anterior.');
  } else lines.push('', 'La cohorte GS Quant adicional no se ha podido comprobar en este momento.');
  if (!labels) lines.push('', 'Se muestran los nombres del catálogo; algunos nombres de la tabla pueden ser más específicos.');
  return lines.join('\n');
}

const normalise=q=>String(q).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function competitionRankingIntent(question){
 const q=normalise(question);
 // Individual strategy/company and methodology questions are not leaderboard queries.
 if(/\bil-\d{3}\b|\bgs-(?:\d{2}|spy)\b|\b(tesis|empresa|adobe|palantir|comprar|recomiend\w*|predec\w*|prediccion|futuro)\b/.test(q))return null;
 const topic=/\b(algoritm\w*|estrateg\w*|modelos?|competicion|ranking|clasificacion|lider\w*|quien|cual)\b/.test(q);
 if(!topic&&!/\b(va ganando|van ganando|quien gana)\b/.test(q))return null;
 if(/\b(hoy|diari[oa]|ultimo dia|esta sesion)\b/.test(q)&&/\b(gana\w*|mejor|rentab\w*|rendimiento|lider\w*|ranking)\b/.test(q))return 'day';
 if(/\b(peor|perdedor|perdiendo|menor rentabilidad|menos rentable)\b/.test(q))return 'worst';
 if(/\b(ranking|clasificacion|top|primeros|mejores|mayor rentabilidad)\b/.test(q))return 'ranking';
 if(/\b(gana\w*|ganador\w*|lider\w*|mejor|mas rentable|mas rentabilidad|primero|primera|encabeza\w*)\b/.test(q))return 'leader';
 return null;
}
export function leaderboardRows(roster, evidence, mode='leader'){
 verifyFullRoster(roster);
 const rows=partitionCompetitionRows(roster.entries).active.map(item=>({
  id:item.slot,name:evidence.original?.labels?.get(item.slot)||item.name,
  record:economicRecordFor(item.slot,evidence)
 }));
 // Reuse precisely the eligibility/tie-breaker from the public leaderboard.
 const valid=rows.filter(row=>paperLeaderboard([row])!==null);
 if(mode==='day')return valid.filter(row=>Number.isFinite(row.record.day_return_pct)).sort((a,b)=>b.record.day_return_pct-a.record.day_return_pct||a.id.localeCompare(b.id));
 if(mode==='worst')return valid.sort((a,b)=>a.record.return_pct-b.record.return_pct||a.id.localeCompare(b.id));
 return valid.sort((a,b)=>b.record.return_pct-a.record.return_pct||a.id.localeCompare(b.id));
}
export function rankingAnswer(roster,evidence,mode='leader'){
 const rows=leaderboardRows(roster,evidence,mode);
 if(!rows.length)return 'No hay resultados paper verificables para esta clasificación. No puedo asignar un ganador sin datos.';
 const pct=x=>new Intl.NumberFormat('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:'exceptZero'}).format(x)+' %';
 const day=mode==='day',list=mode==='ranking'?rows.slice(0,5):rows.slice(0,1);
 const lead=mode==='ranking'?'Clasificación provisional por rentabilidad acumulada paper:':day?'Mayor rentabilidad de la última sesión registrada (no necesariamente de hoy):':mode==='worst'?'Menor rentabilidad acumulada registrada:':'El líder provisional de la competición por rentabilidad acumulada paper es:';
 return [lead,'',...list.map((x,i)=>(mode==='ranking'?(i+1)+'. ':'')+x.name+' ('+x.id+'): '+pct(day?x.record.day_return_pct:x.record.return_pct)+' · '+x.record.currency+'\nInicio: '+x.record.first_session+' · último cierre: '+(x.record.last_session||'N/D')+' · '+x.record.session_count+' sesiones.'),'','Capital simulado; las estrategias pueden tener distintas fechas, divisas y grupos de comparación. La cohorte GS Quant se clasifica por separado.',evidence.partial?'Alguna fuente no se pudo comprobar; la clasificación puede estar incompleta.':''].filter((x,i,a)=>x!==''||i!==a.length-1).join('\n');
}
export async function fetchRankingEvidence(roster,get,getText){
 const results=await Promise.allSettled([
  Promise.all([get('https://raw.githubusercontent.com/idealab2026/laboratorio-cuantitativo/main/strategy_state/dashboard.json'),get('../data/original-track-map.json')]).then(([d,m])=>verifyOriginalPaper(d,m)),
  get('../data/institutional-paper-feed.json').then(d=>verifyPaperFeed(d,roster)),
  Promise.all([getText('../data/historical-paper-results.csv'),getText('../data/historical-paper-curves.csv')]).then(([r,c])=>{const historical=parseLocalPaperResults(r);return {historical,curves:parseLocalPaperCurves(c,historical)};})
 ]);
 const [original,feed,archive]=results.map(x=>x.status==='fulfilled'?x.value:null);
 return {original,feed,...(archive||{}),partial:results.some(x=>x.status!=='fulfilled')};
}
