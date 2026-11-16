"""Windows offline launcher; never starts an external service or subprocess."""
import ctypes
import hashlib
import http.client
import json
import logging
import os
from pathlib import Path
import re
import socket
import threading
import time
import traceback
from desktop.native_window import Window
import uuid
import webbrowser


def offline(database):
    for key in list(os.environ):
        if key.startswith(('OPENAI_', 'N8N_', 'FOODFLOW_')):
            del os.environ[key]
    os.environ.update(FOODFLOW_ALLOW_ONLINE_LLM='false', FOODFLOW_WORKER='false',
                      FOODFLOW_DB_PATH=str(database), FOODFLOW_RUN_ID='interactive')


def load_database(folder):
    pointer = folder / 'active.json'
    if pointer.exists():
        name = json.loads(pointer.read_text(encoding='utf-8'))['database']
        if not re.fullmatch(r'demo(?:-[a-f0-9]{32})?\.sqlite3', name):
            raise ValueError('Invalid database selector')
        return folder / name
    return folder / 'demo.sqlite3'


class Control:
    def __init__(self, root, folder):
        self.root, self.folder = root, folder
        self.server = self.thread = self.sock = None
        self.closing = self.resetting = False
        self.url = None
        root.control('STATIC', 'FoodFlow AI — Demo sintética offline', 22, 20, 580, 30)
        root.control('STATIC', 'Somente neste computador. n8n N01–N08 é evidência histórica.\nRuntime n8n não incluído. LLM online desativado.\nFechar o navegador não encerra o servidor.', 22, 55, 580, 65)
        self.status = root.control('STATIC', 'Iniciando…', 22, 135, 580, 95)
        self.open_button = root.control('BUTTON', 'Abrir interface', 22, 255, 160, 32, self.open_browser)
        self.new_button = root.control('BUTTON', 'Nova demo', 210, 255, 160, 32, self.new_demo)
        root.control('BUTTON', 'Encerrar', 405, 255, 160, 32, self.close)
        self.open_button.configure(state='disabled')
        self.new_button.configure(state='disabled')
        root.on_close = self.close
        self.start()

    def start(self):
        try:
            self.database = load_database(self.folder)
            offline(self.database)
            import uvicorn
            from backend.app.main import app
            owner = self
            class ErrorCapture(logging.Handler):
                def emit(self, record):
                    if record.exc_info:
                        owner.diagnostic(record.exc_info[1])
            logging.getLogger('uvicorn.error').addHandler(ErrorCapture())
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.sock.bind(('127.0.0.1', 0))
            self.sock.listen(128)
            self.url = 'http://127.0.0.1:' + str(self.sock.getsockname()[1])
            self.server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False,
                loop='asyncio', http='h11', ws='none', lifespan='on', timeout_graceful_shutdown=5))
            self.thread = threading.Thread(target=self.serve, daemon=True)
            self.thread.start()
            self.deadline = time.monotonic() + 30
            self.root.after(150, self.ready)
        except Exception as exc:
            self.diagnostic(exc)
            self.fail()

    def serve(self):
        try:
            self.server.run(sockets=[self.sock])
        except BaseException as exc:
            self.diagnostic(exc)

    def diagnostic(self, exc):
        record = {'error': type(exc).__name__, 'frames': [
            {'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)]}
        (self.folder / 'last-error.json').write_text(json.dumps(record), encoding='utf-8')

    def ready(self):
        if self.closing or self.resetting:
            return
        try:
            connection = http.client.HTTPConnection('127.0.0.1', int(self.url.rsplit(':', 1)[1]), timeout=0.5)
            try:
                connection.request('GET', '/health')
                response = connection.getresponse()
                assert response.status == 200
                data = json.loads(response.read())
            finally:
                connection.close()
            assert data['status'] == 'ok' and not data['llm_online_enabled']
            assert data['automation'] == 'not_configured'
        except Exception as exc:
            if time.monotonic() < self.deadline and self.thread.is_alive():
                self.root.after(200, self.ready)
            else:
                if not (self.folder / 'last-error.json').exists():
                    self.diagnostic(exc)
                self.fail()
            return
        self.status.set('Em execução: ' + self.url + '\nBanco persistente: %LOCALAPPDATA%\\FoodFlowAI\\' + self.database.name)
        (self.folder / 'runtime.json').write_text(json.dumps({'pid': os.getpid(), 'url': self.url,
            'database': self.database.name, 'mode': 'demo'}), encoding='utf-8')
        self.open_button.configure(state='normal')
        self.new_button.configure(state='normal')
        self.open_browser()

    def open_browser(self):
        if self.url:
            webbrowser.open(self.url)

    def fail(self):
        self.status.set('Não foi possível iniciar. Encerre e confira se a pasta de dados é gravável.\nNenhum banco anterior foi apagado.')
        if self.server:
            self.server.should_exit = True

    def new_demo(self):
        if self.closing or self.resetting:
            return
        if self.root.message('Nova demo', 'Criar um banco vazio e reabrir a interface?\nO banco atual será preservado, sem exclusão.', question=True):
            self.resetting = True
            self.stop()

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop()

    def stop(self):
        self.open_button.configure(state='disabled')
        self.new_button.configure(state='disabled')
        self.status.set('Encerrando servidor local…')
        if self.server:
            self.server.should_exit = True
        self.root.after(100, self.stopped)

    def stopped(self):
        if self.thread and self.thread.is_alive():
            self.root.after(100, self.stopped)
            return
        if self.sock:
            self.sock.close()
        (self.folder / 'runtime.json').unlink(missing_ok=True)
        if self.closing:
            self.root.destroy()
            return
        try:
            name = 'demo-' + uuid.uuid4().hex + '.sqlite3'
            temp = self.folder / 'active.tmp'
            temp.write_text(json.dumps({'database': name}), encoding='utf-8')
            temp.replace(self.folder / 'active.json')
            self.resetting = False
            self.start()
        except Exception:
            self.resetting = False
            self.fail()


def main():
    root = Window()
    handle = None
    try:
        folder = Path(os.environ['LOCALAPPDATA']) / 'FoodFlowAI'
        folder.mkdir(parents=True, exist_ok=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateMutexW(None, False, 'Local\\FoodFlowAI-' + hashlib.sha256(str(folder).casefold().encode()).hexdigest()[:24])
        if not handle:
            raise OSError('Mutex unavailable')
        if ctypes.get_last_error() == 183:
            root.control('STATIC', 'O FoodFlow AI já está aberto.\nUse a janela de controle existente.\nNenhum segundo servidor foi iniciado.', 22, 35, 580, 100)
            root.control('BUTTON', 'Fechar aviso', 210, 235, 160, 32, root.destroy)
            root.deiconify()
            root.mainloop()
            return
        Control(root, folder)
        root.deiconify()
        root.mainloop()
    except Exception:
        root.message('FoodFlow AI', 'Não foi possível abrir o aplicativo. Verifique a permissão da pasta local de dados.')
    finally:
        if handle:
            kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()
