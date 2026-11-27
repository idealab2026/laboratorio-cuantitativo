import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildCorpus,retrieve,exactSource,selectSources,structuredAnswer,contextualQuery,wantsRaw} from './retrieval.mjs';
import {isCompetitionListQuestion,competitionAnswer,competitionRankingIntent,leaderboardRows,rankingAnswer,fetchRankingEvidence} from './competition.mjs';

const json = async path => JSON.parse(await readFile(new URL(path, import.meta.url)));
const corpus = buildCorpus(await json('../data/competition-roster.json'), await json('../data/public-theses.json'));
test('recupera la empresa y la estrategia exactas sin mezclar identificadores', () => {
  assert.match(retrieve('¿Qué dice la tesis de Palantir?',corpus)[0].title,/PLTR/);
  assert.deepEqual(retrieve('¿Qué es IL-001?',corpus).map(x=>x.title),['IL-001 · SPY · benchmark']);
});
test('no inventa una fuente cuando no hay coincidencias', () => {
  assert.deepEqual(retrieve('ornitorrinco',corpus),[]);
});
test('muestra la fuente literal solo para un identificador inequívoco', () => {
  assert.match(exactSource('¿Qué es IL-001?',corpus).title,/IL-001/);
  assert.match(exactSource('¿Qué dice Palantir Technologies?',corpus).title,/PLTR/);
  assert.match(exactSource('¿Qué dice Palantir?',corpus).title,/PLTR/);
  assert.equal(exactSource('¿Qué es MIDAS?',corpus),null);
});
test('rechaza datos que no cumplen el esquema esperado', () => {
  assert.throws(()=>buildCorpus({entries:[]},{records:[]}),/incompatibles/);
});
test('reconoce la pregunta del usuario y distingue las peticiones de rentabilidad', () => {
  for(const question of ['Que algoritmos están compitiendo?', '¿Qué estrategias compiten actualmente?', '¿Cuáles son los algoritmos activos?'])
    assert.equal(isCompetitionListQuestion(question),true,question);
  for(const question of ['¿Qué es IL-001?', '¿Qué algoritmo es el mejor?', '¿Qué estrategias tienen mayor rentabilidad?'])
    assert.equal(isCompetitionListQuestion(question),false,question);
});
test('describe exactamente la cohorte vigente y separa GS Quant', async () => {
  const roster=await json('../data/competition-roster.json'),gs=await json('../data/gs-quant-paper.json');
  const answer=competitionAnswer(roster,null,gs);
  assert.match(answer,/35 estrategias y referencias/);
  assert.match(answer,/IL-010 Equiponderación 503/);
  assert.match(answer,/IL-044 Algoritmo genético/);
  assert.doesNotMatch(answer,/IL-001|IL-045|IL-R001/);
  assert.match(answer,/cohorte prospectiva GS Quant/);
  assert.match(answer,/GS-05 Multifactor cuantitativo/);
  assert.match(answer,/GS-SPY Referencia SPY/);
  assert.match(competitionAnswer(roster,null,null),/GS Quant adicional no se ha podido comprobar/);
  assert.throws(()=>competitionAnswer({schema:'incorrecto',entries:[]},null,null));
});

test('sala de trading y terminal: documentación operacional recuperable',()=>{
  for(const q of ['¿Cómo funciona la sala de trading?','sala trading','¿Qué es el terminal de análisis?','¿Dónde veo las órdenes previstas?','¿El diario se actualiza cada 30 segundos?']){
    assert.match(selectSources(q,corpus).sources[0].title,/Sala de trading/,q);
  }
  assert.match(structuredAnswer(selectSources('sala de trading',corpus).exact),/No se envían órdenes reales/);
});
test('la tesis exacta se puede explicar y conserva valores históricos',()=>{
  for(const q of ['explícame la tesis de Adobe','ADBE','tesis de Adobe Inc.','valoración de Adobe','qué riesgos tiene Adobe','precio de referencia Adobe','escenario base de Adobe','escenario alcista de Adobe','escenario bajista Adobe','CAGR Adobe']){
    const x=selectSources(q,corpus);
    assert.equal(x.exact.record.ticker,'ADBE',q);
    assert.equal(x.raw,false,q);
    assert.match(structuredAnswer(x.exact),/hipótesis históricas/);
  }
  const doc=selectSources('tesis Adobe',corpus).exact;
  assert.ok(structuredAnswer(doc).includes(new Intl.NumberFormat('es-ES',{maximumFractionDigits:4}).format(doc.record.baseTarget)));
});
test('memoria de entidad y petición explícita de fuente',()=>{
  for(const q of ['¿Y los riesgos?','¿Y su rentabilidad?','¿Sus factores de crecimiento?','¿Qué riesgos tiene?','¿Y el escenario base?','Profundiza en la valoración']){
    assert.equal(selectSources(q,corpus,'ADBE').exact.record.ticker,'ADBE',q);
  }
  assert.equal(selectSources('tesis de Palantir',corpus,'ADBE').exact.record.ticker,'PLTR');
  for(const q of ['texto original de Adobe','registro original Adobe','fragmento original Adobe','Adobe sin resumir','Adobe literal'])assert.equal(wantsRaw(q),true);
  assert.equal(contextualQuery('ornitorrinco','ADBE'),'ornitorrinco');
  assert.equal(selectSources('ornitorrinco',corpus,'ADBE').sources.length,0);
});
test('informe ampliado solo si supera el contrato público',()=>{
  const roster={schema:'idea_lab_strategy_coverage_v1',entries:[]},theses={schema:'midas_public_theses_v1',records:[{ticker:'TEST',company:'Test Company'}]};
  const reports={schema:'midas_canonical_web_reports_v1',reports:[{ticker:'TEST',publication_gate:'approved',source_text:'Supuestos de valoración: flujo de caja de referencia.'}]};
  const c=buildCorpus(roster,theses,reports);
  assert.equal(selectSources('valoración TEST',c).sources.length,2);
  assert.equal(selectSources('tesis TEST',c).sources.length,1);
  reports.reports[0].publication_gate='pending';
  assert.equal(selectSources('valoración TEST',buildCorpus(roster,theses,reports)).sources.length,1);
});

test('las consultas de cifras y seguimiento devuelven el dato pertinente',()=>{
  const adobe=selectSources('Adobe',corpus).exact;
  const base=structuredAnswer(adobe,'¿Y el escenario base?');
  assert.match(base,/Base:/);
  assert.doesNotMatch(base,/Alcista:/);
  assert.match(structuredAnswer(adobe,'¿Qué riesgos tiene?'),/Riesgos de Adobe/);
  assert.match(structuredAnswer(adobe,'precio de referencia'),/No es una cotización actual/);
});

test('preguntas coloquiales de clasificación no se envían al LLM',()=>{
 for(const q of ['q algoritmo va ganando?','¿Qué algoritmo es el mejor?','¿Quién va ganando?','¿Cuál es el líder?','¿Qué estrategia va primera?','¿Qué modelo es más rentable?'])assert.equal(competitionRankingIntent(q),'leader',q);
 for(const q of ['ranking de algoritmos','clasificación de estrategias','top 5 modelos'])assert.equal(competitionRankingIntent(q),'ranking',q);
 for(const q of ['¿Qué algoritmo gana hoy?','¿Qué estrategia tiene mejor rentabilidad diaria?'])assert.equal(competitionRankingIntent(q),'day',q);
 for(const q of ['¿Cuál es la tesis de Adobe?','¿Qué rentabilidad tiene IL-012?','¿Qué algoritmos están compitiendo?','¿Cómo funciona la sala de trading?'])assert.equal(competitionRankingIntent(q),null,q);
});
test('clasificación usa las mismas fuentes públicas y excluye las cohortes retiradas',async()=>{
 const roster=await json('../data/competition-roster.json');
 const fromFile=async url=>json(url.startsWith('https:')?'../strategy_state/dashboard.json':url);
 const fromText=async url=>readFile(new URL(url,import.meta.url),'utf8');
 const evidence=await fetchRankingEvidence(roster,fromFile,fromText);
 assert.ok(evidence.original,'diario original válido');
 const rows=leaderboardRows(roster,evidence);
 assert.ok(rows.length>0);
 assert.ok(rows.every((row,i)=>i===0||rows[i-1].record.return_pct>=row.record.return_pct));
 assert.match(rankingAnswer(roster,evidence),new RegExp(rows[0].id));
 assert.match(rankingAnswer(roster,evidence),/Capital simulado/);
 assert.equal(leaderboardRows(roster,{}).length,0);
 assert.match(rankingAnswer(roster,{}),/No hay resultados/);
});
