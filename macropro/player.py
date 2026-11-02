# -*- coding: utf-8 -*-
"""재생기 — 매크로(동작 목록)를 별도 스레드에서 실행.

옵션(단죄 매크로 호환):
  · loops         반복 횟수 (0=무한)
  · speed         배속
  · jitter        타이밍 랜덤 ±비율 (0~1)
  · cycle         이벤트 실행 주기(초) — 재생 타이머 최소 간격
  · ime_lock      실행 중 한/영을 영문으로 고정 (문구 타이핑 깨짐 방지)
  · release_all   종료 시 눌린 키/버튼 모두 떼기
  · restore_mouse 종료 시 마우스 위치 복구
절대 시각 스케줄이라 오래 돌려도 타이밍이 밀리지 않음.
"""
import random
import threading

from . import ime
from .timing import Scheduler


class Player:
    def __init__(self, engine):
        self.eng = engine
        self._stop = threading.Event()
        self._thread = None
        self.on_status = None      # 콜백(text)
        self.on_done = None        # 콜백(loops_done)

    @property
    def playing(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self._stop.set()

    def play(self, actions, *, loops=1, speed=1.0, jitter=0.0, cycle=0.0,
             ime_lock=False, release_all=True, restore_mouse=False,
             rand_min=0.0, rand_max=0.0):
        if self.playing or not actions:
            return False
        self._stop.clear()
        jitter = min(1.0, max(0.0, jitter))          # 100%↑ 면 딜레이 음수 되던 것 막기
        rand_min = max(0.0, rand_min)
        rand_max = max(rand_min, rand_max)
        self._thread = threading.Thread(
            target=self._run,
            args=(list(actions), loops, max(0.05, speed), jitter, max(0.0, cycle),
                  ime_lock, release_all, restore_mouse, rand_min, rand_max),
            daemon=True)
        self._thread.start()
        return True

    def _status(self, t):
        cb = self.on_status          # 지역으로 한 번만 읽기 (종료 중 null 되는 경쟁 방지)
        if cb:
            cb(t)

    def _run(self, actions, loops, speed, jitter, cycle, ime_lock, release_all, restore_mouse,
             rand_min=0.0, rand_max=0.0):
        start_pos = self.eng.get_pos()
        prev_hangul = None
        if ime_lock:
            prev_hangul = ime.is_hangul()
            ime.set_hangul(False)        # 영문으로 고정
        sched = Scheduler()
        n = 0
        na = len(actions)
        try:
            while not self._stop.is_set():
                sched.start()
                offset = 0.0
                i = 0
                while i < na:
                    if self._stop.is_set():
                        break
                    a = actions[i]
                    dt = a.get("delay", 0.0) / speed
                    if jitter and dt:
                        dt *= random.uniform(1 - jitter, 1 + jitter)
                    if rand_max > 0:
                        dt += random.uniform(rand_min, rand_max)   # 동작마다 랜덤 대기(더 사람같이)
                    if cycle and dt < cycle:
                        dt = cycle              # 실행 주기보다 짧으면 주기로 맞춤
                    offset += dt
                    sched.wait_until(offset)
                    skip = self.eng.run_action(a, self._stop)
                    if isinstance(skip, int) and skip > 0:         # 이미지 조건: 다음 N개 건너뛰기
                        i += skip
                    i += 1
                n += 1
                self._status(f"▶ 실행 {n}회" + ("" if loops == 0 else f"/{loops}"))
                if loops and n >= loops:
                    break
        except Exception as ex:
            self._status(f"오류: {ex}")
        finally:
            if release_all:
                self.eng.release_all()
            if restore_mouse:
                try:
                    self.eng.set_pos(*start_pos)
                except Exception:
                    pass
            if ime_lock and prev_hangul:
                ime.set_hangul(True)         # 원래 한글이었으면 되돌림
            cb = self.on_done                # 지역으로 한 번만 (종료 중 null 경쟁 방지)
            if cb:
                cb(n)
