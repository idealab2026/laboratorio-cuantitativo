import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {featuresBefore,observation,fitRegressor,fitClassifier,estimate,walkForward,evaluateResearch} from "../src/learning.mjs";
const data=JSON.parse(readFileSync(new URL("../data/demo.json",import.meta.url),"utf8"));
test("True fitted estimators produce bounded classification probabilities",()=>{
 const prices=data.market["SIM-A"],samples=[];
 for(let i=6;i<25;i++)samples.push(observation(prices,i));
 const reg=fitRegressor(samples),cls=fitClassifier(samples);
 assert.equal(reg.nTrain,19);
 assert.ok(reg.coefficients.slice(1).some(v=>Math.abs(v)>1e-9));
 const prediction=estimate(reg,featuresBefore(prices,25));
 const probability=estimate(cls,featuresBefore(prices,25));
 assert.ok(Number.isFinite(prediction));
 assert.ok(probability>0&&probability<1);
});
test("Walk forward is chronological and reproducible",()=>{
 const s=walkForward(data.market["SIM-A"],data.dates);
 assert.equal(s.n,28);
 assert.ok(s.forecasts.every(f=>f.trainingObservations>=14 && f.informationCutoff===f.trainingLastLabel));
 assert.deepEqual(s,walkForward(data.market["SIM-A"],data.dates));
 assert.ok(Number.isFinite(s.rmsePct)&&s.rmsePct>=0);
 assert.ok(s.brier>=0&&s.brier<=1);
});
test("Future closing price never influences any earlier prediction",()=>{
 const a=data.market["SIM-B"],baseline=walkForward(a,data.dates);
 const revised=[...a];revised[revised.length-1]*=2;
 const changed=walkForward(revised,data.dates);
 assert.deepEqual(baseline.forecasts.slice(0,-1),changed.forecasts.slice(0,-1));
 assert.equal(baseline.forecasts.at(-1).predictedReturnPct,changed.forecasts.at(-1).predictedReturnPct);
 assert.equal(baseline.forecasts.at(-1).predictedProbabilityUp,changed.forecasts.at(-1).predictedProbabilityUp);
 assert.notEqual(baseline.forecasts.at(-1).realizedReturnPct,changed.forecasts.at(-1).realizedReturnPct);
});
test("Missing quotes and illicit future feature requests fail closed",()=>{
 const bad=[...data.market["SIM-C"]];bad[18]=null;
 assert.throws(()=>walkForward(bad,data.dates));
 assert.throws(()=>featuresBefore(data.market["SIM-C"],48));
 assert.throws(()=>walkForward(data.market["SIM-C"],data.dates.slice(1)));
});
test("Laboratory never claims traded return or migrated performance",()=>{
 const r=evaluateResearch(data);
 assert.equal(r.status,"TRAINED_ON_SYNTHETIC_ONLY");
 assert.equal(r.tradingPerformance,null);
 assert.equal(r.series.length,3);
 for(const s of r.series)assert.equal(s.dataClass,"synthetic");
});
