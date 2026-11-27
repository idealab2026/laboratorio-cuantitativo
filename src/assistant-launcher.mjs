const button = document.getElementById('ai-launcher');
const panel = document.getElementById('ai-panel');
const close = document.getElementById('ai-close');
const frame = document.getElementById('ai-frame');
function startAssistant(){
  if(!frame.getAttribute('src')){
    frame.loading='eager';
    frame.setAttribute('src','./midas-ai/index.html?v=202611270002');
  }
}
function setOpen(open) {
  panel.hidden = !open;
  button.setAttribute('aria-expanded', String(open));
  if (open) {
    startAssistant();
    close.focus();
  } else button.focus();
}
button.addEventListener('click', () => setOpen(panel.hidden));
close.addEventListener('click', () => setOpen(false));
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !panel.hidden) setOpen(false); });

// Start after the main page loads, without a manual activation step.
if(document.readyState==='complete')startAssistant();
else window.addEventListener('load',startAssistant,{once:true});
