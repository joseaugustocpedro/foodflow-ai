# Arquitetura e decisões

FastAPI entrega a API e a interface HTML/CSS/JS. SQLite guarda sessões, propostas, tickets, outbox, inbox e eventos. Fixtures e políticas são sintéticas. Não houve migração de stack na finalização.

`main.py` coordena rotas; `services.py` aplica titularidade, pedido-alvo e confirmação; `agent.py` contém baseline, adaptador Responses e renderer factual; `automation.py` implementa lease/retry/inbox; `metrics.py` agrega coortes; `boundary.py` limita Host/Origin e bytes recebidos.

1. **Fatos antes do texto:** servidor valida ferramentas e publica resultados confirmados. Modelo não é autoridade de status, ETA ou ações. Isso sacrifica liberdade textual em favor de fatos conferíveis.
2. **Humano antes da escrita:** tools propõem; rota de confirmação valida token, sessão, cliente, pedido e idempotência. Token nunca entra no contexto do modelo. Propostas descartadas são revogadas.
3. **Persistência antes do ACK:** ticket/outbox/eventos são atômicos; inbox deduplica event_id e exige payload idêntico. HTTP200 sozinho não confirma entrega.
4. **Falha recuperável:** três tentativas por ciclo, lease 15 s, dois ciclos manuais adicionais. N06 comprovou interrupções reais; nenhum timestamp de banco foi editado para simular tempo.
5. **Métricas com contexto:** request/tool/operation IDs pareiam eventos; since/until selecionam início e as_of limita observação. Confirmação posterior é evento imutável. Fallback não é sucesso LLM.

Limites: quatro rodadas e seis tentativas de ferramentas compartilhadas com fallback; orçamento assíncrono não garante hard deadline diante de SQLite síncrono. A demo tem identidades públicas, métricas sem autenticação real de operador e limite por sessão contornável. Não expor em rede pública.

O cenário usa 11/11/2026, 19h Brasília; dados técnicos são medidos em tempo real. A interface final apenas formata datas recebidas: payload e ISO técnico permanecem inalterados. Não existem ações financeiras, reembolso automático, canais externos ou atendentes reais.

Autoria: requisitos e direção do usuário, implementação assistida por Codex, auditorias documentais/técnicas Work identificadas no pacote de auditoria. Nenhum dado de economia, satisfação ou receita foi coletado.
