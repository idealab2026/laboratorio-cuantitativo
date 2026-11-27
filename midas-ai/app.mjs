import {buildCorpus,retrieve,exactSource} from './retrieval.mjs';
const $ = id => document.getElementById(id);
const load = $('load'), input = $('question'), send = $('send'), status = $('status'), messages = $('messages'), badge = $('badge');
let corpus, worker, pendingSources=[];
function setBusy(busy) { input.disabled=busy; send.disabled=busy; }
function message(role, content, sources=[]) {
  messages.querySelector('.welcome')?.remove();
  const box=document.createElement('div'); box.className=`message ${role}`;
  const label=document.createElement('strong'); label.textContent=role==='user'?'Tú':role==='source'?'Fragmento de la fuente':'MIDAS AI · respuesta experimental';
  const text=document.createElement('p'); text.textContent=content; box.append(label,text);
  if(sources.length){const refs=document.createElement('div');refs.className='sources';refs.append('Fuentes consultadas: ');
    sources.forEach((source,i)=>{if(i) refs.append(' · ');const a=document.createElement('a');a.href=source.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent=source.title;refs.append(a);});box.append(refs);
    const details=document.createElement('details'), summary=document.createElement('summary');summary.textContent='Ver fragmentos recuperados';details.append(summary);
    for(const source of sources){const h=document.createElement('strong'),p=document.createElement('p');h.textContent=source.title;p.textContent=source.text;details.append(h,p);}box.append(details);}
  messages.append(box);messages.scrollTop=messages.scrollHeight;
}
async function initialise() {
  load.disabled=true; status.textContent='Cargando fuentes públicas y preparando el modelo…';
  try {
    const responses=await Promise.all(['../data/competition-roster.json','../data/public-theses.json'].map(url=>fetch(url)));
    if(responses.some(r=>!r.ok)) throw Error('No se pudieron cargar las fuentes públicas.');
    corpus=buildCorpus(...await Promise.all(responses.map(r=>r.json())));
    worker=new Worker('./worker.mjs',{type:'module'});
    worker.onerror=(event)=>fail(`No se pudo iniciar el modelo: ${event.message || 'revisa la compatibilidad del navegador'}.`);
    worker.onmessage=({data})=>{
      if(data.type==='progress') status.textContent=`Descargando modelo: ${Math.round(data.progress)} %`;
      if(data.type==='ready'){status.textContent='Modelo listo. El procesamiento se realiza en este dispositivo.';badge.textContent='Listo';load.hidden=true;setBusy(false);input.focus();}
      if(data.type==='answer'){message('assistant',data.answer || 'No he podido generar una respuesta.',pendingSources);pendingSources=[];status.textContent='Modelo listo.';setBusy(false);input.focus();}
      if(data.type==='error') fail('No se pudo ejecutar el modelo. Comprueba la conexión, el espacio y la memoria, y vuelve a intentarlo.');
    };
    worker.postMessage({type:'load'});
  } catch(e) {fail(e.message || 'No se pudieron cargar las fuentes.');}
}
function fail(text){worker?.terminate();worker=null;setBusy(true);load.hidden=false;load.disabled=false;badge.textContent='Sin iniciar';status.textContent=text;}
function ask(){const q=input.value.trim();if(!q||!worker)return;input.value='';message('user',q);const sources=retrieve(q,corpus);
  if(!sources.length){message('assistant','No he encontrado información relacionada en las fuentes públicas disponibles. Prueba con el nombre o identificador de una estrategia o empresa.');return;}
  const exact=exactSource(q,corpus);
  if(exact){message('source',`Esto es lo que consta en el registro consultado. Revisa si responde a tu pregunta:\n\n${exact.text}`,[exact]);return;}
  pendingSources=sources;setBusy(true);status.textContent='Preparando respuesta…';worker.postMessage({type:'ask',question:q,context:sources.map((s,i)=>`[${i+1}] ${s.title}: ${s.text}`).join('\n\n')});}
load.addEventListener('click',initialise);send.addEventListener('click',ask);
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}});
document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',()=>{input.value=b.dataset.example;if(!input.disabled)input.focus();else status.textContent='Carga primero el modelo para hacer tu pregunta.';}));
