# FoodFlow AI — Website / Showcase

Landing page de portfólio, responsiva e sem dependências de build, baseada nas evidências públicas do [FoodFlow AI](https://github.com/joseaugustocpedro/foodflow-ai).

## Abrir localmente

Abra `index.html` no navegador. Também pode iniciar um servidor estático na pasta `site`:

```bash
python -m http.server 8080
```

Em seguida abra `http://localhost:8080`.

Não é necessário instalar Node.js, configurar variáveis de ambiente, criar banco de dados ou fornecer credenciais.

## O que o site faz

- Landing page com informações verificáveis do protótipo.
- Demo **visual, determinística e independente** dos cenários ORD-1001, ORD-1002 e ORD-1004.
- Ilustra consulta com fonte, solicitação sujeita à confirmação humana e bloqueio de acesso.
- Galeria com capturas reais via URLs públicas do repositório.
- Links para documentação, GitHub, vídeo e release Windows.
- Página responsiva, navegação por teclado, foco visível, semântica HTML e suporte a `prefers-reduced-motion`.
- SEO básico com metadados, `robots.txt` e `sitemap.xml`.

## O que ele **não** faz

- Não executa FastAPI nem n8n.
- Não chama IA online.
- Não armazena dados de clientes, pedidos ou tickets.
- Não publica as APIs locais do FoodFlow na internet.
- Não representa um serviço comercial ou pronto para produção.

A demonstração altera somente a interface do navegador. Não confundir os resultados visuais com execução do backend real.

## Organização

- `index.html`: conteúdo, links e estrutura semântica.
- `styles.css`: visual, layout e responsividade.
- `app.js`: demonstração guiada, navegação mobile, copiar comandos e interações.
- `assets/`: SVG da marca e favicon.

## Publicar com GitHub Pages

O workflow `.github/workflows/deploy-showcase.yml` (na raiz do repositório) publica **somente** a pasta `site/`. Ele usa `workflow_dispatch` para evitar publicação automática. Após mesclar a branch contendo este website:

1. Abra **Settings → Pages** no repositório e selecione **GitHub Actions** em *Build and deployment*.
2. Abra **Actions → Deploy FoodFlow Showcase → Run workflow**, selecione a branch principal e execute.
3. Verifique a URL `https://joseaugustocpedro.github.io/foodflow-ai/` quando o GitHub confirmar o deploy.

Observação: a URL acima é o endereço **esperado**, não indica que a publicação já tenha ocorrido.

## Fontes e limitação das imagens

As capturas mostradas na galeria são arquivos públicos em `/media/` do repositório original, carregados por `raw.githubusercontent.com`. Elas dependem de internet; a landing page e a demo funcionam localmente sem essas imagens. As fontes Google Fonts são opcionais e também usam fallback local.

## Autoria, escopo e licenciamento

Projeto original com direção, requisitos e validação humana e implementação assistida por Codex. O website de apresentação reutiliza informações públicas do projeto e não reivindica vínculo com o iFood. Observe os termos da licença MIT do repositório.
