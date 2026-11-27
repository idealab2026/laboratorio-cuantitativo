const button = document.getElementById('ai-launcher');
const panel = document.getElementById('ai-panel');
const close = document.getElementById('ai-close');
const frame = document.getElementById('ai-frame');
function setOpen(open) {
  panel.hidden = !open;
  button.setAttribute('aria-expanded', String(open));
  if (open) {
    if (!frame.getAttribute('src')) frame.setAttribute('src', './midas-ai/index.html?v=be068a33eccb');
    close.focus();
  } else button.focus();
}
button.addEventListener('click', () => setOpen(panel.hidden));
close.addEventListener('click', () => setOpen(false));
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !panel.hidden) setOpen(false); });
