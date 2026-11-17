# FoodFlow AI — Showcase Motion V2

Website estático de portfólio, sem backend público, preparado para GitHub Pages. O app FoodFlow AI original é independente e roda localmente.

## Ver o site

Abra `index.html` ou rode `python -m http.server 8080` dentro de `site/`. A navegação é estática, não há etapa de build ou dependências npm.

## Funcionalidades

- Visual grafite/coral alinhado ao projeto original; movimento cinematográfico no título e leve parallax de desktop.
- Scroll reveals progressivos, barra de leitura e navegação ativa.
- Três cenários de **simulação determinística** (ORD-1001, ORD-1002 e ORD-1004) com progresso visual, validação e confirmação ilustrativa.
- Arquitetura animada em seis etapas com replay manual.
- Testes documentados com contadores em entrada; imagens originais com zoom modal; vídeo de 29 segundos do protótipo real.
- Transições curtas, design responsivo, teclado, `prefers-reduced-motion` e opção **EFEITOS ON/OFF**.

O site usa JavaScript nativo e não carrega bibliotecas de animação. O controle dos efeitos armazena uma preferência no `localStorage` do navegador, quando permitido. Não armazena dados de visitantes nem faz chamadas à API FoodFlow.

## Transparência

Os números (118 testes aprovados, 86/86 cenários offline, 49 verificações no navegador, N01–N08 de n8n) são resultados documentados em novembro/2026, **não** indicadores de clientes reais. O LLM online não foi executado. Nenhuma solicitação é gravada por esta página. Imagens e WebM são servidos do repositório público e podem não aparecer offline.

O pacote Windows está disponível em [v1.0.0](https://github.com/joseaugustocpedro/foodflow-ai/releases/tag/v1.0.0). NÃO exponha o servidor local a usuários externos.

## Arquivos

`index.html` — estrutura, semântica e SEO.
`styles.css` — layout, efeitos, responsividade.
`app.js` — demo determinística.
`motion.js` — efeitos de rolagem, contadores, arquitetura guiada, galeria e preferência de movimento.
`assets/` — marca e favicon SVG.
`MOTION_DESIGN_NOTES.md` — decisões, referências e melhorias possíveis.

## Publicação

O workflow `.github/workflows/deploy-showcase.yml` publica somente `site/` mediante disparo manual em GitHub Actions. Não publica backend, SQLite nem scripts de avaliação.
