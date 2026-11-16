# Reproduzir a validação n8n no Windows

Esta instrução reproduz testes sintéticos supervisionados, não inicia um serviço permanente. Use somente após autorização para instalar/rodar n8n e criar credenciais locais. O LLM fica desabilitado. Não use `python -O`: o harness contém asserções de validação.

## Runtime isolado

Versões testadas: Node portátil **24.22.3 win-x64**, n8n **2.47.7**, Python **3.12.14**. A demonstração FoodFlow continua funcionando sem n8n.

Na execução da Etapa 06, o runtime foi instalado em `work/stage06-runtime` do workspace original, fora do projeto. Não é incluído no ZIP. Estrutura necessária para o harness:

```text
RUNTIME/
  node-v24.22.3-win-x64/node.exe
  n8n/node_modules/n8n/bin/n8n
```

Para uma instalação nova autorizada, em PowerShell, defina `$runtime` como um diretório novo fora do projeto. Use Node somente nos processos abaixo:

```powershell
$runtime = Join-Path (Split-Path -Parent $PWD.Path) 'foodflow-runtime'
New-Item -ItemType Directory -Path $runtime -ErrorAction Stop | Out-Null
$archive = Join-Path $runtime 'node-v24.22.3-win-x64.zip'
Invoke-WebRequest 'https://nodejs.org/dist/v24.22.3/node-v24.22.3-win-x64.zip' -OutFile $archive
Invoke-WebRequest 'https://nodejs.org/dist/v24.22.3/SHASUMS256.txt' -OutFile (Join-Path $runtime 'SHASUMS256.txt')
$expected = 'e612af99f626ab415ea225af6bce5c971feb448cb5cae250bb1c3fa50c5f7d9f'
if ((Get-FileHash $archive -Algorithm SHA256).Hash -ne $expected) { throw 'SHA-256 divergente' }
Expand-Archive -LiteralPath $archive -DestinationPath $runtime
$nodeRoot = Join-Path $runtime 'node-v24.22.3-win-x64'
$previousPath = $env:PATH
New-Item -ItemType File -Path "$runtime/isolated.npmrc" | Out-Null
try {
  $env:PATH = "$nodeRoot;$previousPath"
  & "$nodeRoot/node.exe" "$nodeRoot/node_modules/npm/bin/npm-cli.js" install --prefix "$runtime/n8n" --cache "$runtime/npm-cache" --userconfig "$runtime/isolated.npmrc" --registry https://registry.npmjs.org/ --no-audit --no-fund --omit=dev n8n@2.47.7
  if ($LASTEXITCODE -ne 0) { throw 'Instalação n8n falhou' }
} finally { $env:PATH = $previousPath }
```

O diretório de runtime deve estar fora da pasta exportável FoodFlow. Não instale globalmente. Confira também a entrada correspondente em SHASUMS256.txt; se versão/hash mudarem, interrompa e revise, não contorne a conferência. O comando acima documenta a instalação já realizada; uma nova instalação usa rede e as dependências transitivas disponíveis nessa ocasião. A procedência e o hash do Node estão no relatório técnico do pacote de auditoria; o SHA-256 esperado também aparece acima.

## Executar

Na raiz do projeto extraído, use o Python com `backend/requirements.txt` já disponível. Consulte RUN_LOCAL_WINDOWS.md para a demo e o setup Python. Nesta rodada as dependências Python existentes foram reutilizadas.

```powershell
# Ajuste caminhos para diretórios fora do projeto. PRIVATE deve ser NOVO.
.\.venv\Scripts\python.exe scripts/validate_n8n_local.py `
  --confirm-local-n8n `
  --runtime '..\foodflow-runtime' `
  --private '..\foodflow-testes-privados-01' `
  --output 'artifacts\minha-validacao-n8n'
```

O script confere portas livres **5678, 5679, 8000 e 8006**, gera segredos novos em memória, cria conta local sintética e credenciais, importa/ativa o workflow somente no n8n local, confirma tickets sintéticos e executa N01–N08. Não acessa contas existentes. Não precisa colar senhas, tokens ou chaves. Se uma porta estiver ocupada, identifique o processo e encerre apenas sua própria instância; não mate processos por nome nem abra firewall.

O modo externo de runners exige token, gerado automaticamente pelo script; nenhum runner de código adicional é iniciado. O broker fica em loopback. Saídas de terminal e bancos privados ficam em PRIVATE; não os publique. A evidência exportável vai a OUTPUT. O processo termina o backend/n8n no bloco finally, preserva metadados e limpa payloads de execuções marcadas para exclusão. Se o computador/processo for interrompido abruptamente, inspecione os PIDs e a pasta privada antes de retomar; não reutilize credenciais nem declare cleanup concluído automaticamente.

N04 aguarda retries reais; N06 aguarda três leases de 15 s. Falhas induzidas são esperadas: N02/N03 terminam com envio pendente, e N08 recebe 500 do n8n refletindo 422/409 na inbox. Resultado aprovado é a rejeição sem falso ACK. A pasta de evidências não deve conter `.n8n`, banco, log privado, cookie, header ou segredo.

## Conferir e apresentar

Leia `cases.json`, `runtime-executions.jsonl` e `retention-cleanup.json`. Para as evidências desta entrega, confira também `runtime-db-metadata.json`: IDs do hook foram confrontados com o banco real. Snapshots isolados do coletor antigo não certificam n8n. A opção C de LLM online permanece desabilitada.

Para apresentar os três fluxos na entrevista: consulte ORD-1001 com fonte; consulte ORD-1002, confirme e mostre ticket/recuperação comprovada nas evidências; tente ORD-1004 como Cliente A e mostre o bloqueio. Diga que os dados são fictícios, o projeto é independente e ACK significa entrada na fila local, não atendimento humano realizado. O relógio de negócio é fixo em 11/11/2026; timestamps técnicos das execuções são reais.

Após a revisão, não iniciar GitHub, CI remoto, vídeo publicado ou deploy sem autorização separada.
