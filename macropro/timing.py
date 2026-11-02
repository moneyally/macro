# -*- coding: utf-8 -*-
"""밀리초 정밀 타이밍.

Windows 기본 sleep 은 ~15ms 해상도라 매크로엔 너무 거침.
- time.perf_counter() = QueryPerformanceCounter (마이크로초급, 단조증가)
- timeBeginPeriod(1) 로 시스템 타이머 해상도 1ms 로 올림
- hrsleep: 대부분 OS sleep + 마지막 ~1.2ms 만 busy-wait → 정밀하면서 CPU 거의 0
근거: MS docs QueryPerformanceCounter, win-precise-time, PEP 418.
"""
import sys
import time

_winmm = None
_IS_WIN = sys.platform.startswith("win")


def enable_high_res_timer():
    """시스템 타이머 해상도 1ms (프로그램 시작 때 1번). 끝나면 disable 로 되돌릴 것."""
    global _winmm
    if not _IS_WIN:
        return
    try:
        import ctypes
        _winmm = ctypes.WinDLL("winmm")
        _winmm.timeBeginPeriod(1)
    except Exception:
        _winmm = None


def disable_high_res_timer():
    global _winmm
    if _winmm:
        try:
            _winmm.timeEndPeriod(1)
        except Exception:
            pass
        _winmm = None


def now():
    return time.perf_counter()


def hrsleep(duration):
    """고정밀 sleep(초). 음수/0 은 즉시 반환."""
    if duration <= 0:
        return
    end = time.perf_counter() + duration
    remain = duration - 0.0012          # 마지막 1.2ms 는 busy-wait
    if remain > 0:
        time.sleep(remain)
    while time.perf_counter() < end:
        pass


class Scheduler:
    """절대 시각 스케줄러 — 누적 오차(drift) 없이 재생.

    start() 로 기준시각을 잡고, wait(target_offset) 로 '시작 + offset' 까지 정확히 기다린다.
    매 이벤트마다 sleep(간격) 을 쓰면 오차가 쌓이지만, 절대 시각으로 맞추면 안 쌓인다.
    """
    def __init__(self):
        self._base = 0.0

    def start(self):
        self._base = time.perf_counter()

    def wait_until(self, offset):
        hrsleep(self._base + offset - time.perf_counter())
