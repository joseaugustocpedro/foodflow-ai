/* FoodFlow AI — showcase estático e demonstrador visual.
 * Cenários determinísticos baseados nos documentos públicos; nenhuma API, banco de dados,
 * modelo de IA ou credencial é utilizada nesta página. */
'use strict';

const SCENARIOS = Object.freeze({
  '1001': {
    title: 'Consulta com fonte', order: 'ORD-1001', button: 'Consultar pedido',
    placeholder: 'Consulta com dados verificáveis',
    description: 'Consulte o pedido ORD-1001 e visualize uma resposta baseada em registros fictícios.',
    question: 'Qual o status do pedido ORD-1001?',
    response: '<strong>Pedido em preparo.</strong> Última atualização registrada: 11/11/2026 às 18h42 (Brasília). Previsão registrada: 19h30. Essa previsão não é uma garantia de entrega.<small>Fonte: registro sintético ORD-1001 · cenário de 11/11/2026</small>',
    evidence: {access:'Autorizado · demo', record:'Consulta ilustrativa', note:'Consulta autorizada e resposta apoiada no registro fictício, não em texto gerado por IA.'}
  },
  '1002': {
    title: 'Solicitação por atraso', order:'ORD-1002', button:'Verificar solicitação',
    placeholder:'Primeiro verificar. Depois decidir.',
    description:'O sistema pode propor uma solicitação, mas nunca registrá-la antes da confirmação humana.',
    question:'Meu pedido ORD-1002 está atrasado. Pode abrir uma solicitação?',
    response:'O pedido foi conferido com as regras fictícias. Uma <strong>proposta de solicitação por atraso</strong> está disponível, mas ainda não foi registrada.<small>Próxima etapa: decidir se deseja confirmar a solicitação.</small>',
    evidence:{access:'Autorizado · demo',record:'Confirmação pendente',note:'A interface ilustra a barreira entre propor uma solicitação e registrar uma ação persistente.'}
  },
  '1004': {
    title:'Restrição de acesso', order:'ORD-1004', button:'Testar acesso',
    placeholder:'Privacidade antes da resposta.',
    description:'O Cliente A tenta consultar um pedido que não lhe pertence e não deve receber informações protegidas.',
    question:'Qual o status do pedido ORD-1004?',
    response:'<strong>Acesso negado.</strong> O pedido solicitado não pertence à identidade fictícia selecionada. Nenhum dado protegido do pedido foi exibido.<small>Controle ilustrado: autorização de cliente e pedido realizada pelo servidor original.</small>',
    evidence:{access:'Negado · titularidade',record:'Nenhum',note:'A interface não divulga status, previsão ou outros atributos de pedidos não autorizados.'}
  }
});

let currentScenario = '1001';
let simulationStatus = 'idle';
let busy = false;
let toastTimer;

const byId = id => document.getElementById(id);
const chatArea = byId('chat-area');
const actionArea = byId('demo-actions');
const tabButtons = Array.from(document.querySelectorAll('.scenario-tab'));

function escapeText(s) {
  return String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function setStages(stage) {
  const stages = document.querySelectorAll('.stage');
  stages.forEach((element,index)=>{
    element.classList.toggle('is-current',index===stage);
    element.classList.toggle('is-complete',index<stage);
  });
}
function resetAction() {
  const item = SCENARIOS[currentScenario];
  actionArea.innerHTML = `<button id="demo-run" type="button" class="btn btn-coral btn-demo">${escapeText(item.button)} <span aria-hidden="true">↗</span></button><span id="demo-action-hint">Clique para executar a simulação.</span>`;
  byId('demo-run').addEventListener('click', runSimulation);
}
function selectScenario(id, focus=false) {
  if (!SCENARIOS[id] || busy) return;
  currentScenario=id;
  simulationStatus='idle';
  const s=SCENARIOS[id];
  tabButtons.forEach(tab=>{
    const active=tab.dataset.scenario===id;
    tab.classList.toggle('is-active',active);
    tab.setAttribute('aria-selected',String(active));
    tab.tabIndex=active?0:-1;
    if(active && focus)tab.focus();
  });
  const panel=byId('demo-panel');
  panel.setAttribute('aria-labelledby',`tab-${id}`);
  byId('scenario-title').textContent=s.title;
  byId('scenario-order').textContent=s.order;
  byId('evidence-order').textContent=s.order;
  byId('evidence-identity').textContent='Cliente A';
  byId('evidence-access').textContent='Pendente';
  byId('evidence-record').textContent='Aguardando';
  byId('evidence-note').textContent='A verificação de titularidade ocorre antes de publicar os dados do pedido.';
  chatArea.innerHTML = `<div class="chat-placeholder"><div class="placeholder-symbol">✳</div><strong>${escapeText(s.placeholder)}</strong><p>${escapeText(s.description)}</p></div>`;
  setStages(0);
  resetAction();
}
function addMessage(type,html) {
  const node=document.createElement('div');
  node.className='chat-msg '+type;
  // Only constant content from this source file is passed here.
  node.innerHTML=html;
  chatArea.appendChild(node);
  return node;
}
async function runSimulation() {
  if(busy || simulationStatus!=='idle')return;
  busy=true;
  const id=currentScenario;
  const s=SCENARIOS[id];
  simulationStatus='running';
  chatArea.innerHTML='';
  addMessage('user',escapeText(s.question));
  const btn=byId('demo-run');
  btn.disabled=true;
  btn.textContent='Verificando…';
  byId('demo-action-hint').textContent='Execução demonstrativa, sem servidor.';
  await new Promise(resolve=>setTimeout(resolve,500));
  addMessage(id==='1004'?'system alert':'system',s.response);
  byId('evidence-access').textContent=s.evidence.access;
  byId('evidence-record').textContent=s.evidence.record;
  byId('evidence-note').textContent=s.evidence.note;
  if(id==='1002') {
    setStages(1);
    simulationStatus='pending';
    const card=document.createElement('div');
    card.className='confirmation-card';
    card.innerHTML=`<strong>Confirmação humana necessária</strong><p>Deseja ilustrar o registro de uma solicitação referente a ORD-1002? Nada será salvo.</p><div class="confirmation-actions"><button type="button" class="mini-btn" id="discard-ticket">Descartar</button><button type="button" class="mini-btn confirm" id="confirm-ticket">Confirmar registro ✓</button></div>`;
    chatArea.appendChild(card);
    byId('discard-ticket').addEventListener('click',()=>completeProposal(false));
    byId('confirm-ticket').addEventListener('click',()=>completeProposal(true));
    actionArea.innerHTML='<span>Proposta gerada. A decisão está nas suas mãos.</span>';
  } else {
    simulationStatus='done';
    setStages(2);
    actionArea.innerHTML='<button type="button" class="btn btn-coral btn-demo" id="restart-demo">Reiniciar cenário ↻</button><span>Verificação ilustrativa concluída.</span>';
    byId('restart-demo').addEventListener('click',()=>selectScenario(id));
  }
  busy=false;
}
function completeProposal(confirmed) {
  if(simulationStatus!=='pending')return;
  simulationStatus='done';
  const card=chatArea.querySelector('.confirmation-card');
  if(card)card.remove();
  if(confirmed){
    addMessage('system','<strong>Confirmação recebida nesta simulação.</strong> A tela ilustra um ticket de atendimento, mas não existe registro em SQLite nesta página.<small>No aplicativo original, a confirmação é validada e o ticket é persistido localmente.</small>');
    byId('evidence-record').textContent='Simulado · não persistido';
    byId('evidence-note').textContent='Somente mudança visual: nenhum ticket foi criado no backend ou salvo nesta página.';
  } else {
    addMessage('system alert','<strong>Solicitação descartada.</strong> Nenhum registro foi criado.<small>A decisão de não prosseguir também faz parte de um fluxo responsável.</small>');
    byId('evidence-record').textContent='Descartado';
    byId('evidence-note').textContent='Fluxo encerrado sem registro de solicitação.';
  }
  setStages(2);
  actionArea.innerHTML='<button type="button" class="btn btn-coral btn-demo" id="restart-demo">Reiniciar cenário ↻</button><span>Etapa concluída nesta simulação.</span>';
  byId('restart-demo').addEventListener('click',()=>selectScenario(currentScenario));
}

tabButtons.forEach((btn,index)=>{
  btn.addEventListener('click',()=>selectScenario(btn.dataset.scenario));
  btn.addEventListener('keydown',event=>{
    if(!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;
    event.preventDefault();
    let next=index;
    if(event.key==='ArrowRight')next=(index+1)%tabButtons.length;
    if(event.key==='ArrowLeft')next=(index-1+tabButtons.length)%tabButtons.length;
    if(event.key==='Home')next=0;
    if(event.key==='End')next=tabButtons.length-1;
    selectScenario(tabButtons[next].dataset.scenario,true);
  });
});

function showToast(message){const toast=byId('toast');toast.textContent=message;toast.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove('show'),3200)}
byId('copy-command').addEventListener('click',async()=>{
  const commands='py -3.12 -m venv .venv\n.\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt\n.\\.venv\\Scripts\\python.exe scripts\\run_local.py';
  try{
    if(navigator.clipboard && window.isSecureContext){await navigator.clipboard.writeText(commands)}
    else{const text=document.createElement('textarea');text.value=commands;text.style.position='fixed';text.style.opacity='0';document.body.appendChild(text);text.select();const ok=document.execCommand('copy');text.remove();if(!ok)throw new Error('copy unavailable')}
    showToast('Comandos copiados! Execute na pasta do repositório.');
  }catch{showToast('Não foi possível copiar automaticamente. Selecione os comandos no terminal acima.')}
});
const menuToggle=byId('menu-toggle');const navLinks=byId('nav-links');
menuToggle.addEventListener('click',()=>{const open=menuToggle.getAttribute('aria-expanded')!=='true';menuToggle.setAttribute('aria-expanded',String(open));menuToggle.setAttribute('aria-label',open?'Fechar menu':'Abrir menu');navLinks.classList.toggle('open',open)});
navLinks.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{menuToggle.setAttribute('aria-expanded','false');menuToggle.setAttribute('aria-label','Abrir menu');navLinks.classList.remove('open')}));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&navLinks.classList.contains('open')){menuToggle.click();menuToggle.focus()}});
if('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches){
  const observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target)}})},{threshold:.08,rootMargin:'0px 0px 20px 0px'});
  document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));
}else{document.querySelectorAll('.reveal').forEach(el=>el.classList.add('visible'))}
selectScenario('1001');
