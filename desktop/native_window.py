"""Small Win32 control window; uses only Windows DLLs and Python ctypes."""
import ctypes as c
from ctypes import wintypes as w
import time

user = c.WinDLL('user32', use_last_error=True)
kernel = c.WinDLL('kernel32', use_last_error=True)
PROC = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class CLASS(c.Structure):
    _fields_ = [('style', w.UINT), ('proc', PROC), ('extra', c.c_int), ('windowextra', c.c_int),
                ('instance', w.HINSTANCE), ('icon', w.HICON), ('cursor', w.HANDLE),
                ('background', w.HBRUSH), ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]


user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user.DefWindowProcW.restype = c.c_ssize_t
user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int, c.c_int,
                                c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
user.CreateWindowExW.restype = w.HWND
user.SetWindowTextW.argtypes = [w.HWND, w.LPCWSTR]
user.ShowWindow.argtypes = [w.HWND, c.c_int]
user.DestroyWindow.argtypes = [w.HWND]
user.EnableWindow.argtypes = [w.HWND, w.BOOL]
user.SetTimer.argtypes = [w.HWND, c.c_size_t, w.UINT, c.c_void_p]
user.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user.MessageBoxW.argtypes = [w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT]
kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
kernel.GetModuleHandleW.restype = w.HINSTANCE


class Widget:
    def __init__(self, handle):
        self.handle = handle

    def set(self, text):
        user.SetWindowTextW(self.handle, text)

    def configure(self, state):
        user.EnableWindow(self.handle, state != 'disabled')


class Window:
    def __init__(self):
        self.callbacks, self.jobs = {}, []
        self.on_close = lambda: self.destroy()
        self.proc = PROC(self.dispatch)
        instance = kernel.GetModuleHandleW(None)
        self.cls = CLASS(0, self.proc, 0, 0, instance, None, None, 16, None, 'FoodFlowControl')
        if not user.RegisterClassW(c.byref(self.cls)):
            raise OSError('Window registration failed')
        self.handle = user.CreateWindowExW(0, self.cls.name, 'FoodFlow AI — controle local',
            0x00CA0000, 180, 150, 630, 355, None, None, instance, None)
        if not self.handle:
            raise OSError('Window creation failed')
        user.SetTimer(self.handle, 1, 50, None)

    def dispatch(self, hwnd, msg, wp, lp):
        if msg == 0x111:
            callback = self.callbacks.get(wp & 0xffff)
            if callback:
                callback()
            return 0
        if msg == 0x10:
            self.on_close()
            return 0
        if msg == 2:
            user.PostQuitMessage(0)
            return 0
        if msg == 0x113:
            due = [job for job in self.jobs if job[0] <= time.monotonic()]
            self.jobs = [job for job in self.jobs if job not in due]
            for _, callback in due:
                callback()
            return 0
        return user.DefWindowProcW(hwnd, msg, wp, lp)

    def control(self, kind, text, x, y, width, height, callback=None):
        ident = len(self.callbacks) + 100 if callback else 0
        handle = user.CreateWindowExW(0, kind, text, 0x50000000 | (0x10000 if callback else 0),
            x, y, width, height, self.handle, ident, None, None)
        gdi = c.WinDLL('gdi32')
        gdi.GetStockObject.restype = w.HANDLE
        user.SendMessageW(handle, 0x30, gdi.GetStockObject(17), 1)
        if callback:
            self.callbacks[ident] = callback
        return Widget(handle)

    def after(self, milliseconds, callback):
        self.jobs.append((time.monotonic() + milliseconds / 1000, callback))

    def destroy(self):
        user.DestroyWindow(self.handle)

    def deiconify(self):
        user.ShowWindow(self.handle, 5)

    def mainloop(self):
        msg = w.MSG()
        while user.GetMessageW(c.byref(msg), None, 0, 0) > 0:
            user.TranslateMessage(c.byref(msg))
            user.DispatchMessageW(c.byref(msg))

    def message(self, title, text, question=False):
        return user.MessageBoxW(self.handle, text, title, 0x24 if question else 0x40) == 6
