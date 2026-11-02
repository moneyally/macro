# -*- coding: utf-8 -*-
"""입력 엔진 — 실제 마우스/키보드 조작 + 눌린 키 추적.

pynput Controller 는 Windows 에서 SendInput 을 쓴다. 누른 키/버튼을 추적해서
매크로가 중간에 멈춰도 '모두 떼기'로 안전하게 되돌린다.
"""
import random

from pynput import keyboard, mouse

from . import keys as K
from .timing import hrsleep


class Engine:
    def __init__(self):
        self.mc = mouse.Controller()
        self.kb = keyboard.Controller()
        self._down_keys = set()      # 누른 채인 키 (직렬화 dict 의 튜플화)
        self._down_btns = set()

    # ── 위치 ──────────────────────────────────────────────
    def get_pos(self):
        return self.mc.position

    def set_pos(self, x, y):
        self.mc.position = (int(x), int(y))

    # ── 저수준 (녹화 재생용) ──────────────────────────────
    def key_down(self, key):
        self.kb.press(key)
        self._down_keys.add(repr(key))

    def key_up(self, key):
        self.kb.release(key)
        self._down_keys.discard(repr(key))

    def btn_down(self, btn):
        self.mc.press(btn)
        self._down_btns.add(btn)

    def btn_up(self, btn):
        self.mc.release(btn)
        self._down_btns.discard(btn)

    def scroll_raw(self, dx, dy):
        self.mc.scroll(dx, dy)

    # ── 고수준 (조립 동작용) ──────────────────────────────
    def click(self, x, y, button="left", count=1, jitter=0):
        if jitter:
            x += random.randint(-jitter, jitter)
            y += random.randint(-jitter, jitter)
        self.set_pos(x, y)
        hrsleep(0.012)
        btn = K.button_of(button)
        for _ in range(max(1, count)):
            self.btn_down(btn)
            hrsleep(0.02 + random.uniform(0, 0.03))
            self.btn_up(btn)
            if count > 1:
                hrsleep(0.05)

    def move_smooth(self, x, y, duration=0.0, stop=None):
        if duration <= 0:
            self.set_pos(x, y)
            return
        sx, sy = self.get_pos()
        steps = max(1, int(duration / 0.008))
        for i in range(1, steps + 1):
            if stop and stop.is_set():
                return
            f = i / steps
            f = f * f * (3 - 2 * f)   # ease-in-out
            self.set_pos(sx + (x - sx) * f, sy + (y - sy) * f)
            hrsleep(duration / steps)

    def type_text(self, text, cps=0, stop=None):
        if cps <= 0:
            self.kb.type(text)
            return
        delay = 1.0 / cps
        for ch in text:
            if stop and stop.is_set():
                return
            self.kb.type(ch)
            hrsleep(delay * random.uniform(0.7, 1.3))

    def hotkey(self, spec):
        ks = K.parse_combo(spec)
        if not ks:
            return
        for k in ks[:-1]:
            self.key_down(k)
        self.key_down(ks[-1])
        hrsleep(0.02)
        self.key_up(ks[-1])
        for k in reversed(ks[:-1]):
            self.key_up(k)

    def image_click(self, path, confidence=0.8, button="left"):
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
        except Exception:
            raise RuntimeError("이미지 클릭은  pip install pyautogui opencv-python  필요")
        try:
            loc = pyautogui.locateCenterOnScreen(path, confidence=confidence)
        except TypeError:
            loc = pyautogui.locateCenterOnScreen(path)
        if loc is None:
            return False
        self.click(int(loc[0]), int(loc[1]), button)
        return True

    # ── 동작 1개 실행 ─────────────────────────────────────
    def run_action(self, a, stop=None):
        t = a["type"]
        if t == "move":
            if a.get("dur"):
                self.move_smooth(a["x"], a["y"], a["dur"], stop)
            else:
                self.set_pos(a["x"], a["y"])
        elif t == "mouse":                       # 녹화된 버튼 누름/뗌
            self.set_pos(a["x"], a["y"])
            btn = K.button_of(a["button"])
            (self.btn_down if a["pressed"] else self.btn_up)(btn)
        elif t == "scroll":
            self.scroll_raw(a.get("dx", 0), a.get("dy", 0))
        elif t == "key":                         # 녹화된 키 누름/뗌
            key = K.deser_key(a["key"])
            (self.key_down if a["action"] == "press" else self.key_up)(key)
        elif t == "click":
            self.click(a["x"], a["y"], a.get("button", "left"), a.get("count", 1), a.get("jitter", 0))
        elif t == "type":
            self.type_text(a["text"], a.get("cps", 0), stop)
        elif t == "hotkey":
            self.hotkey(a["combo"])
        elif t == "image":
            self.image_click(a["path"], a.get("confidence", 0.8), a.get("button", "left"))
        # "wait" 는 delay 로 이미 기다렸으니 할 일 없음

    # ── 안전: 눌린 키/버튼 모두 떼기 ──────────────────────
    def release_all(self):
        for btn in list(self._down_btns):
            try:
                self.mc.release(btn)
            except Exception:
                pass
        self._down_btns.clear()
        # 흔한 수식키는 명시적으로도 떼 줌 (추적 누락 대비)
        for k in (keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift, keyboard.Key.cmd):
            try:
                self.kb.release(k)
            except Exception:
                pass
        self._down_keys.clear()
