'use strict';
// Presentation state only. All business results still come from app.js/backend.
(()=>{
 const byId=id=>document.getElementById(id),reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const tokens={reveal:280,confirm:420,ease:'cubic-bezier(.2,.8,.2,1)'};
 const svg=(paths,cls='flow-symbol')=>{const el=document.createElementNS('http://www.w3.org/2000/svg','svg');el.setAttribute('viewBox','0 0 180 80');el.setAttribute('class',cls);el.setAttribute('aria-hidden','true');el.innerHTML=paths;return el};
 const map='<path class="signal-line" d="M22 42H78Q90 42 90 30V18H154"/><path class="signal-line secondary" d="M90 42V62H154"/><rect x="8" y="27" width="28" height="30" rx="6"/><path d="M16 37h12m-12 8h8"/><circle cx="90" cy="18" r="8"/><circle cx="154" cy="18" r="8"/><rect x="145" y="53" width="18" height="18" rx="4"/>';
 const hero=document.querySelector('.intro');hero.append(svg(map,'hero-flow'));
 const brand=document.querySelector('.brand-mark');brand.classList.add('signal-brand');
 const iconPaths=['M7 5h18v14H15l-7 5v-5H7z','M6 23L24 5M10 5h14v14','M7 5h18v22H7zM12 11h8M12 16h8M12 21h5'];
 document.querySelectorAll('.nav-icon').forEach((el,i)=>{el.textContent='';const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 32 32');icon.innerHTML=`<path d="${iconPaths[i]}"/>`;el.append(icon)});
 const indicator=document.createElement('span');indicator.id='scenario-indicator';indicator.setAttribute('aria-hidden','true');byId('scenarios').prepend(indicator);
 let selected=null,spotFrame=0;
 function align(){if(!selected||!selected.isConnected||!selected.offsetHeight){indicator.hidden=true;return}indicator.hidden=false;indicator.style.width=selected.offsetWidth+'px';indicator.style.height=selected.offsetHeight+'px';indicator.style.transform=`translate(${selected.offsetLeft}px,${selected.offsetTop}px)`}
 new ResizeObserver(align).observe(byId('scenarios'));
 const preview=byId('flow-preview'),rail=document.querySelector('.journey');
 const phrases={idle:'Como funciona · nenhuma consulta enviada',prepared:'Prévia do cenário · ainda não consultado',loading:'Consulta em andamento · aguardando o servidor',answered:'Consulta concluída · confira a fonte',proposed:'Sua decisão · aguardando confirmação humana',confirming:'Registrando · aguardando confirmação do servidor',confirmed:'Registro confirmado pelo servidor',error:'Consulta ou ação não concluída · confira a mensagem'};
 function reveal(el){if(reduced.matches)return;el.animate([{opacity:.35,transform:'translateY(12px) scale(.98)'},{opacity:1,transform:'none'}],{duration:tokens.reveal,easing:tokens.ease})}
 function set(value,data={}){
   rail.dataset.flow=value;preview.dataset.state=value;
   preview.textContent=phrases[value]+(data.order?' · '+data.order:'');
   if(value==='confirmed'&&data.ticket)preview.textContent+=' · '+data.ticket;
   if(value==='prepared'){selected=data.button;align();document.querySelector('.chat').dataset.selection='prepared'}
   if(value==='idle'){selected=null;indicator.hidden=true;delete document.querySelector('.chat').dataset.selection}
   if(value==='answered')reveal(byId('facts'));
   if(value==='confirmed'&&!reduced.matches){rail.getAnimations().forEach(a=>a.cancel());rail.animate([{transform:'scale(.985)'},{transform:'scale(1.012)',offset:.55},{transform:'scale(1)'}],{duration:tokens.confirm,easing:tokens.ease})}
 }
 function prepare(index){const target=byId('scenarios').querySelectorAll('button')[index];if(target){document.querySelector('[data-tab=care]').click();target.click()}}
 function emptyQueue(){const box=document.createElement('div');box.className='queue-empty';const diagram=document.createElement('div');diagram.className='empty-map';diagram.append(svg(map));const label=document.createElement('p');label.textContent='COMO FUNCIONA · MAPA ILUSTRATIVO';diagram.append(label);const stages=document.createElement('div');stages.className='map-labels';for(const text of ['Pedido','Sua confirmação','Registro local']){const span=document.createElement('span');span.textContent=text;stages.append(span)}diagram.append(stages);const copy=document.createElement('div');copy.className='empty-copy';const title=document.createElement('h3');title.textContent='A próxima ação começa com você.';const p=document.createElement('p');p.textContent='Nenhuma solicitação registrada para este cliente. Consulte um pedido e confirme uma proposta para criar um registro local.';const cta=document.createElement('button');cta.className='primary';cta.textContent='Preparar cenário de atraso';cta.onclick=()=>prepare(1);const note=document.createElement('small');note.textContent='Só prepara a mensagem. Nenhuma solicitação é enviada automaticamente.';copy.append(title,p,cta,note);box.append(diagram,copy);return box}
 const welcome=document.querySelector('.empty-conversation');if(welcome){welcome.prepend(svg(map,'welcome-flow'));const note=document.createElement('span');note.className='welcome-label';note.textContent='COMO FUNCIONA · ILUSTRAÇÃO';welcome.prepend(note)}
 hero.addEventListener('pointermove',e=>{if(e.pointerType==='touch'||reduced.matches||!matchMedia('(hover:hover) and (pointer:fine)').matches)return;cancelAnimationFrame(spotFrame);spotFrame=requestAnimationFrame(()=>{const r=hero.getBoundingClientRect();hero.style.setProperty('--spot-x',e.clientX-r.left+'px');hero.style.setProperty('--spot-y',e.clientY-r.top+'px');hero.classList.add('spotlight-on')})});
 hero.addEventListener('pointerleave',()=>hero.classList.remove('spotlight-on'));
 reduced.addEventListener('change',()=>{if(reduced.matches){document.getAnimations().forEach(a=>a.cancel());hero.classList.remove('spotlight-on')}});
 window.FoodFlowMotion={set,reveal,emptyQueue,metrics:()=>{byId('cards').dataset.updated='true';reveal(byId('cards'))}};
 indicator.hidden=true;set('idle');
})();
