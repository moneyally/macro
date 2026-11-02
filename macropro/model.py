# -*- coding: utf-8 -*-
"""데이터 모델 — 여러 매크로 + 전역 설정, .m 파일 저장/불러오기.

.m 파일 = JSON. 단죄식 다중 매크로(목록·개별 단축키·반복)를 담는다.
"""
import json


def _safe_int(v, default):
    try:
        return int(float(v))
    except Exception:
        return default


def _safe_float(v, default):
    try:
        return float(v)
    except Exception:
        return default


class Macro:
    def __init__(self, name="Macro", actions=None, hotkey="", loops=1, speed=1.0,
                 chain="", schedule=""):
        self.name = name
        self.actions = actions or []     # [{type, delay, ...}]
        self.hotkey = hotkey             # 이 매크로 실행 단축키 (예: 'f1')
        self.loops = loops               # 0 = 무한
        self.speed = speed
        self.chain = chain               # 끝나면 이어서 실행할 매크로 이름 (체인)
        self.schedule = schedule         # 자동 실행 시각 'HH:MM' (빈값=안 함)
        self.sched_days = []             # 요일 제한 [0=월..6=일]. 빈 리스트=매일
        self.sched_start = ""            # 예약 시작 날짜 'YYYY-MM-DD' (빈값=제한없음)
        self.sched_end = ""              # 예약 종료 날짜
        self.list_source = {}            # 📄 CSV/TXT 목록: {path, header, on_end}
        self.err = "stop"                # 동작 오류 기본 처리 stop|skip

    def to_dict(self):
        return {"name": self.name, "actions": self.actions,
                "hotkey": self.hotkey, "loops": self.loops, "speed": self.speed,
                "chain": self.chain, "schedule": self.schedule,
                "sched_days": self.sched_days, "sched_start": self.sched_start,
                "sched_end": self.sched_end, "list_source": self.list_source, "err": self.err}

    @classmethod
    def from_dict(cls, d):
        m = cls(d.get("name", "Macro"), d.get("actions", []) or [],
                d.get("hotkey", ""), _safe_int(d.get("loops", 1), 1), _safe_float(d.get("speed", 1.0), 1.0),
                d.get("chain", ""), d.get("schedule", ""))
        m.sched_days = list(d.get("sched_days", []) or [])
        m.sched_start = d.get("sched_start", "")
        m.sched_end = d.get("sched_end", "")
        m.list_source = dict(d.get("list_source", {}) or {})
        m.err = d.get("err", "stop")
        return m

    def copy(self):
        m = Macro.from_dict(self.to_dict())
        m.name = self.name + " 복사"
        m.hotkey = ""       # 단축키 중복 방지
        m.schedule = ""     # 예약 중복 방지
        m.sched_days = []   # 요일·기간 제한도 초기화 (안 그러면 복사본에 숨은 제한)
        m.sched_start = ""
        m.sched_end = ""
        m.chain = ""        # 체인도 초기화
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
        self.variables = []         # 🔢 사용자 변수 [{name,start,step,reset}]
        self.targets = []           # 📚 저장 대상 [{id,name,kind,x,y,title}]
        self.theme = "warm"         # 화면 테마 (warm 하나뿐, 확장 여지)
        self.advanced = False       # 🧰 고급 모드 (끄면 기본 기능만 보임)

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
            "variables": self.variables, "targets": self.targets, "theme": self.theme,
            "advanced": self.advanced,
            "macros": [m.to_dict() for m in self.macros],
        }

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.cycle_ms = _safe_int(d.get("cycle_ms", 33), 33)
        s.ime_detect = bool(d.get("ime_detect", True))
        s.release_on_stop = bool(d.get("release_on_stop", True))
        s.restore_mouse = bool(d.get("restore_mouse", False))
        s.jitter_pct = _safe_int(d.get("jitter_pct", 0), 0)
        s.record_moves = bool(d.get("record_moves", True))
        s.rand_min_ms = _safe_int(d.get("rand_min_ms", 0), 0)
        s.rand_max_ms = _safe_int(d.get("rand_max_ms", 0), 0)
        s.variables = list(d.get("variables", []) or [])
        s.targets = list(d.get("targets", []) or [])
        s.theme = d.get("theme", "warm")
        s.advanced = bool(d.get("advanced", False))
        s.macros = []
        for x in (d.get("macros", []) or []):
            try:
                s.macros.append(Macro.from_dict(x))
            except Exception:
                pass            # 매크로 하나가 깨져도 나머지는 살림
        return s

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# 동작 1개를 사람이 읽는 한 줄로 (어떤 입력에도 안 터지게 방어)
def action_label(a):
    try:
        return _action_label(a)
    except Exception:
        return str(a.get("type", a)) if isinstance(a, dict) else str(a)


def _action_label(a):
    t = a.get("type", "")
    d = a.get("delay", 0)
    gap = f"  ·{int(d * 1000)}ms" if d >= 0.001 else ""
    if t == "move":
        return f"➡  이동 ({a.get('x',0)},{a.get('y',0)}){gap}"
    if t == "mouse":
        onoff = "누름" if a.get("pressed") else "뗌"
        return f"🖱  {a.get('button','left')} {onoff} ({a.get('x',0)},{a.get('y',0)}){gap}"
    if t == "scroll":
        return f"🖲  스크롤 dx{a.get('dx',0)} dy{a.get('dy',0)}{gap}"
    if t == "key":
        k = (a.get("key") or {}).get("v")
        onoff = "누름" if a.get("action") == "press" else "뗌"
        return f"⌨  키 '{k}' {onoff}{gap}"
    if t == "click":
        if a.get("coordinate_mode") == "window_relative":   # 🪟 창 기준 클릭
            return f"🪟  창 '{str(a.get('window',''))[:14]}' 기준 ({int(a.get('x',0)*100)}%,{int(a.get('y',0)*100)}%){gap}"
        j = f" ±{a['jitter']}px" if a.get("jitter") else ""
        return f"🖱  클릭 ({a.get('x',0)},{a.get('y',0)}) {a.get('button','left')} ×{a.get('count',1)}{j}{gap}"
    if t == "type":
        return f"✎  문구 \"{a.get('text','')[:22]}\" ({'즉시' if not a.get('cps') else str(a['cps'])+'자/초'}){gap}"
    if t == "paste":
        return f"📋  붙여넣기 \"{a.get('text','')[:22]}\"{gap}"
    if t == "hotkey":
        return f"🔑  단축키 {a.get('combo','')}{gap}"
    if t == "window":
        op = a.get("op", "activate")
        xy = ""
        if op == "move":
            xy = f" → ({a.get('x')},{a.get('y')})"
        elif op == "resize":
            xy = f" → {a.get('w')}×{a.get('h')}"
        return f"🪟  창 \"{a.get('title','')[:16]}\" {op}{xy}{gap}"
    if t == "wait_image":
        return f"⏳  이미지 뜰 때까지 {a.get('path','')} (≤{int(a.get('timeout',10))}초){gap}"
    if t == "if_image":
        cond = "있으면 진행" if a.get("when", "found") == "found" else "없으면 진행"
        return f"🔀  이미지 {cond}, 아니면 {a.get('skip',1)}개 건너뛰기  {a['path']}"
    if t == "wait":
        return f"⏱  대기 {int(a.get('delay',0)*1000)}ms"
    if t == "image":
        return f"🖼  이미지 클릭 {a['path']}{gap}"
    if t == "broadcast":
        n = len(a.get("targets", [])) + len(a.get("target_ids", []))
        en = " +엔터" if a.get("enter", True) else ""
        return f"📡  여러 방 {n}곳 전송  \"{a.get('text','')[:18]}\"{en}"
    if t == "increment":
        st = a.get("step", 1)
        return f"🔢  변수 '{a.get('name','')}' +{st}"
    if t == "set":
        return f"🔧  변수 '{a.get('name','')}' = \"{str(a.get('value',''))[:16]}\""
    if t == "if":
        c = a.get("condition", {})
        src = {"image": "이미지", "window": "창", "active_title": "활성창",
               "pixel": "픽셀색", "clipboard": "클립보드"}.get(c.get("source", "image"), c.get("source", ""))
        nt, ne = len(a.get("then", [])), len(a.get("else", []))
        return f"🧠  만약 [{src} {c.get('operator','')} {str(c.get('value',''))[:12]}] → 참 {nt}개 / 거짓 {ne}개"
    if t == "ifcond":
        c = a.get("condition", {})
        src = {"image": "이미지", "window": "창", "active_title": "활성창",
               "pixel": "픽셀색", "clipboard": "클립보드"}.get(c.get("source", "image"), c.get("source", ""))
        w = "맞으면" if a.get("when", "true") == "true" else "틀리면"
        return f"🧠  조건 [{src} {c.get('operator','')} {str(c.get('value',''))[:12]}] {w} 진행, 아니면 {a.get('skip',1)}개 건너뜀"
    return str(a)
