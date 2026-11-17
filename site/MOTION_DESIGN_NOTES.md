# Motion design — decisões técnicas

## Referências (pesquisa pública, novembro/2026)

- [SaaSKiller](https://saaskiller.app/): narrativa da ideia ao resultado em passos e painéis explicativos. Não copiamos componentes, imagens ou textos.
- [Linear](https://linear.app/): hierarquia limpa e interface do próprio software em destaque.
- [Framer Fluxframe](https://www.framer.com/marketplace/templates/fluxframe/): apresentação de produto com entradas conforme rolagem e ilustrações de funcionalidades.
- [Framer Eventide](https://www.framer.com/marketplace/templates/eventide/): valorização de fluxos técnicos e controles interativos de agentes, em escala mais intensa do que é necessário neste portfólio.
- [Motion — inView](https://motion.dev/docs/inview): base conceitual para entradas disparadas por observação de viewport.
- [MDN — Intersection Observer](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API): API nativa adotada.
- [web.dev — High performance CSS animations](https://web.dev/articles/animations-guide): priorizar `transform` e `opacity`, evitando deslocamento de layout.
- [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion): remover movimentos não essenciais para visitantes que solicitam redução.

## Arquitetura da animação

A página segue estática em HTML/CSS/JS, sem bibliotecas extras. `app.js` executa os cenários; `motion.js` gerencia movimentos e galeria; `styles.css` contém estilos, keyframes e regras responsivas.

O conteúdo **não depende das animações para ser exibido**: `.reveal` só fica oculto quando JavaScript e observadores de viewport estão disponíveis. Contadores numéricos mantêm valores originais no HTML. A confirmação em ORD-1002 continua puramente ilustrativa. A galeria utiliza `<dialog>` para modal, sem depender de componentes de terceiros.

## Próximas melhorias opcionais

- Medição real de Lighthouse/Core Web Vitals após a publicação.
- Capturas de vídeo H.264/MP4 compatíveis em maior variedade de navegadores, somente se o arquivo de origem for fornecido e autorizado.
- Adicionar imagens otimizadas localmente para acesso offline, preservando os arquivos originais do projeto.
- Testes com leitores de tela, teclado e aparelhos físicos.
