# n8n: prova local preservada da Etapa 06

**N01–N08 PASSED**, n8n 2.47.7 / Node portátil 24.22.3, em 14/11/2026. Run: `stage06-20261114T132347Z-e8fe98`. Não foi reexecutado na finalização; código da integração, workflow e evidências foram preservados.

| Caso | Prova | Execution IDs |
|---|---|---|
| N01 | Inbox persistida e ACK correspondente | 1 |
| N02 | Webhook rejeita segredo errado com 403; zero inbox | Sem execução: rejeição prévia |
| N03 | Callback rejeitado com 403, sem confirmação | 2 |
| N04 | Três tentativas com n8n parado; reinício e retry recuperam o evento | 3 |
| N05 | 504 após commit, reenvio idempotente | 4–5 |
| N06 | Três workers interrompidos, lease real, falha terminal e recovery | 6–9 |
| N07 | HTTP200 com ACK inválido não confirma; recuperação | 10–11 |
| N08 | Replay idempotente; extra 422, evento inexistente/motivo conflitante 409 na inbox | 12–16 |

O n8n mapeou os erros de callback de N08 para HTTP500 externo. São erros esperados de workflow, não falsos sucessos. N06 usa relay TCP local para reter ACK genuíno após persistência e interromper o processo real; não usa sender fake nem edição de lease.

Evidências: [casos e snapshots](../evidence/n8n/cases.json), [hook real](../evidence/n8n/runtime-executions.jsonl), [metadados do SQLite n8n](../evidence/n8n/runtime-db-metadata.json), [limpeza](../evidence/n8n/retention-cleanup.json). São 16 IDs/status correlacionados: 12 success e 4 error esperados. O ID 15 usa event_id propositalmente inexistente; aparece no JSONL e banco, fora do filtro do evento original em cases.json.

Snapshots do coletor antigo dizem NOT_EXECUTED isoladamente porque não certificam runtime por si. A conclusão usa sua correlação com hook e banco reais. A auditoria independente da Etapa 06 conferiu a consistência dessas evidências, **não repetiu o runtime n8n**.

`save=none` faz exclusão lógica: foram observados 16 payloads temporários e removidos após parada; zero linhas de payload, metadados preservados. Não é apagamento forense. O runtime privado, bancos, credenciais e logs não acompanham o repositório. Duas tentativas externas do runtime foram bloqueadas pelo guard local; não liberadas.

Hash do workflow principal: `39c312edc3f193e6f94cbc1d28d2f2c56a50aea28b556db35ca143b3d30a4c02`. O arquivo histórico de auditoria, mantido fora deste repositório público, preserva o ZIP íntegro da Etapa 06 e seu SHA-256 `6dbe05674bce7b67719ca825d3965ad0343d266ebad1133586a004b2834a0719`, com relatório completo e histórico. Hashes das versões efetivamente persistidas estão na projeção do banco.

Demo offline e integração validada são estados diferentes. A demo não inicia n8n; ACK significa fila local, não atendimento humano. [Reprodução autorizada no Windows](../RUN_N8N_WINDOWS.md). LLM online e CI remoto: NOT_EXECUTED.
