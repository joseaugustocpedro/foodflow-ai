/* FoodFlow AI — motion, storytelling, media preview.
 * Progressive enhancement. Static content and core demo work without this file.
 * Does not load external scripts, access services, or persist customer data.
 */
'use strict';
(() => {
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-reduced-motion: reduce)');
  const motionButton = document.getElementById('motion-toggle');
  const motionLabel = motionButton?.querySelector('.motion-label');
  let manuallyOff = false;
  try { manuallyOff = localStorage.getItem('foodflow-motion-off') === '1'; }
  catch { /* Blocked storage is fine; the website stays functional. */ }
  const motionDisabled = () => manuallyOff || media.matches;
  const countNodes = [...document.querySelectorAll('[data-count]')];

  function finishCounters() {
    countNodes.forEach(el => {
      const target = Number(el.dataset.count);
      el.textContent = el.dataset.pad ? String(target).padStart(Number(el.dataset.pad),'0') : String(target);
      el.dataset.animated = 'true';
    });
  }
  function updateMotionPreference() {
    const off = motionDisabled();
    root.classList.toggle('motion-off', off);
    if (motionButton) {
      motionButton.setAttribute('aria-pressed', String(off));
      motionButton.setAttribute('aria-label', off ? 'Ativar animações' : 'Desativar animações');
      if (motionLabel) motionLabel.textContent = off ? 'EFEITOS OFF' : 'EFEITOS ON';
    }
    if (off) finishCounters();
  }
  updateMotionPreference();
  root.classList.add('motion-ready');

  motionButton?.addEventListener('click', () => {
    // Never override the operating system's accessibility setting.
    if (media.matches) {
      manuallyOff = true;
      updateMotionPreference();
      return;
    }
    manuallyOff = !manuallyOff;
    try { localStorage.setItem('foodflow-motion-off', manuallyOff ? '1' : '0'); } catch {}
    updateMotionPreference();
  });
  const onSystemChange = () => updateMotionPreference();
  if (media.addEventListener) media.addEventListener('change', onSystemChange);
  else if (media.addListener) media.addListener(onSystemChange);

  // Accessible reveal effects; additional blocks animate in a small cascading rhythm.
  const groups = [
    ['.pillars .pillar', 0.09, 'reveal-left'],
    ['.feature-grid .feature-tile', 0.105, 'reveal-scale'],
    ['.architecture-diagram .arch-node', 0.065, 'reveal-scale'],
    ['.stats-grid .stat', 0.065, 'reveal-scale'],
    ['.gallery-grid figure', 0.09, 'reveal-scale'],
    ['.gallery-heading', 0, 'reveal-left'],
    ['.faq-list details', 0.055, 'reveal-right'],
  ];
  const additionalReveals = [];
  groups.forEach(([selector, gap, variant]) => {
    document.querySelectorAll(selector).forEach((el, index) => {
      el.classList.add('reveal', variant);
      el.style.setProperty('--reveal-delay', `${Math.min(index * gap, .3).toFixed(3)}s`);
      additionalReveals.push(el);
    });
  });
  if ('IntersectionObserver' in window && !motionDisabled()) {
    const observer = new IntersectionObserver(entries => {
      for(const entry of entries) {
        if(entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      }
    }, {threshold: 0.05, rootMargin: '0px 0px 55px 0px'});
    additionalReveals.forEach(el => observer.observe(el));
  } else additionalReveals.forEach(el => el.classList.add('visible'));

  // One inexpensive scale transform for reading progress; no per-pixel DOM layout.
  const progress = document.getElementById('scroll-progress-fill');
  const header = document.querySelector('.site-header');
  let scrollPending = false;
  function drawScroll() {
    const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const position = Math.min(1, Math.max(0, window.scrollY / maxScroll));
    if(progress) progress.style.transform = `scaleX(${position.toFixed(4)})`;
    header?.classList.toggle('is-scrolled', window.scrollY > 35);
    scrollPending = false;
  }
  window.addEventListener('scroll', () => {
    if(!scrollPending) { scrollPending = true; requestAnimationFrame(drawScroll); }
  }, {passive: true});
  window.addEventListener('resize', drawScroll, {passive: true});
  drawScroll();

  const navEntries = [...document.querySelectorAll('.nav-links a[href^="#"]')];
  if ('IntersectionObserver' in window) {
    const navMap = new Map(navEntries.map(link => [link.hash.slice(1), link]));
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        navEntries.forEach(a => a.classList.toggle('is-active', a === navMap.get(entry.target.id)));
      });
    }, {threshold:0, rootMargin:'-22% 0px -68% 0px'});
    for(const key of navMap.keys()) {
      const section = document.getElementById(key);
      if(section) observer.observe(section);
    }
  }

  // Small, bounded pointer tilt for desktop; no event observers on mobile.
  const hero = document.querySelector('.hero-card');
  if(hero && window.matchMedia('(hover: hover) and (pointer: fine) and (min-width: 921px)').matches) {
    let tiltFrame = 0;
    let nextX = 0, nextY = 0;
    hero.addEventListener('pointermove', event => {
      if(motionDisabled()) return;
      const r = hero.getBoundingClientRect();
      nextX = ((event.clientX-r.left)/r.width-.5)*5;
      nextY = (.5-(event.clientY-r.top)/r.height)*5;
      if(tiltFrame) return;
      tiltFrame = requestAnimationFrame(() => {
        hero.style.setProperty('--tilt-x', `${nextX.toFixed(2)}deg`);
        hero.style.setProperty('--tilt-y', `${nextY.toFixed(2)}deg`);
        tiltFrame = 0;
      });
    }, {passive:true});
    hero.addEventListener('pointerleave', () => {
      hero.style.setProperty('--tilt-x','0deg');
      hero.style.setProperty('--tilt-y','0deg');
    });
  }

  // Evidence counters are from documented test runs, never new fabricated metrics.
  function animateCounter(el) {
    if(el.dataset.animated) return;
    if(motionDisabled()) { finishCounters(); return; }
    el.dataset.animated = 'true';
    const final = Number(el.dataset.count);
    const digits = Number(el.dataset.pad || 0);
    const started = performance.now();
    const duration = 950;
    const update = now => {
      const p = Math.min(1,(now-started)/duration);
      const eased = 1 - Math.pow(1-p,3.4);
      const value = Math.min(final, Math.round(final*eased));
      el.textContent = digits ? String(value).padStart(digits,'0') : String(value);
      if(p < 1 && !motionDisabled()) requestAnimationFrame(update);
      else el.textContent = digits ? String(final).padStart(digits,'0') : String(final);
    };
    requestAnimationFrame(update);
  }
  if('IntersectionObserver' in window && !motionDisabled()) {
    const observer = new IntersectionObserver(entries => {
      for(const entry of entries) {
        if(entry.isIntersecting) {
          animateCounter(entry.target);
          observer.unobserve(entry.target);
        }
      }
    }, {threshold:.48});
    countNodes.forEach(el => observer.observe(el));
  } else finishCounters();

  // Reproducible six-step architecture highlight; the actual project remains offline.
  const diagram = document.querySelector('.architecture-diagram');
  const flowNodes = [...document.querySelectorAll('.architecture-diagram .arch-node')];
  const flowText = document.getElementById('flow-status');
  const flowButton = document.getElementById('flow-replay');
  const flowMessages = [
    '01 · Interface local: HTML, CSS e JavaScript.',
    '02 · FastAPI: rotas e regras de aplicação.',
    '03 · Validação de identidade, pedido e políticas.',
    '04 · Proposta aguarda confirmação humana.',
    '05 · SQLite: ticket e eventos persistidos.',
    '06 · Worker: reenvio controlado e deduplicação.'
  ];
  let flowRunning = false;
  let flowAutoPlayed = false;
  const pause = ms => new Promise(resolve => setTimeout(resolve,ms));
  async function playFlow({manual=false}={}) {
    if(flowRunning || !flowNodes.length) return;
    flowRunning = true;
    flowButton?.setAttribute('disabled','');
    flowNodes.forEach(el => el.classList.remove('flow-done','flow-current'));
    if(!motionDisabled()) diagram?.classList.add('is-playing');
    for(let i=0;i<flowNodes.length;i++) {
      if(motionDisabled()) break;
      if(i>0) {flowNodes[i-1].classList.remove('flow-current');flowNodes[i-1].classList.add('flow-done');}
      flowNodes[i].classList.add('flow-current');
      if(flowText)flowText.textContent=flowMessages[i];
      await pause(470);
    }
    diagram?.classList.remove('is-playing');
    flowNodes.forEach(el => {el.classList.remove('flow-current');el.classList.add('flow-done');});
    if(flowText) flowText.textContent = 'Fluxo concluído · integração n8n validada separadamente; LLM online não executado.';
    flowButton?.removeAttribute('disabled');
    flowRunning=false;
    if(manual && flowButton) flowButton.focus({preventScroll:true});
  }
  flowButton?.addEventListener('click', () => playFlow({manual:true}));
  if(diagram && 'IntersectionObserver' in window && !motionDisabled()) {
    const observer = new IntersectionObserver(entries => {
      if(entries.some(e => e.isIntersecting) && !flowAutoPlayed) {
        flowAutoPlayed = true;
        observer.disconnect();
        playFlow();
      }
    }, {threshold:.27});
    observer.observe(diagram);
  }

  // Lightbox uses a native dialog for focus trapping, Escape, and semantics.
  const dialog = document.getElementById('gallery-lightbox');
  const expandedImage = document.getElementById('lightbox-image');
  const expandedCaption = document.getElementById('lightbox-caption');
  document.querySelectorAll('.gallery-expand').forEach(button => {
    button.addEventListener('click', () => {
      const img = button.querySelector('img');
      if(!img) return;
      if(dialog && typeof dialog.showModal==='function') {
        expandedImage.src = img.currentSrc || img.src;
        expandedImage.alt = img.alt;
        expandedCaption.textContent = img.alt + ' · Captura do aplicativo original.';
        dialog.showModal();
      } else {
        window.open(img.currentSrc || img.src,'_blank','noopener,noreferrer');
      }
    });
  });
  document.getElementById('lightbox-close')?.addEventListener('click', () => dialog?.close());
  dialog?.addEventListener('click', event => { if(event.target===dialog) dialog.close(); });
})();
