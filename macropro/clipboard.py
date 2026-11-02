# -*- coding: utf-8 -*-
"""클립보드에 글 넣기 (Windows, ctypes).

긴 문구는 한 글자씩 타이핑하면 느리고 한/영·특수문자에서 깨지기 쉽다.
클립보드에 넣고 Ctrl+V 로 붙여넣으면 빠르고 원문 그대로 들어간다.
윈도우가 아니거나 실패하면 False → 호출한 쪽이 타이핑으로 대신한다.
"""
import sys

_IS_WIN = sys.platform.startswith("win")


def set_clipboard(text):
    """클립보드에 유니코드 글 넣기. 성공하면 True."""
    if not _IS_WIN:
        return False     # 비윈도우: 클립보드 안 씀(재생 스레드에서 Tk 만들면 위험) → 호출부가 타이핑으로 폴백
    try:
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32

        k32.GlobalAlloc.restype = wintypes.HGLOBAL
        k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k32.GlobalLock.restype = wintypes.LPVOID
        k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k32.GlobalFree.restype = wintypes.HGLOBAL
        k32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        u32.SetClipboardData.restype = wintypes.HANDLE
        u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

        data = text.replace("\r\n", "\n").replace("\n", "\r\n")
        buf = data.encode("utf-16-le") + b"\x00\x00"   # 끝 널 문자
        size = len(buf)

        if not u32.OpenClipboard(None):
            return False
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not h:
                return False
            p = k32.GlobalLock(h)
            if not p:
                k32.GlobalFree(h)          # 잠금 실패 → 할당한 핸들 직접 해제
                return False
            ctypes.memmove(p, buf, size)
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(CF_UNICODETEXT, h):
                k32.GlobalFree(h)          # 실패 시 시스템이 소유 안 함 → 우리가 해제(안 하면 누수)
                return False
            return True                    # 성공 시 h 소유권은 시스템에 넘어감 → GlobalFree 하면 안 됨
        finally:
            u32.CloseClipboard()
    except Exception:
        return False


def get_clipboard():
    """클립보드의 글(유니코드). 못 읽으면 ''."""
    if not _IS_WIN:
        return ""        # 비윈도우: 재생 스레드에서 Tk 만들지 않음
    try:
        import ctypes
        from ctypes import wintypes
        CF_UNICODETEXT = 13
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        k32.GlobalLock.restype = wintypes.LPVOID
        k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        u32.GetClipboardData.restype = wintypes.HANDLE
        u32.GetClipboardData.argtypes = [wintypes.UINT]
        if not u32.OpenClipboard(None):
            return ""
        try:
            h = u32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            p = k32.GlobalLock(h)
            if not p:
                return ""
            try:
                return ctypes.c_wchar_p(p).value or ""
            finally:
                k32.GlobalUnlock(h)
        finally:
            u32.CloseClipboard()
    except Exception:
        return ""
