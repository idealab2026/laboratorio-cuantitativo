// The corpus is deliberately limited to the two public, versioned datasets.
const stop = new Set('que es en de la el los las un una y por para con como del al se su qué cómo cuál cuáles me puedes sobre hay son sus dime información'.split(' '));
function tokens(text) {
  return String(text).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .match(/il-\d{3}|[a-z0-9]+/g)?.filter(x => x.length > 1 && !stop.has(x)) ?? [];
}
export function buildCorpus(roster, theses) {
  if (roster?.schema !== 'idea_lab_strategy_coverage_v1' || !Array.isArray(roster.entries) ||
      theses?.schema !== 'midas_public_theses_v1' || !Array.isArray(theses.records)) throw Error('Fuentes públicas incompatibles.');
  const documents = [{
    title: 'Qué es MIDAS', href: 'https://idealab2026.github.io/laboratorio-cuantitativo/',
    text: 'MIDAS es un proyecto de investigación de IDEA LAB. Estudia estrategias de inversión automatizada con operaciones simuladas y capital virtual y también el análisis fundamental de empresas cotizadas. Los escenarios y resultados deben interpretarse según su fuente y fecha; no constituyen asesoramiento de inversión.'
  }, {
    title: 'Registro de estrategias', href: '../data/competition-roster.json',
    text: `El registro institucional describe ${roster.expected} plazas de estrategias. ${roster.notice} Los estados y la disponibilidad se deben consultar por estrategia; una plaza en el catálogo no acredita resultados.`
  }];
  for (const e of roster.entries) {
    if (!e.slot || !e.name) continue;
    documents.push({title: `${e.slot} · ${e.name}`, identity: [e.slot], href: '../data/competition-roster.json',
      text: `Estrategia ${e.slot}: ${e.name}. Grupo: ${e.group}. Estado del registro: ${e.record_status}; actividad: ${e.activity}. Última sesión: ${e.last_session ?? 'no disponible'}. Rentabilidad registrada: ${e.return_pct == null ? 'no disponible' : `${e.return_pct}%`}. Una posición en el catálogo no acredita por sí sola ejecución ni rentabilidad comparable.`});
  }
  for (const t of theses.records) {
    if (!t.ticker || !t.company) continue;
    const firstName = t.company.split(/\s+/)[0];
    documents.push({title: `${t.ticker} · ${t.company}`, identity: [t.ticker, t.company, ...(firstName.length >= 5 ? [firstName] : [])], href: '../data/public-theses.json',
      text: `Tesis histórica de ${t.company} (${t.ticker}), tema ${t.theme || 'no indicado'}. Fecha de estudio ${t.studyDate || 'no indicada'}. ${t.summary || ''} Riesgos: ${Array.isArray(t.risks) ? t.risks.join('; ') : t.risks || 'no indicados'}. Los escenarios son hipótesis históricas, no cotizaciones actuales ni rentabilidades obtenidas. Publicación del archivo: ${theses.published_as_of || 'fecha no indicada'}.`});
  }
  return documents;
}
// A precise identifier gives the user the source itself, avoiding unsupported paraphrase.
export function exactSource(query, docs) {
  const q = ` ${tokens(query).join(' ')} `;
  const matches = docs.filter(doc => doc.identity?.some(name => {
    const term = tokens(name).join(' ');
    return term && q.includes(` ${term} `);
  }));
  return matches.length === 1 ? matches[0] : null;
}
export function retrieve(query, docs, limit = 4) {
  const terms = [...new Set(tokens(query))];
  if (!terms.length) return [];
  const identifier = terms.find(term => /^il-\d{3}$/.test(term));
  const ranked = docs.filter(doc => !identifier || tokens(doc.title).includes(identifier)).map(doc => {
    const title = new Set(tokens(doc.title));
    const body = new Set(tokens(doc.text));
    const score = terms.reduce((s, term) => s + (title.has(term) ? 4 : 0) + (body.has(term) ? 1 : 0), 0);
    return {doc, score};
  }).filter(x => x.score > 0).sort((a, b) => b.score - a.score);
  return ranked.filter(x => x.score >= ranked[0].score / 2).slice(0, limit).map(x => x.doc);
}
