# Executar o FoodFlow AI

## Aplicativo Windows x64

O executável Windows é distribuído separadamente por **GitHub Releases**, após o envio do pacote de lançamento. Ele não é incluído no histórico de código.

1. Extraia o pacote Windows em uma pasta local.
2. Dê dois cliques em **FoodFlow AI.exe**.
3. Aguarde a janela exibir **Em execução**. O navegador padrão abrirá com a interface local.
4. Mantenha a janela de controle aberta enquanto usa a aplicação. Fechar apenas a aba não encerra o backend; fechar a janela de controle **encerra** o backend.
5. Para novos dados fictícios, use **Nova demo**. O banco anterior é preservado.

O SQLite fica em `%LOCALAPPDATA%\FoodFlowAI`. O programa usa uma porta local livre em `127.0.0.1`. Não precisa instalar Python, Node ou n8n. **Não foi testado em outra instalação limpa de Windows sem Python.** O `.exe` não possui assinatura digital; em caso de alerta SmartScreen/antivírus, não desative proteções para contornar.

## Executar do código-fonte (Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe scripts\run_local.py
```

No navegador: `http://127.0.0.1:8000`. Mantenha o terminal aberto e encerre com `Ctrl+C`. Dados fictícios, nenhum serviço pago e nenhuma automação externa configurados no modo padrão.

## Testes locais

```powershell
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe scripts\evaluate.py --mode all-offline
.\.venv\Scripts\python.exe scripts\evaluate.py --pilot --mode all-offline
```

Testes n8n reais só devem ser reexecutados com autorização específica, instalação isolada e credenciais sintéticas. Confira [o guia dedicado](../RUN_N8N_WINDOWS.md).
