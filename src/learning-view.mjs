import {evaluateResearch} from "./learning.mjs";
const root=document.getElementById("training-report");
const fmt=(x,d=3)=>Number.isFinite(x)?x.toFixed(d):"N/D";
try{
  const response=await fetch(new URL("../data/demo.json",import.meta.url),{cache:"no-store"});
  if(!response.ok)throw Error("Fallo de lectura del universo artificial");
  const result=evaluateResearch(await response.json());
  const rows=result.series.map(s=>'<tr><th scope="row">'+s.symbol+'</th><td>'+s.n+'</td><td>'+fmt(s.rmsePct)+' pp</td><td>'+fmt(s.brier)+'</td><td>'+fmt(100*s.accuracy,1)+' %</td><td>'+s.forecasts.at(-1).informationCutoff+'</td></tr>').join("");
  root.innerHTML='<p class="research-note">Entrenamiento ejecutado localmente con observaciones sintéticas. El objetivo es la predicción de la variación del siguiente cierre; no se simula operativa ni se publica una rentabilidad.</p>'+
  '<div class="training-scroll"><table><thead><tr><th>Activo artificial</th><th>Predicciones OOS</th><th>RMSE</th><th>Brier</th><th>Dirección correcta</th><th>Último corte de información</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
  '<p class="research-note">Modelos realmente ajustados en cada ventana: regresión regularizada y clasificador logístico. Entrenamiento cronológico expansivo; los parámetros y la normalización se recalculan exclusivamente con observaciones anteriores. Estas métricas son diagnósticos de una serie artificial, sin significado de rentabilidad bursátil.</p>';
}catch(error){
  root.textContent="Experimento rechazado: "+String(error.message||error);
}
