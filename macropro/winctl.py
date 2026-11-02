# -*- coding: utf-8 -*-
"""창 조절 — 제목 일부로 창을 찾아 띄우기/이동/크기/최소·최대화/닫기 (Windows).

pygetwindow 을 쓰고, 없으면 ctypes(user32)로 직접 처리한다.
제목은 '일부만' 맞아도 됨(부분 일치, 대소문자 무시) — 텔레그램 방 이름 같은 거.
안전: 못 찾거나 실패하면 조용히 False (매크로는 계속).
"""
import sys

_IS_WIN = sys.platform.startswith("win")


def _find_pgw(title):
    import pygetwindow as gw
    t = (title or "").lower()
    for w in gw.getAllWindows():
        if w.title and t in w.title.lower():
            return w
    return None


def _do_pgw(op, title, x, y, w, h):
    import importlib.util
    if importlib.util.find_spec("pygetwindow") is None:
        return None          # pygetwindow 없음 → ctypes 폴백으로
    try:
        win = _find_pgw(title)
        if win is None:
            return False
        if op in ("activate", "show", "front"):
            try:
                win.activate()
            except Exception:
                win.minimize(); win.restore()   # activate 가 가끔 실패 → 흔드는 우회
        elif op in ("min", "minimize"):
            win.minimize()
        elif op in ("max", "maximize"):
            win.maximize()
        elif op in ("restore", "normal"):
            win.restore()
        elif op == "close":
            win.close()
        elif op == "move" and x is not None and y is not None:
            win.moveTo(int(x), int(y))
        elif op == "resize" and w is not None and h is not None:
            win.resizeTo(int(w), int(h))
        else:
            return False
        return True
    except Exception:
        return False


def _do_ctypes(op, title, x, y, w, h):
    """pygetwindow 가 없을 때 user32 로 최소 기능."""
    if not _IS_WIN:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        u32 = ctypes.windll.user32
        # HWND 를 32비트 int 로 자르지 않게 argtypes 명시 (견고성)
        u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u32.SetForegroundWindow.argtypes = [wintypes.HWND]
        u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
        u32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u32.IsWindowVisible.argtypes = [wintypes.HWND]
        found = []
        t = (title or "").lower()

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _cb(hwnd, _l):
            if not u32.IsWindowVisible(hwnd):
                return True
            n = u32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value and t in buf.value.lower():
                found.append(hwnd)
                return False
            return True

        u32.EnumWindows(EnumWindowsProc(_cb), 0)
        if not found:
            return False
        hwnd = found[0]
        SW = {"activate": 9, "show": 9, "front": 9, "min": 6, "minimize": 6,
              "max": 3, "maximize": 3, "restore": 9, "normal": 1}
        if op in SW:
            u32.ShowWindow(hwnd, SW[op])
            u32.SetForegroundWindow(hwnd)
            return True
        if op == "close":
            u32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
            return True
        if op == "move" and x is not None and y is not None:
            u32.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0, 0x0001 | 0x0004)  # SWP_NOSIZE|NOZORDER
            return True
        if op == "resize" and w is not None and h is not None:
            u32.SetWindowPos(hwnd, 0, 0, 0, int(w), int(h), 0x0002 | 0x0004)  # SWP_NOMOVE|NOZORDER
            return True
        return False
    except Exception:
        return False


def do(op, title, x=None, y=None, w=None, h=None):
    r = _do_pgw(op, title, x, y, w, h)
    if r is None:              # pygetwindow 미설치 → ctypes
        return _do_ctypes(op, title, x, y, w, h)
    return r


def list_titles(limit=60):
    """지금 열린 창 제목들 (UI 에서 고르게)."""
    out = []
    try:
        import pygetwindow as gw
        for wd in gw.getAllWindows():
            if wd.title and wd.title.strip():
                out.append(wd.title.strip())
    except Exception:
        if _IS_WIN:
            try:
                import ctypes
                from ctypes import wintypes
                u32 = ctypes.windll.user32
                EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

                def _cb(hwnd, _l):
                    if u32.IsWindowVisible(hwnd):
                        n = u32.GetWindowTextLengthW(hwnd)
                        if n > 0:
                            buf = ctypes.create_unicode_buffer(n + 1)
                            u32.GetWindowTextW(hwnd, buf, n + 1)
                            if buf.value and buf.value.strip():
                                out.append(buf.value.strip())
                    return True

                u32.EnumWindows(EnumWindowsProc(_cb), 0)
            except Exception:
                pass
    # 중복 제거(순서 유지)
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:limit]
