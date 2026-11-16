# FoodFlow AI / Control Room

## Direção

Conversa no centro; roteiro como contexto e fatos como prova. A sidebar escura organiza o produto, o workspace quente recebe a conversa e o coral marca decisões. O símbolo SVG original conecta três nós. Não foram copiadas marcas ou telas de terceiros. Não há fonte remota, imagem gerada, CDN ou framework novo.

## Tokens e componentes

| Papel | Token |
|---|---|
| Fundo / texto | #F5F4EF / #101417 |
| Navegação / superfície | #101417, #191F22 / branco |
| Texto secundário | #59615F |
| Ação principal | #FF694A com texto #28150F |
| Ênfase textual coral | #A62D16 |
| Estado local decorativo | #63CBB5 |
| Bordas | #DEDFD7 |
| Tipografia | Segoe UI, system-ui, sans-serif; arquivos do sistema |
| Espaçamento | 4, 8, 12, 16, 20, 24, 28 px |
| Radius | controles 7–8 px, chat 12 px, fontes 4 px |

Somente números vindos da API entram nas métricas. Etapas 01/02/03 são rótulos da jornada, não indicadores inventados de execução. O usuário visualiza proposta, confirma com clique e recebe o estado persistido. Datas ISO permanecem nos detalhes. A identidade da demo e suas limitações estão no topo e rodapé.

## Layout responsivo

Desktop: rail de 192 px (176 em telas intermediárias), contexto de 150–190 px, chat flexível, evidência de 205–270 px. Abaixo de 1050 px a prova passa para baixo da conversa; abaixo de 768 px a navegação vira três áreas horizontais, roteiro compacto e prova inicialmente recolhida. O botão Ver evidências expande sem perder dados. Esc dentro da prova recolhe e devolve foco ao botão.

Container queries são um fallback adicional para espaços estreitos e zoom CSS. Nenhum conteúdo é escondido por clipping para fazer o teste de overflow passar. Textareas podem crescer com limites e histórico tem rolagem própria. Alvos mobile principais têm 44 px ou mais.

## Movimento

`--fast:150ms`, `--motion:240ms`, `--ease:cubic-bezier(.22,1,.36,1)`. Entrada do título 440 ms; painéis 260 ms de entrada e 200 ms de saída; mensagens 220 ms; confirmação 260 ms; fontes 220 ms. Deslocamentos máximos 8 px. Registros 2 e 3 recebem 40/80 ms de escalonamento; listas maiores não acumulam atraso.

Crossfade usa uma cópia temporária inerte, sem IDs, sem foco, aria-hidden e removida no fim. Mudanças reais de seção e foco são imediatas. Troca rápida remove a cópia anterior. Indicador de navegação desliza por CSS. Selecionar cenário prepara o composer, não envia. Não há espera artificial, pulso infinito, vídeo, som, parallax ou ação ligada ao fim de animação. Carregamento usa estado textual real e aria-busy.

`prefers-reduced-motion:reduce` desliga animações, transições, pseudo-elementos e scroll suave; animação contextual via JS também consulta essa preferência. A interface permanece utilizável sem movimento.

## Acessibilidade e limites

IDs e rótulos usados pelos 17 checks originais foram mantidos. Botões nativos, aria-current, aria-expanded, live status, foco em heading e mensagem de stale permanecem. Sete combinações principais de texto são verificadas por cálculo WCAG de luminância (≥4,5:1); isso não certifica todos os estados nem WCAG integral. Zoom CSS não equivale a teste manual do zoom nativo; leitor de tela não foi verificado.

## Referências realmente consultadas

- [Linear: hierarquia e menor competição visual](https://linear.app/now/behind-the-latest-design-refresh). Usado como princípio, não como layout copiado.
- [MDN: View Transitions](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition). Avaliada; a implementação usa CSS/DOM inerte para não depender da API.
- [W3C: movimento desativável](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions). Fundamenta a preferência por redução de movimento.

Não foram inspecionados pins ou vídeos do TikTok/Pinterest. Nenhuma alegação de resultado comercial ou IA online foi acrescentada.

## Evolução final: Signal & Flow / Motion Showcase V2

A camada `motion.css`/`motion.js` evolui o Control Room existente; as especificações acima descrevem o checkpoint V1. A versão final usa hero escuro/coral, tipografia ampliada, SVGs originais, mapa vazio explicitamente ilustrativo e KPIs retornados pela API. Tokens: entrada até 700 ms; navegação 240/320 ms; spring 280/300 ms; confirmação 420 ms. Prioridade a transform/opacity. O spotlight acompanha o ponteiro somente no hero, sem touch/reduced motion.

O trilho diferencia prévia não consultada, consulta em andamento, resposta, proposta, confirmação em andamento, registro persistido e erro. Não decide ações nem conta sucesso: recebe notificações do fluxo existente. Um novo teste retém a resposta real do servidor e comprova que o estado confirmado não aparece antes dela. A aplicação não contém vídeo em background ou atrasos artificiais.

Mobile: painel limita pintura horizontal transitória; evidência entra verticalmente; controles medidos mantêm pelo menos 44 px durante a animação. Reduced motion desliga as animações, inclusive WAAPI e o indicador dos cenários. [Validação e capturas](docs/VERIFICACAO.md).
