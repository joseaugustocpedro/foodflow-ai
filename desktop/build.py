"""Run on Windows with Python 3.12 and PyInstaller 6.22.3 available."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
        '--windowed', '--name', 'FoodFlow AI', '--paths', str(root),
        '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
        '--specpath', str(root / 'desktop'), '--collect-submodules', 'backend.app',
        '--hidden-import', 'uvicorn.logging', '--hidden-import', 'uvicorn.loops.asyncio',
        '--hidden-import', 'uvicorn.protocols.http.h11_impl', '--hidden-import', 'uvicorn.lifespan.on',
        '--copy-metadata', 'fastapi', '--copy-metadata', 'starlette', '--copy-metadata', 'pydantic']
for name in ['frontend', 'fixtures', 'artifacts/evaluations']:
    args += ['--add-data', str(root / name) + ';' + name]
args += [str(root / 'desktop/launcher.py')]
raise SystemExit(subprocess.call(args, cwd=root))
