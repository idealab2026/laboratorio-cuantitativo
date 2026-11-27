import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildCorpus,retrieve,exactSource} from './retrieval.mjs';
import {isCompetitionListQuestion,competitionAnswer} from './competition.mjs';

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
