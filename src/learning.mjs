// IDEA LAB. Trained models evaluated on an artificial price laboratory.
// No external prices, historical investments or inherited model weights.
import {verify, finite} from "./metrics.mjs";

const AVERAGE = xs => xs.reduce((a,b)=>a+b,0)/xs.length;
const STDEV = xs => Math.sqrt(xs.reduce((a,b)=>a+(b-AVERAGE(xs))**2,0)/Math.max(1,xs.length-1));
const SIGMOID = x => 1/(1+Math.exp(-Math.max(-35,Math.min(35,x))));

function priceCheck(prices) {
  if (!Array.isArray(prices) || prices.length < 28 || prices.some(p=>!finite(p)||p<=0)) {
    throw Error("Missing, nonpositive or insufficient prices: evaluation stopped");
  }
}
export function featuresBefore(prices, targetIndex) {
  if (!Number.isInteger(targetIndex) || targetIndex < 6 || targetIndex >= prices.length) throw Error("Feature date outside causal sample");
  const k=targetIndex-1, changes=[];
  for(let i=k-4;i<=k;i++) changes.push(100*(prices[i]/prices[i-1]-1));
  return [
    100*(prices[k]/prices[k-1]-1),
    100*(prices[k]/prices[k-3]-1),
    100*(prices[k]/prices[k-5]-1),
    STDEV(changes)
  ];
}
export function observation(prices, targetIndex) {
  const x=featuresBefore(prices,targetIndex);
  return {x, y:100*(prices[targetIndex]/prices[targetIndex-1]-1)};
}
function train(samples, kind) {
  if (!Array.isArray(samples)||samples.length<10)throw Error("Training window too small");
  if (!["regression","classification"].includes(kind))throw Error("Unknown estimator");
  if(samples.some(row=>!Array.isArray(row.x)||row.x.length!==4||row.x.some(v=>!finite(v))||!finite(row.y)))throw Error("Invalid training observation");
  const center=[0,1,2,3].map(i=>AVERAGE(samples.map(r=>r.x[i])));
  const scale=[0,1,2,3].map(i=>Math.max(1e-8,STDEV(samples.map(r=>r.x[i]))));
  const vectors=samples.map(s=>[1,...s.x.map((v,i)=>(v-center[i])/scale[i])]);
  const targets=samples.map(s=>kind==="classification"?(s.y>0?1:0):s.y);
  const coefficients=[0,0,0,0,0];
  const learningRate=kind==="classification"?.11:.045, regularization=.02;
  for(let epoch=0;epoch<440;epoch++){
    const gradient=[0,0,0,0,0];
    vectors.forEach((row,i)=>{
      const linear=row.reduce((sum,x,j)=>sum+x*coefficients[j],0);
      const prediction=kind==="classification"?SIGMOID(linear):linear;
      const error=prediction-targets[i];
      row.forEach((x,j)=>{gradient[j]+=error*x;});
    });
    coefficients.forEach((v,j)=>{
      const penalty=j===0?0:regularization*v;
      coefficients[j]-=learningRate*(gradient[j]/samples.length+penalty);
    });
  }
  return {kind,center,scale,coefficients,nTrain:samples.length};
}
export const fitRegressor = samples => train(samples,"regression");
export const fitClassifier = samples => train(samples,"classification");
export function estimate(model, x) {
  if (!Array.isArray(x)||x.length!==4||x.some(v=>!finite(v)))throw Error("Invalid prediction features");
  const vector=[1,...x.map((v,i)=>(v-model.center[i])/model.scale[i])];
  const raw=vector.reduce((sum,v,i)=>sum+v*model.coefficients[i],0);
  return model.kind==="classification"?SIGMOID(raw):raw;
}
export function walkForward(prices,sessions,minimumTraining=14) {
  priceCheck(prices);
  if(!Array.isArray(sessions)||sessions.length!==prices.length||new Set(sessions).size!==sessions.length)throw Error("Inconsistent calendar");
  if(!Number.isInteger(minimumTraining)||minimumTraining<10||minimumTraining>prices.length-12)throw Error("Invalid training policy");
  const forecasts=[];
  for(let target=6+minimumTraining;target<prices.length;target++){
    // At the last observed close (target-1), every fitted label is already known.
    const training=[];
    for(let past=6;past<target;past++) training.push(observation(prices,past));
    const regressor=fitRegressor(training),classifier=fitClassifier(training);
    const x=featuresBefore(prices,target);
    forecasts.push({
      targetSession:sessions[target],
      informationCutoff:sessions[target-1],
      trainingLastLabel:sessions[target-1],
      trainingObservations:training.length,
      predictedReturnPct:estimate(regressor,x),
      predictedProbabilityUp:estimate(classifier,x),
      realizedReturnPct:100*(prices[target]/prices[target-1]-1)
    });
  }
  const n=forecasts.length;
  const rmse=Math.sqrt(AVERAGE(forecasts.map(f=>(f.predictedReturnPct-f.realizedReturnPct)**2)));
  const brier=AVERAGE(forecasts.map(f=>(f.predictedProbabilityUp-(f.realizedReturnPct>0?1:0))**2));
  const accuracy=AVERAGE(forecasts.map(f=>(f.predictedProbabilityUp>=.5)===(f.realizedReturnPct>0)?1:0));
  return {trainingMethod:"chronological expanding-window",dataClass:"synthetic",n,rmsePct:rmse,brier,accuracy,forecasts};
}
export function evaluateResearch(data){
  verify(data);
  const series=Object.entries(data.market).map(([symbol,prices])=>({symbol,...walkForward(prices,data.dates)}));
  return {dataClass:"synthetic",status:"TRAINED_ON_SYNTHETIC_ONLY",series,trainers:["ridge-like gradient optimization","logistic gradient optimization"],tradingPerformance:null};
}
