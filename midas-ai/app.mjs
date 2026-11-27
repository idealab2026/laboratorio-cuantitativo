import {buildCorpus,selectSources,structuredAnswer} from './retrieval.mjs?v=202611270002';
import {isCompetitionListQuestion,competitionAnswer,competitionRankingIntent,fetchRankingEvidence,rankingAnswer} from './competition.mjs?v=202611270002';
import {verifyOriginalPaper} from '../src/original-paper.mjs';
const $ = id => document.getElementById(id);
const load = $('load'), input = $('question'), send = $('send'), status = $('status'), messages = $('messages'), badge = $('badge');
let corpus, worker, pendingSources=[], pendingFallback='', previous='', ready=false, loading=false, busy=false;
function setBusy(value) { busy=value; input.disabled=value||!corpus; send.disabled=value||!corpus; }
function message(role, content, sources=[]) {
  messages.querySelector('.welcome')?.remove();
  const box=document.createElement('div'); box.className=`message ${role}`;
  const label=document.createElement('strong'); label.textContent=role==='user'?'Tú':role==='source'?'Fragmento de la fuente':role==='data'?'Datos verificados de la fuente':'MIDAS AI · respuesta experimental';
  const text=document.createElement('p'); text.textContent=content; box.append(label,text);
  if(sources.length){const refs=document.createElement('div');refs.className='sources';refs.append('Fuentes consultadas: ');
    sources.forEach((source,i)=>{if(i) refs.append(' · ');const a=document.createElement('a');a.href=source.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent=source.title;refs.append(a);});box.append(refs);
    const details=document.createElement('details'), summary=document.createElement('summary');summary.textContent='Ver fragmentos recuperados';details.append(summary);
    for(const source of sources){const h=document.createElement('strong'),p=document.createElement('p');h.textContent=source.title;p.textContent=source.text;details.append(h,p);}box.append(details);}
  messages.append(box);messages.scrollTop=role==='user'?messages.scrollHeight:Math.max(0,messages.scrollHeight-box.offsetHeight-60);
}
async function initialise() {
  if(loading||ready)return; loading=true;load.hidden=true;load.disabled=true; status.textContent='Cargando fuentes públicas y preparando el modelo…';
  try {
    const responses=await Promise.all(['../data/competition-roster.json','../data/public-theses.json'].map(url=>fetch(url)));
    if(responses.some(r=>!r.ok)) throw Error('No se pudieron cargar las fuentes públicas.');
    const [roster,theses]=await Promise.all(responses.map(r=>r.json()));
    let reports=null;
    try{const response=await fetch('../data/thesis-reports.json');if(response.ok)reports=await response.json();}catch{/* optional public reports */}
    corpus=buildCorpus(roster,theses,reports);setBusy(false);
    worker=new Worker('./worker.mjs?v=202611270002',{type:'module'});
    worker.onerror=(event)=>fail(`No se pudo iniciar el modelo: ${event.message || 'revisa la compatibilidad del navegador'}.`);
    worker.onmessage=({data})=>{
      if(data.type==='progress') status.textContent=`Descargando modelo: ${Math.round(data.progress)} %`;
      if(data.type==='ready'){ready=true;loading=false;status.textContent='Modelo listo. El procesamiento se realiza en este dispositivo.';badge.textContent='Listo';load.hidden=true;if(!busy)setBusy(false);}
      if(data.type==='answer'){
        const answer=String(data.answer||'').trim();
        if(answer.length>=20 && !/<think>/i.test(answer) && !(pendingFallback&&/no (consta|hay información|se dispone)/i.test(answer)))message('assistant',pendingFallback?answer+'\n\nDatos verificados:\n'+pendingFallback:answer,pendingSources);
        else if(pendingFallback)message('data',pendingFallback,pendingSources);
        else message('assistant','No he podido elaborar una explicación fiable. Consulta las fuentes recuperadas.',pendingSources);
        pendingSources=[];pendingFallback='';status.textContent='Modelo listo.';setBusy(false);input.focus();
      }
      if(data.type==='error') fail('No se pudo ejecutar el modelo. Comprueba la conexión, el espacio y la memoria, y vuelve a intentarlo.');
    };
    worker.postMessage({type:'load'});
  } catch(e) {fail(e.message || 'No se pudieron cargar las fuentes.');}
}
function fail(text){
  worker?.terminate();worker=null;ready=false;loading=false;
  if(pendingSources.length)message(pendingFallback?'data':'assistant',pendingFallback||'El modelo no ha podido generar una respuesta. Puedes consultar los fragmentos recuperados.',pendingSources);
  pendingSources=[];pendingFallback='';setBusy(false);load.hidden=false;load.disabled=false;badge.textContent=corpus?'Solo fuentes':'Sin iniciar';status.textContent=text;
}
async function ask(){const q=input.value.trim();if(!q||!corpus||busy)return;input.value='';message('user',q);
  const ranking=competitionRankingIntent(q);
  if(ranking){
    previous='';setBusy(true);status.textContent='Verificando la clasificación paper…';
    try{
      const response=async url=>{const r=await fetch(url,{cache:'no-store',credentials:'omit',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Fuente no disponible');return r;};
      const get=async url=>(await response(url)).json(),getText=async url=>(await response(url)).text();
      const roster=await get('../data/competition-roster.json');
      const evidence=await fetchRankingEvidence(roster,get,getText);
      const text=rankingAnswer(roster,evidence,ranking);
      message('data',text,[{title:'Clasificación de algoritmos',href:'../index.html?view=competition',text:'Misma cohorte activa y criterio de rentabilidad que la tabla pública.'}]);
    }catch{message('assistant','No he podido verificar la clasificación actual. Consulta la tabla de competición o vuelve a intentarlo.');}
    finally{setBusy(false);status.textContent=ready?'Modelo listo.':loading?'Preparando modelo; datos disponibles.':'Datos disponibles sin modelo.';input.focus();}
    return;
  }
  if(isCompetitionListQuestion(q)){
    previous='';setBusy(true);status.textContent='Consultando la competición…';
    try{
      const get=async url=>{const r=await fetch(url,{cache:'no-store',credentials:'omit',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('Fuente no disponible');return r.json();};
      const [rosterResult,mapResult,dashboardResult,gsResult]=await Promise.allSettled([
        get('../data/competition-roster.json'),get('../data/original-track-map.json'),
        get('https://raw.githubusercontent.com/idealab2026/laboratorio-cuantitativo/main/strategy_state/dashboard.json'),
        get('https://raw.githubusercontent.com/idealab2026/laboratorio-cuantitativo/main/data/gs-quant-paper.json')]);
      if(rosterResult.status!=='fulfilled')throw Error('No se ha podido consultar el catálogo.');
      let labels=null;
      if(mapResult.status==='fulfilled'&&dashboardResult.status==='fulfilled'){
        try{labels=verifyOriginalPaper(dashboardResult.value,mapResult.value).labels;}catch(_error){/* use catalog labels */}
      }
      const text=competitionAnswer(rosterResult.value,labels,gsResult.status==='fulfilled'?gsResult.value:null);
      const sources=[{title:'Competición de algoritmos',href:'../index.html?view=competition',text:'Clasificación y fases de las estrategias publicadas por MIDAS.'}];
      if(labels)sources.push({title:'Diario institucional',href:'https://raw.githubusercontent.com/idealab2026/laboratorio-cuantitativo/main/strategy_state/dashboard.json',text:'Nombres de estrategias del diario institucional verificado.'});
      if(gsResult.status==='fulfilled')sources.push({title:'Cohorte GS Quant',href:'https://raw.githubusercontent.com/idealab2026/laboratorio-cuantitativo/main/data/gs-quant-paper.json',text:'Registro publicado de la cohorte GS Quant.'});
      message('data',text,sources);
    }catch(_error){message('assistant','No he podido verificar el registro de la competición ahora mismo. Vuelve a intentarlo o abre la pestaña Competición de algoritmos.');}
    finally{setBusy(false);status.textContent=ready?'Modelo listo.':'Fuentes disponibles; modelo en preparación.';input.focus();}
    return;
  }
  const selection=selectSources(q,corpus,previous);
  const {sources,exact,raw}=selection;
  if(!sources.length){message('assistant','No he encontrado información relacionada en las fuentes públicas disponibles. Prueba con la sala de trading, una estrategia o una empresa.');return;}
  previous=exact?.identity?.[0]||sources[0]?.identity?.[0]||'';
  if(raw&&exact){message('source',exact.text,[exact]);return;}
  const fallback=structuredAnswer(exact,q);
  if(fallback&&!ready){message('data',fallback,sources);return;}
  if(!ready){message('source','El modelo todavía no está disponible. Estas son las fuentes recuperadas; vuelve a preguntar cuando esté listo.',sources);return;}
  // Exact financial values remain deterministic; use the LLM for the explanation.
  if(fallback&&/\b(precio de referencia|cagr|rentabilidad registrada|escenario (base|central|bajista|alcista))\b/i.test(q)){message('data',fallback,sources);return;}
  pendingSources=sources;pendingFallback=fallback;setBusy(true);status.textContent='Preparando respuesta…';
  worker.postMessage({type:'ask',question:selection.query,context:sources.map((s,i)=>`[${i+1}] ${s.title}: ${s.text}`).join('\n\n').slice(0,10000),qualitative:!!fallback});
}
load.addEventListener('click',initialise);send.addEventListener('click',ask);
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}});
document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',()=>{input.value=b.dataset.example;if(!input.disabled)input.focus();else status.textContent='Preparando las fuentes públicas…';}));

// Opening the assistant starts loading automatically; the model is cached by the runtime.
void initialise();
