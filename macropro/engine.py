# -*- coding: utf-8 -*-
"""입력 엔진 — 실제 마우스/키보드 조작 + 눌린 키 추적.

pynput Controller 는 Windows 에서 SendInput 을 쓴다. 누른 키/버튼을 추적해서
매크로가 중간에 멈춰도 '모두 떼기'로 안전하게 되돌린다.
"""
import random

from pynput import keyboard, mouse

from . import conditions as C
from . import keys as K
from . import targets as TG
from .timing import hrsleep


class Engine:
    def __init__(self):
        self.mc = mouse.Controller()
        self.kb = keyboard.Controller()
        self._down_keys = set()      # 누른 채인 키 (직렬화 dict 의 튜플화)
        self._down_btns = set()
        self.ctx = None              # 실행 중 변수·목록(값 치환)  — player 가 넣어줌
        self.mset = None             # 저장 대상(창 기준 좌표·broadcast) — player 가 넣어줌

    # ── 위치 ──────────────────────────────────────────────
    def get_pos(self):
        return self.mc.position

    def set_pos(self, x, y):
        self.mc.position = (int(x), int(y))

    # ── 저수준 (녹화 재생용) ──────────────────────────────
    def key_down(self, key):
        self.kb.press(key)
        self._down_keys.add(key)          # 실제 키 객체(repr 아님) — 떼려면 객체가 필요

    def key_up(self, key):
        self.kb.release(key)
        self._down_keys.discard(key)

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
        jitter = abs(int(jitter))          # 음수 들어와도 randint 빈 범위로 안 터지게
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
        loc = self.locate_image(path, confidence)
        if loc is None:
            return False
        self.click(int(loc[0]), int(loc[1]), button)
        return True

    def pixel(self, x, y):
        """화면 (x,y) 의 색 (r,g,b). 못 읽으면 None."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            c = pyautogui.pixel(int(x), int(y))
            return (int(c[0]), int(c[1]), int(c[2]))
        except Exception:
            return None

    def locate_image(self, path, confidence=0.8):
        """화면에서 이미지를 찾아 (x, y) 반환, 없으면 None (예외 안 터뜨림)."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
        except Exception:
            return None
        try:
            return pyautogui.locateCenterOnScreen(path, confidence=confidence)
        except (TypeError, NotImplementedError):   # opencv 없으면 confidence 거부(옛:TypeError, 요즘:NotImplementedError)
            try:
                return pyautogui.locateCenterOnScreen(path)
            except Exception:
                return None
        except Exception:          # 요즘 pyscreeze 는 못 찾으면 ImageNotFoundException 던짐
            return None

    # ── 붙여넣기 (긴 글은 타이핑 대신 복사→Ctrl+V: 빠르고 안 깨짐) ──
    def paste(self, text):
        if not text:
            return
        from .clipboard import set_clipboard
        if set_clipboard(text):
            hrsleep(0.03)
            self.hotkey("ctrl+v")
        else:
            self.type_text(text, 0)      # 클립보드 실패하면 그냥 타이핑

    # ── 창 조절 (제목 일부로 창 찾기) ─────────────────────
    def window_op(self, a):
        try:
            from . import winctl
        except Exception:
            return False
        return winctl.do(a.get("op", "activate"), a.get("title", ""),
                         a.get("x"), a.get("y"), a.get("w"), a.get("h"))

    # ── 동작 1개 실행 ─────────────────────────────────────
    # 반환값: 보통 None. "if_image" 가 조건에 따라 '다음 N개 건너뛰기'를 int 로 돌려줄 수 있음.
    def run_action(self, a, stop=None):
        t = a["type"]
        if t == "move":
            pt = TG.resolve_click_point(self, a, self.mset)
            if pt is None:                       # 창 기준인데 창 못 찾음 → 건너뜀
                return
            if a.get("dur"):
                self.move_smooth(pt[0], pt[1], a["dur"], stop)
            else:
                self.set_pos(pt[0], pt[1])
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
            pt = TG.resolve_click_point(self, a, self.mset)
            if pt is None:                       # 창 기준인데 창 못 찾음 → 건너뜀
                return
            self.click(pt[0], pt[1], a.get("button", "left"), a.get("count", 1), a.get("jitter", 0))
        elif t == "type":
            self.type_text(self._sub(a["text"]), a.get("cps", 0), stop)
        elif t == "increment":                   # 🔢 변수 1 증가(자동 번호)
            if self.ctx is not None:
                self.ctx.increment(a.get("name", ""), a.get("step"))
        elif t == "set":                         # 변수 값 지정
            if self.ctx is not None:
                self.ctx.set_var(a.get("name", ""), self._sub(str(a.get("value", ""))))
        elif t == "hotkey":
            self.hotkey(a["combo"])
        elif t == "image":
            self.image_click(a["path"], a.get("confidence", 0.8), a.get("button", "left"))
        elif t == "paste":                       # 📋 붙여넣기
            self.paste(self._sub(a.get("text", "")))
        elif t == "window":                      # 🪟 창 조절
            self.window_op(a)
        elif t == "wait_image":                  # ⏳ 이미지 뜰 때까지 대기(최대 timeout 초)
            self._wait_image(a, stop)
        elif t == "if_image":                    # 🔀 이미지 조건: 없으면 다음 N개 건너뛰기
            found = self.locate_image(a["path"], a.get("confidence", 0.8)) is not None
            want = a.get("when", "found")        # found=보이면 진행 / notfound=안 보이면 진행
            ok = found if want == "found" else (not found)
            if not ok:
                return int(a.get("skip", 1))     # 조건 불만족 → 다음 N개 건너뛰기
        elif t == "ifcond":                      # 🧠 공통 조건: 안 맞으면 다음 N개 건너뛰기
            ok = C.evaluate(self, a.get("condition", {}), self.ctx)
            want = a.get("when", "true")         # true=맞으면 진행 / false=틀리면 진행
            cond_ok = ok if want == "true" else (not ok)
            if not cond_ok:
                return int(a.get("skip", 1))
        elif t == "broadcast":                   # 📡 여러 방: 각 방 클릭 → 문구 입력 → 엔터
            self._broadcast(a, stop)
        # "wait" 는 delay 로 이미 기다렸으니 할 일 없음

    def _wait_image(self, a, stop=None):
        import time
        path = a["path"]
        conf = a.get("confidence", 0.8)
        timeout = max(0.0, float(a.get("timeout", 10)))
        btn = a.get("button", "")
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            if stop and stop.is_set():
                return
            loc = self.locate_image(path, conf)
            if loc is not None:
                if btn:                          # 뜨면 클릭까지 할지(선택)
                    self.click(int(loc[0]), int(loc[1]), btn)
                return
            hrsleep(0.4)

    def _sub(self, text):
        """값 치환({번호}·{날짜}·변수·목록). ctx 없으면 원문."""
        if self.ctx is not None:
            try:
                return self.ctx.substitute(text)
            except Exception:
                return text
        return text

    def _broadcast(self, a, stop=None):
        items = TG.resolve_broadcast(self.mset, a)   # 저장 대상(target_ids) + 옛 인라인 둘 다
        text = self._sub(a.get("text", ""))
        cps = a.get("cps", 0)
        gap = max(0, a.get("gap_ms", 150)) / 1000.0
        do_enter = a.get("enter", True)
        pre = max(0, a.get("focus_ms", 120)) / 1000.0   # 클릭 후 입력 전 대기(창 포커스)
        for kind, val in items:
            if stop and stop.is_set():
                return
            if kind == "win":                          # 창 제목으로 그 방 띄우기
                self.window_op({"op": "activate", "title": val})
                hrsleep(pre)
            else:
                x, y = val
                self.click(int(x), int(y), "left", 1, 0)   # 그 방 입력칸 클릭
                hrsleep(pre)
            if stop and stop.is_set():      # 정지 누르면 엔터·입력 더 안 나가게
                return
            if text:
                self.type_text(text, cps, stop)
            if stop and stop.is_set():
                return
            if do_enter:
                self.key_down(keyboard.Key.enter)
                hrsleep(0.02)
                self.key_up(keyboard.Key.enter)
            hrsleep(gap)

    # ── 안전: 눌린 키/버튼 모두 떼기 ──────────────────────
    def release_all(self):
        for btn in list(self._down_btns):
            try:
                self.mc.release(btn)
            except Exception:
                pass
        self._down_btns.clear()
        # 추적 중인 눌린 키를 실제로 떼 줌 (게임서 키 누른 채 정지 → 키 안 떼지던 버그)
        for k in list(self._down_keys):
            try:
                self.kb.release(k)
            except Exception:
                pass
        self._down_keys.clear()
        # 흔한 수식키는 혹시 몰라 한 번 더 (추적 누락 대비)
        for k in (keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift, keyboard.Key.cmd):
            try:
                self.kb.release(k)
            except Exception:
                pass
