# Evidências de validação — FoodFlow AI

Este resumo distingue a **entrega final executada no Windows** dos testes históricos de n8n e das verificações reproduzidas por revisão independente. Nenhum indicador aqui representa qualidade de um modelo generativo real ou uso em produção.

## Versão Windows Motion Showcase V2

Fonte: relatório de validação da entrega consolidada de 15/11/2026 e arquivos JSON sanitizados do pacote validado.

| Componente | Resultado registrado |
|---|---|
| Pytest | 118 passed, 2 skipped (112 backend + 6 launcher) |
| Avaliações offline | 35 demo, 35 fake roteirizado, piloto separado 8 demo + 8 fake |
| HTTP local | 6 checks |
| Navegador | 17 checks originais, 23 checks Control Room, 9 checks Motion Showcase |
| Ciclo de vida Windows | Inicialização por duplo clique, banco persistente, Nova demo, segunda instância e encerramento validados no ambiente de teste |
| Vídeo | Captura real em WebM com aproximadamente 29 segundos |

Provas resumidas em [results.json](../evidence/validation/results.json), [HTTP](../evidence/validation/http-smoke.json), [navegador original](../evidence/validation/ui-results.json), [Control Room](../evidence/validation/redesign-results.json), [motion](../evidence/validation/motion-results.json) e [console](../evidence/validation/console-results.json).

## Automação n8n — execução independente anterior

A matriz N01–N08 foi aprovada em runtime local n8n 2.47.7 / Node 24.22.3 em 14/11/2026, com 16 registros correlacionados; a execução **não foi repetida na versão Windows final** e o runtime n8n **não acompanha o `.exe`**. [Documento N8N_VALIDATION](N8N_VALIDATION.md) e [provas sintéticas sanitizadas](../evidence/n8n/).

## Testes realizados pelo usuário

Na versão Windows entregue, os cenários ORD-1001 (consulta com fonte), ORD-1002 (confirmação e persistência do ticket) e ORD-1004 (acesso negado a outro cliente) foram exercitados no computador do responsável pelo projeto, com capturas de tela na revisão. Também foi verificado que o ticket permanecia após reinício. Estes testes pessoais não equivalem a certificação de portabilidade em todos os Windows.

## Limitações

- LLM online: **não executado**; a modalidade fake é um roteiro de teste, não modelo generativo.
- CI remoto, deploy e servidor público: **não executados**.
- Windows limpo sem Python, testes universais de antivírus/SmartScreen, acessibilidade com leitor de tela e carga: **não verificados**.
- Identidades públicas e métricas sem autenticação de operador não permitem uso seguro em produção aberta.
- Métricas de ROI, satisfação, tempo humano economizado e uso comercial: **não medidas**.

O workflow GitHub Actions fica inicialmente **somente com disparo manual** para que uma publicação pública não seja confundida com autorização para consumo de minutos e downloads de dependências de CI.
