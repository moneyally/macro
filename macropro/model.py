# -*- coding: utf-8 -*-
"""데이터 모델 — 여러 매크로 + 전역 설정, .m 파일 저장/불러오기.

.m 파일 = JSON. 단죄식 다중 매크로(목록·개별 단축키·반복)를 담는다.
"""
import json


class Macro:
    def __init__(self, name="Macro", actions=None, hotkey="", loops=1, speed=1.0,
                 chain="", schedule=""):
        self.name = name
        self.actions = actions or []     # [{type, delay, ...}]
        self.hotkey = hotkey             # 이 매크로 실행 단축키 (예: 'f1')
        self.loops = loops               # 0 = 무한
        self.speed = speed
        self.chain = chain               # 끝나면 이어서 실행할 매크로 이름 (체인)
        self.schedule = schedule         # 매일 자동 실행 시각 'HH:MM' (빈값=안 함)

    def to_dict(self):
        return {"name": self.name, "actions": self.actions,
                "hotkey": self.hotkey, "loops": self.loops, "speed": self.speed,
                "chain": self.chain, "schedule": self.schedule}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("name", "Macro"), d.get("actions", []),
                   d.get("hotkey", ""), int(d.get("loops", 1)), float(d.get("speed", 1.0)),
                   d.get("chain", ""), d.get("schedule", ""))

    def copy(self):
        m = Macro.from_dict(self.to_dict())
        m.name = self.name + " 복사"
        m.hotkey = ""       # 단축키 중복 방지
        m.schedule = ""     # 예약 중복 방지
        return m


class MacroSet:
    """매크로 묶음 + 전역 옵션(단죄 매크로 호환)."""
    def __init__(self):
        self.macros = []
        self.cycle_ms = 33          # 이벤트 실행 주기
        self.ime_detect = True      # 한/영 감지(영문 고정)
        self.release_on_stop = True # 종료 시 눌린 키/버튼 떼기
        self.restore_mouse = False  # 종료 시 마우스 위치 복구
        self.jitter_pct = 0         # 타이밍 랜덤 ±%
        self.record_moves = True
        self.rand_min_ms = 0        # 동작마다 추가 랜덤 대기 최소(ms) — 더 사람같이
        self.rand_max_ms = 0        # 동작마다 추가 랜덤 대기 최대(ms)

    def add(self, macro=None):
        macro = macro or Macro(name=self._next_name())
        self.macros.append(macro)
        return macro

    def _next_name(self):
        i = 1
        names = {m.name for m in self.macros}
        while f"Macro {i}" in names:
            i += 1
        return f"Macro {i}"

    def to_dict(self):
        return {
            "version": 1,
            "cycle_ms": self.cycle_ms, "ime_detect": self.ime_detect,
            "release_on_stop": self.release_on_stop, "restore_mouse": self.restore_mouse,
            "jitter_pct": self.jitter_pct, "record_moves": self.record_moves,
            "rand_min_ms": self.rand_min_ms, "rand_max_ms": self.rand_max_ms,
            "macros": [m.to_dict() for m in self.macros],
        }

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.cycle_ms = int(d.get("cycle_ms", 33))
        s.ime_detect = bool(d.get("ime_detect", True))
        s.release_on_stop = bool(d.get("release_on_stop", True))
        s.restore_mouse = bool(d.get("restore_mouse", False))
        s.jitter_pct = int(d.get("jitter_pct", 0))
        s.record_moves = bool(d.get("record_moves", True))
        s.rand_min_ms = int(d.get("rand_min_ms", 0))
        s.rand_max_ms = int(d.get("rand_max_ms", 0))
        s.macros = [Macro.from_dict(x) for x in d.get("macros", [])]
        return s

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# 동작 1개를 사람이 읽는 한 줄로
def action_label(a):
    t = a["type"]
    d = a.get("delay", 0)
    gap = f"  ·{int(d * 1000)}ms" if d >= 0.001 else ""
    if t == "move":
        return f"➡  이동 ({a['x']},{a['y']}){gap}"
    if t == "mouse":
        onoff = "누름" if a["pressed"] else "뗌"
        return f"🖱  {a['button']} {onoff} ({a['x']},{a['y']}){gap}"
    if t == "scroll":
        return f"🖲  스크롤 dx{a.get('dx',0)} dy{a.get('dy',0)}{gap}"
    if t == "key":
        k = a["key"].get("v")
        onoff = "누름" if a["action"] == "press" else "뗌"
        return f"⌨  키 '{k}' {onoff}{gap}"
    if t == "click":
        j = f" ±{a['jitter']}px" if a.get("jitter") else ""
        return f"🖱  클릭 ({a['x']},{a['y']}) {a.get('button','left')} ×{a.get('count',1)}{j}{gap}"
    if t == "type":
        return f"✎  문구 \"{a['text'][:22]}\" ({'즉시' if not a.get('cps') else str(a['cps'])+'자/초'}){gap}"
    if t == "paste":
        return f"📋  붙여넣기 \"{a.get('text','')[:22]}\"{gap}"
    if t == "hotkey":
        return f"🔑  단축키 {a['combo']}{gap}"
    if t == "window":
        op = a.get("op", "activate")
        xy = ""
        if op == "move":
            xy = f" → ({a.get('x')},{a.get('y')})"
        elif op == "resize":
            xy = f" → {a.get('w')}×{a.get('h')}"
        return f"🪟  창 \"{a.get('title','')[:16]}\" {op}{xy}{gap}"
    if t == "wait_image":
        return f"⏳  이미지 뜰 때까지 {a['path']} (≤{int(a.get('timeout',10))}초){gap}"
    if t == "if_image":
        cond = "있으면 진행" if a.get("when", "found") == "found" else "없으면 진행"
        return f"🔀  이미지 {cond}, 아니면 {a.get('skip',1)}개 건너뛰기  {a['path']}"
    if t == "wait":
        return f"⏱  대기 {int(a.get('delay',0)*1000)}ms"
    if t == "image":
        return f"🖼  이미지 클릭 {a['path']}{gap}"
    if t == "broadcast":
        n = len(a.get("targets", []))
        en = " +엔터" if a.get("enter", True) else ""
        return f"📡  여러 방 {n}곳 전송  \"{a.get('text','')[:18]}\"{en}"
    return str(a)
