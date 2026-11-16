# Reproduzir o executável

Windows x64, Python 3.12. A receita usa PyInstaller 6.22.3, modo onefile/windowed e janela Win32 via ctypes, sem Tk/Tcl. O executável contém Python e não exige Python do usuário final.

Em ambiente de build isolado e com downloads autorizados:

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r backend/requirements.txt -r desktop/requirements-build.txt
.\.venv-build\Scripts\python.exe desktop/build.py
```

Saída: `dist/FoodFlow AI.exe`. O `.spec` é gerado localmente e pode conter caminhos do build: não exportar esse arquivo gerado ou logs brutos. O script build.py é a receita portátil. Nesta execução foram reutilizadas dependências de aplicação existentes e instalado apenas o empacotador autorizado em `work/exe-build-tools`, com PYTHONPATH limitado ao processo de build.

Recursos: frontend, fixtures, avaliações sanitizadas usadas pelo painel. PyInstaller resolve `__file__` dos módulos no diretório temporário interno, preservando as resoluções existentes do backend. Nenhuma lógica do backend foi modificada. SQLite sempre recebe caminho em LOCALAPPDATA pelo iniciador.

Testes adicionais: `python -m pytest desktop/test_launcher.py -q`. Os testes originais permanecem em backend/tests. O teste manual deve usar o binário recém-gerado, incluindo duplo clique, encerramento, reinício, persistência, segunda instância e Nova demo. Não declarar Windows limpo validado com base somente na máquina de build.
