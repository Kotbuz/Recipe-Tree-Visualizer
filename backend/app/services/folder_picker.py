from __future__ import annotations

import contextlib
import sys


def pick_folder_dialog(*, title: str = "Выберите папку инстанса") -> str | None:
    """Нативный диалог выбора папки (локальный backend с GUI)."""
    if sys.platform == "win32":
        return _pick_folder_windows(title=title)
    return _pick_folder_tkinter(title=title)


def _pick_folder_tkinter(*, title: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    with contextlib.suppress(tk.TclError):
        root.attributes("-topmost", True)
    selected = filedialog.askdirectory(title=title, mustexist=True)
    root.destroy()
    if not selected:
        return None
    return str(selected)


def _pick_folder_windows(*, title: str) -> str | None:
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return _pick_folder_tkinter(title=title)

    BIF_RETURNONLYFSDIRS = 0x0001
    BIF_NEWDIALOGSTYLE = 0x0040

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", wintypes.LPWSTR),
            ("lpszTitle", wintypes.LPCWSTR),
            ("ulFlags", wintypes.UINT),
            ("lpfn", ctypes.c_void_p),
            ("lParam", ctypes.c_longlong),
            ("iImage", ctypes.c_int),
        ]

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32

    buffer = ctypes.create_unicode_buffer(260)
    info = BROWSEINFO()
    info.hwndOwner = None
    info.pidlRoot = None
    info.pszDisplayName = ctypes.cast(buffer, wintypes.LPWSTR)
    info.lpszTitle = title
    info.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE

    pidl = shell32.SHBrowseForFolderW(ctypes.byref(info))
    if not pidl:
        return _pick_folder_tkinter(title=title)

    path_buffer = ctypes.create_unicode_buffer(260)
    if not shell32.SHGetPathFromIDListW(pidl, path_buffer):
        ole32.CoTaskMemFree(pidl)
        return _pick_folder_tkinter(title=title)

    ole32.CoTaskMemFree(pidl)
    selected = path_buffer.value.strip()
    return selected or None
