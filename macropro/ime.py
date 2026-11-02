# -*- coding: utf-8 -*-
"""한/영 IME 상태 감지·전환 (Windows 전용, 실패해도 무해).

포커스 창의 IME 컨텍스트에서 변환 상태를 읽어 한글 모드인지 본다.
  ImmGetContext(hwnd) → ImmGetConversionStatus → conv & 0x1 (native=한글)
  보조로 키보드 레이아웃 0x0412 = 한국어.
근거: MS docs ImmGetConversionStatus, GetGUIThreadInfo.
윈도우 아니거나 호출 실패하면 None 반환 → 호출하는 쪽이 그냥 건너뜀.
"""
import sys

_IS_WIN = sys.platform.startswith("win")
IME_CMODE_NATIVE = 0x0001   # 한글 입력 모드 비트

if _IS_WIN:
    try:
        import ctypes
        from ctypes import wintypes
        _user32 = ctypes.WinDLL("user32", use_last_error=True)
        _imm32 = ctypes.WinDLL("imm32", use_last_error=True)

        class _GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                        ("rcCaret", wintypes.RECT)]
        _OK = True
    except Exception:
        _OK = False
else:
    _OK = False


def _focused_hwnd():
    gti = _GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(_GUITHREADINFO)
    if _user32.GetGUIThreadInfo(0, ctypes.byref(gti)) and gti.hwndFocus:
        return gti.hwndFocus
    return _user32.GetForegroundWindow()


def is_hangul():
    """한글 입력 모드면 True, 영문이면 False, 알 수 없으면 None."""
    if not _OK:
        return None
    try:
        hwnd = _focused_hwnd()
        himc = _imm32.ImmGetContext(hwnd)
        if not himc:
            return None
        conv = wintypes.DWORD()
        sent = wintypes.DWORD()
        ok = _imm32.ImmGetConversionStatus(himc, ctypes.byref(conv), ctypes.byref(sent))
        _imm32.ImmReleaseContext(hwnd, himc)
        if not ok:
            return None
        return bool(conv.value & IME_CMODE_NATIVE)
    except Exception:
        return None


def korean_layout():
    """지금 활성 키보드 레이아웃이 한국어(0x0412)면 True. 보조 신호."""
    if not _OK:
        return None
    try:
        tid = _user32.GetWindowThreadProcessId(_user32.GetForegroundWindow(), None)
        hkl = _user32.GetKeyboardLayout(tid)
        return (hkl & 0xFFFF) == 0x0412
    except Exception:
        return None


def set_hangul(on):
    """한글 모드를 on 으로 맞춤(best-effort). 바꿨으면 True.
    ImmSetConversionStatus 로 포커스 창 IME 상태를 직접 지정."""
    if not _OK:
        return False
    cur = is_hangul()
    if cur is None or cur == bool(on):
        return False
    try:
        hwnd = _focused_hwnd()
        himc = _imm32.ImmGetContext(hwnd)
        if not himc:
            return False
        conv = wintypes.DWORD()
        sent = wintypes.DWORD()
        _imm32.ImmGetConversionStatus(himc, ctypes.byref(conv), ctypes.byref(sent))
        if on:
            conv.value |= IME_CMODE_NATIVE
        else:
            conv.value &= ~IME_CMODE_NATIVE
        _imm32.ImmSetConversionStatus(himc, conv, sent)
        _imm32.ImmReleaseContext(hwnd, himc)
        return True
    except Exception:
        return False
