# -*- coding: utf-8 -*-
"""녹화기 — 키보드·마우스 입력을 동작 목록으로 기록.

각 동작은 { "type":..., "delay": 앞 동작과의 간격(초), ... } 형태.
delay 로 저장해 두면 재생 때 배속·랜덤을 걸기 쉽다.
move 는 cycle 간격으로 솎아 파일을 가볍게.
"""
from pynput import keyboard, mouse

from . import keys as K
from .timing import now

STOP_KEYS = set()   # 녹화에 기록하지 않을 제어키 (앱이 채워 줌: F8/F9/F10/F12 등)
MAX_ACTIONS = 200000   # 아주 오래 녹화해도 메모리 안 터지게 상한


class Recorder:
    def __init__(self, record_moves=True, move_interval=0.015):
        self.record_moves = record_moves
        self.move_interval = move_interval
        self.actions = []
        self._m = None
        self._k = None
        self._t0 = 0.0
        self._last = 0.0
        self._last_move = 0.0
        self.running = False

    def start(self):
        self.actions = []
        self._t0 = now()
        self._last = self._t0
        self._last_move = 0.0
        self.running = True
        self._m = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
        self._k = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._m.start()
        self._k.start()

    def stop(self):
        self.running = False
        for lst in (self._m, self._k):
            if lst:
                lst.stop()
        self._m = self._k = None
        return self.actions

    def _add(self, d):
        if len(self.actions) >= MAX_ACTIONS:
            self.running = False        # 상한 도달 → 더 안 쌓음 (앱이 다음 틱에 정지 처리)
            return
        t = now()
        d["delay"] = max(0.0, t - self._last)
        self._last = t
        self.actions.append(d)

    def _on_move(self, x, y):
        if not self.record_moves or not self.running:
            return
        t = now()
        if t - self._last_move < self.move_interval:
            return
        self._last_move = t
        self._add({"type": "move", "x": int(x), "y": int(y)})

    def _on_click(self, x, y, button, pressed):
        self._add({"type": "mouse", "x": int(x), "y": int(y), "button": button.name, "pressed": pressed})

    def _on_scroll(self, x, y, dx, dy):
        self._add({"type": "scroll", "dx": int(dx), "dy": int(dy)})

    def _on_press(self, key):
        if key in STOP_KEYS:
            return
        self._add({"type": "key", "action": "press", "key": K.ser_key(key)})

    def _on_release(self, key):
        if key in STOP_KEYS:
            return
        self._add({"type": "key", "action": "release", "key": K.ser_key(key)})
