import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildCorpus,retrieve,exactSource} from './retrieval.mjs';

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
