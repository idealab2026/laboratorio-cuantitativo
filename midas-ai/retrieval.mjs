// Public sources only. Retrieval and exact numeric summaries are independent of generation.
const stop = new Set('que es en de la el los las un una y por para con como del al se su qué cómo cuál cuáles me puedes sobre hay son sus dime informacion explicame explica explicacion cuentame funciona funcionamiento decir quiero saber'.split(' '));
function tokens(text) {
  return String(text).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .match(/il-\d{3}|[a-z0-9]+/g)?.filter(x => x.length > 1 && !stop.has(x)) ?? [];
}
export function buildCorpus(roster, theses, reports=null) {
  if (roster?.schema !== 'idea_lab_strategy_coverage_v1' || !Array.isArray(roster.entries) ||
      theses?.schema !== 'midas_public_theses_v1' || !Array.isArray(theses.records)) throw Error('Fuentes públicas incompatibles.');
  const documents = [{
    title: 'Qué es MIDAS', href: 'https://idealab2026.github.io/laboratorio-cuantitativo/',
    text: 'MIDAS es un proyecto de investigación de IDEA LAB. Estudia estrategias de inversión automatizada con operaciones simuladas y capital virtual y también el análisis fundamental de empresas cotizadas. Los escenarios y resultados deben interpretarse según su fuente y fecha; no constituyen asesoramiento de inversión.'
  }, {
    title: 'Registro de estrategias', href: '../data/competition-roster.json',
    text: `El registro institucional describe ${roster.expected} plazas de estrategias. ${roster.notice} Los estados y la disponibilidad se deben consultar por estrategia; una plaza en el catálogo no acredita resultados.`
  }];
  documents.push({
    title: 'Sala de trading · panel y terminal de análisis',
    identity: ['sala de trading','sala trading','terminal de análisis'],
    href: '../index.html?view=trading',
    text: 'La sala de trading muestra señales y órdenes previstas de carteras simuladas. No envía órdenes reales. Tiene dos vistas: Panel y Terminal de análisis. El diario se consulta y actualiza cada 30 segundos y los gráficos muestran cierres auditados. Puedes seleccionar sesión, algoritmos, fase de señales, ticker y tipo de señal. El plan de apertura distingue órdenes previstas, ejecuciones simuladas de la sesión y órdenes para la siguiente apertura. El botón Actualizar comprueba el diario. El reloj operativo muestra el estado de la sesión. Las señales, planes y ejecuciones paper no son operaciones reales ni garantía de rentabilidad.',
    concise: 'La sala de trading es el panel operativo de las carteras simuladas de MIDAS.\n\n1. Selecciona la sesión y los algoritmos que quieras consultar.\n2. En Panel puedes filtrar las señales por fase, ticker y tipo; verás planes de apertura y ejecuciones paper.\n3. En Terminal de análisis puedes consultar un algoritmo y sus gráficos de cierres auditados.\n\nEl diario se consulta cada 30 segundos y puedes actualizarlo manualmente. No se envían órdenes reales.'
  });
  for (const e of roster.entries) {
    if (!e.slot || !e.name) continue;
    documents.push({title: `${e.slot} · ${e.name}`, identity: [e.slot], href: '../data/competition-roster.json',
      kind:'strategy', record:e, text: `Estrategia ${e.slot}: ${e.name}. Grupo: ${e.group}. Estado del registro: ${e.record_status}; actividad: ${e.activity}. Última sesión: ${e.last_session ?? 'no disponible'}. Rentabilidad registrada: ${e.return_pct == null ? 'no disponible' : `${e.return_pct}%`}. Una posición en el catálogo no acredita por sí sola ejecución ni rentabilidad comparable.`});
  }
  for (const t of theses.records) {
    if (!t.ticker || !t.company) continue;
    const firstName = t.company.split(/\s+/)[0];
    documents.push({title: `${t.ticker} · ${t.company}`, identity: [t.ticker, t.company, ...(firstName.length >= 5 ? [firstName] : [])], href: '../data/public-theses.json',
      kind:'thesis', record:t, text: `Tesis histórica de ${t.company} (${t.ticker}), tema ${t.theme || 'no indicado'}. Fecha de estudio ${t.studyDate || 'no indicada'}. ${t.summary || ''} Riesgos: ${Array.isArray(t.risks) ? t.risks.join('; ') : t.risks || 'no indicados'}. Factores de crecimiento: ${t.drivers || 'no indicados'}. Los escenarios son hipótesis históricas, no cotizaciones actuales ni rentabilidades obtenidas. Publicación del archivo: ${theses.published_as_of || 'fecha no indicada'}.`});
  }
  if(reports?.schema==='midas_canonical_web_reports_v1' && Array.isArray(reports.reports)){
    for(const entry of reports.reports){
      if(entry.publication_gate!=='approved'||typeof entry.source_text!=='string') continue;
      const thesis=documents.find(d=>d.kind==='thesis'&&d.record.ticker===entry.ticker);
      if(!thesis) continue;
      thesis.report=entry.source_text;
      thesis.reportHref='../data/thesis-reports.json';
    }
  }
  return documents;
}
// Exact entity detection selects grounding; it does not bypass generation.
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
  const indexed = docs.map(doc => ({doc,title:new Set(tokens(doc.title)),body:new Set(tokens(doc.text))}));
  // Downweight generic words (e.g. "diario") relative to discriminating
  // terms such as "segundos" or "apertura". No external model is required.
  const weights = new Map(terms.map(term => [term,1+Math.log((indexed.length+1)/(1+indexed.filter(d=>d.title.has(term)||d.body.has(term)).length))]));
  const ranked = indexed.filter(d=>!identifier||d.title.has(identifier)).map(({doc,title,body})=>{
    const score = terms.reduce((sum,term)=>sum+weights.get(term)*((title.has(term)?2:0)+(body.has(term)?1:0)),0);
    return {doc,score};
  }).filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
  return ranked.filter(x => x.score >= ranked[0].score / 2).slice(0, limit).map(x => x.doc);
}

const norm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function contextualQuery(question, previous){
  const q=norm(question).trim().replace(/^[¿?\s]+/,'');
  if(!previous||!(/^(y\b|sus\b|su\b|eso\b|ese\b|esa\b|el mismo\b|la misma\b|amplia\b|profundiza\b|que riesgos\b|cuales son los riesgos\b|que rentabilidad\b)/.test(q)))return question;
  return previous+' '+question;
}
export function wantsRaw(question){
  return /\b(literal|fragmento original|texto original|registro original|sin resumir)\b/.test(norm(question));
}
const number=v=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('es-ES',{maximumFractionDigits:4}).format(v):'no disponible';
export function structuredAnswer(doc,question=''){
  if(!doc)return '';
  if(doc.concise)return doc.concise;
  const t=doc.record;
  if(doc.kind==='thesis'&&t){
    const currency=t.currency||'moneda no indicada';
    const line=(name,target,cagr)=>name+': '+number(target)+' '+currency+'; CAGR estimado '+number(cagr)+(typeof cagr==='number'?' %':'');
    const q=norm(question);
    if(/\b(riesgos|amenazas)\b/.test(q)&&!(/\b(tesis|resumen|explicame)\b/.test(q)))return 'Riesgos de '+t.company+' según la tesis del '+(t.studyDate||'fecha no indicada')+': '+(Array.isArray(t.risks)?t.risks.join('; '):t.risks||'no indicados')+'.';
    if(/\b(factores|drivers|catalizadores)\b/.test(q)&&!(/\b(tesis|resumen)\b/.test(q)))return 'Factores de crecimiento de '+t.company+': '+(t.drivers||'no indicados')+'.';
    if(/\b(escenario|cagr|objetivo|target)\b/.test(q)&&!(/\b(tesis|resumen)\b/.test(q))){
      const lines=[];
      if(/\b(bajista|bear)\b/.test(q))lines.push(line('Bajista',t.bearTarget,t.bearCagr));
      if(/\b(base|central)\b/.test(q))lines.push(line('Base',t.baseTarget,t.baseCagr));
      if(/\b(alcista|bull)\b/.test(q))lines.push(line('Alcista',t.bullTarget,t.bullCagr));
      if(!lines.length)lines.push(line('Bajista',t.bearTarget,t.bearCagr),line('Base',t.baseTarget,t.baseCagr),line('Alcista',t.bullTarget,t.bullCagr));
      return t.company+' · escenarios de la tesis histórica:\n'+lines.join('\n')+'\nSon hipótesis, no resultados realizados.';
    }
    if(/\bprecio de referencia\b/.test(q)&&!(/\b(tesis|resumen)\b/.test(q)))return t.company+': '+number(t.referencePrice)+' '+currency+' ('+(t.priceDate||'fecha no indicada')+'). No es una cotización actual.';
    return [
      'Tesis histórica de '+t.company+' ('+t.ticker+'), estudiada el '+(t.studyDate||'fecha no indicada')+'. Tema: '+(t.theme||'no indicado')+'.',
      'Precio de referencia: '+number(t.referencePrice)+' '+currency+' ('+(t.priceDate||'fecha no indicada')+').',
      'Escenarios de valoración:\n'+line('Bajista',t.bearTarget,t.bearCagr)+'\n'+line('Base',t.baseTarget,t.baseCagr)+'\n'+line('Alcista',t.bullTarget,t.bullCagr),
      'Factores de crecimiento: '+(t.drivers||'no indicados')+'.',
      'Riesgos: '+(Array.isArray(t.risks)?t.risks.join('; '):t.risks||'no indicados')+'.',
      'Estado: '+(t.thesisStatus||t.valuationStatus||'no indicado')+'. Son hipótesis históricas, no rentabilidades realizadas ni precios actuales.'
    ].join('\n\n');
  }
  if(doc.kind==='strategy'&&t){
    return 'Estrategia '+t.slot+' · '+t.name+'\nGrupo: '+t.group+'\nEstado: '+t.record_status+' / '+t.activity+'\nÚltima sesión: '+(t.last_session||'no disponible')+'\nRentabilidad registrada: '+number(t.return_pct)+(typeof t.return_pct==='number'?' %':'')+'\nLa presencia en el catálogo no acredita ejecución ni comparabilidad.';
  }
  return '';
}
export function selectSources(question,docs,previous=''){
  const direct=exactSource(question,docs);
  const query=direct?question:contextualQuery(question,previous);
  const exact=direct||exactSource(query,docs);
  let sources=exact?[exact]:retrieve(query,docs);
  if(exact?.report && /\b(metodologia|supuesto|supuestos|valoracion|detalle|modelo|dcf|multiplo|multiplo[s]?|fundamento|profundiza)\b/.test(norm(question))){
    const terms=new Set(tokens(question));
    const chunks=exact.report.match(/[\s\S]{1,1400}/g)||[];
    const ranked=chunks.map((text,i)=>({text,i,score:tokens(text).filter(w=>terms.has(w)).length})).sort((a,b)=>b.score-a.score).slice(0,2);
    sources=sources.concat(ranked.map(c=>({title:exact.record.ticker+' · informe público, fragmento '+(c.i+1),href:exact.reportHref,text:c.text})));
  }
  return {query,exact,sources,raw:wantsRaw(question)};
}
