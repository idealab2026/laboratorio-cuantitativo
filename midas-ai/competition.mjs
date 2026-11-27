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
