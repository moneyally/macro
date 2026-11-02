# -*- coding: utf-8 -*-
"""Value Resolver — 변수·자동번호·날짜/시간·CSV/TXT 목록을 '값'으로 풀어 준다.

설계 철학: 임의 코드 실행 없음. 안전한 '문자열 치환 + 숫자 증가'만.
문구 안 {이름} 을 값으로 바꿔 끼운다.
  - 기본 제공: {번호}/{순번}(1부터), {반복}(0부터), {날짜}, {시간}, {날짜시간}, {요일}
  - 사용자 변수: MacroSet.variables 에 {name,start,step,reset} 로 정의
  - 목록 열: Macro.list_source 로 CSV/TXT 를 줄마다 — {열이름} 또는 {값}(TXT 한 줄)
한 번의 매크로 '실행' 동안 상태를 들고 다니는 RunContext 로 관리.
"""
import csv
import os
import re
import time

_TOKEN = re.compile(r"\{([^{}]{1,40})\}")   # {이름} 토큰


def _num(v):
    try:
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return v
        s = str(v).strip().replace(",", "")
        if s == "":
            return None
        f = float(s)
        return int(f) if f.is_integer() else f
    except Exception:
        return None


def to_num(s, default=0):
    """문자열/값 → 숫자. 안 되면 default. (UI 입력 처리용)"""
    v = _num(s)
    return default if v is None else v


def _fmt(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


class RunContext:
    """한 번의 매크로 실행 동안의 변수·반복·목록 상태."""

    def __init__(self, mset=None, macro=None):
        self.rep = 0                      # 0부터: 현재 반복 회차
        self.vars = {}                    # 사용자 변수: 이름 -> 값
        self._defs = {}                   # 이름 -> 정의(step/reset) (증가·초기화용)
        self.row = {}                     # 현재 목록 행: 열이름 -> 값
        self.list_done = False            # 목록 끝까지 다 씀
        self._rows = None                 # 전체 목록 행들(없으면 None)
        self._li = 0
        self._list_on_end = "stop"        # stop | loop | continue
        self._list_cfg = None

        for v in (getattr(mset, "variables", None) or []):
            try:
                name = str(v["name"]).strip()
            except Exception:
                continue
            if not name:
                continue
            start = _num(v.get("start", 1))
            self.vars[name] = 1 if start is None else start
            self._defs[name] = {"step": _num(v.get("step", 1)),   # None 이면 증가 때 1 로
                                 "reset": v.get("reset", "run")}  # run=실행마다 / never

        ls = getattr(macro, "list_source", None) or None
        if ls and ls.get("path"):
            self._list_cfg = ls
            self._load_list(ls)
            self._apply_row()

    # ── 목록(CSV/TXT) ─────────────────────────────────────
    def _load_list(self, ls):
        path = ls.get("path", "")
        self._list_on_end = ls.get("on_end", "stop")
        rows = []
        try:
            if not path or not os.path.exists(path):
                self._rows = None
                return
            lower = path.lower()
            if lower.endswith(".csv"):
                with open(path, encoding="utf-8-sig", newline="") as f:
                    has_header = bool(ls.get("header", True))
                    if has_header:
                        for d in csv.DictReader(f):
                            rows.append({(k or "").strip(): (v or "") for k, v in d.items() if k is not None})
                    else:
                        for cells in csv.reader(f):
                            if not cells or not any((c or "").strip() for c in cells):
                                continue                       # 빈 줄 건너뜀 (TXT·헤더CSV 와 일관)
                            rows.append({f"열{i+1}": c for i, c in enumerate(cells)})
            else:  # TXT: 한 줄 = 한 데이터
                with open(path, encoding="utf-8-sig") as f:   # BOM 있는 윈도우 파일도
                    for line in f:
                        line = line.rstrip("\r\n")
                        if line.strip() == "":
                            continue
                        rows.append({"값": line})
        except Exception:
            self._rows = None
            return
        self._rows = rows

    def _apply_row(self):
        if self._rows is None:
            return
        if 0 <= self._li < len(self._rows):
            self.row = dict(self._rows[self._li])
        else:
            self.row = {}
            self.list_done = True

    def has_list(self):
        return bool(self._rows)

    def list_len(self):
        return len(self._rows) if self._rows else 0

    # ── 반복 넘어갈 때 ────────────────────────────────────
    def next_rep(self):
        """한 바퀴(loop) 끝나고 다음 회차로. 목록도 다음 행으로.
        반환: 계속 돌아도 되면 True, 목록이 끝나 멈춰야 하면 False."""
        self.rep += 1
        if self._rows:
            self._li += 1
            if self._li >= len(self._rows):
                if self._list_on_end == "loop":
                    self._li = 0
                else:                      # stop / continue
                    self.list_done = True
                    self._apply_row()
                    return self._list_on_end != "stop"
            self._apply_row()
        return True

    # ── 값 풀기 ───────────────────────────────────────────
    def value_of(self, name):
        key = (name or "").strip()
        # 사용자 목록 열·변수가 기본 토큰보다 우선 (CSV 에 '번호'·'날짜' 열이 있으면 그 값)
        if key in self.row:
            return self.row[key]
        if key in self.vars:
            return self.vars[key]
        low = key.lower()
        now = time.localtime()
        if low in ("번호", "순번", "no", "n", "index", "i1"):
            return self.rep + 1
        if low in ("반복", "회차0", "rep", "i", "i0"):
            return self.rep
        if low in ("날짜", "date"):
            return time.strftime("%Y-%m-%d", now)
        if low in ("시간", "time"):
            return time.strftime("%H:%M:%S", now)
        if low in ("날짜시간", "datetime"):
            return time.strftime("%Y-%m-%d %H:%M:%S", now)
        if low in ("요일", "weekday"):
            return "월화수목금토일"[now.tm_wday]
        return None

    def substitute(self, text):
        if not text or "{" not in text:
            return text

        def repl(m):
            v = self.value_of(m.group(1))
            return _fmt(v) if v is not None else m.group(0)   # 모르는 토큰은 그대로 둠

        return _TOKEN.sub(repl, text)

    def increment(self, name, step=None):
        key = (name or "").strip()
        if not key:
            return
        cur = _num(self.vars.get(key, 0))
        if cur is None:
            cur = 0
        if step is not None:                 # 호출에서 준 step (0 도 그대로)
            st = _num(step)
        else:
            st = self._defs.get(key, {}).get("step", 1)
        if st is None:                       # 정의도 없고 값도 이상하면 1
            st = 1
        self.vars[key] = cur + st

    def set_var(self, name, value):
        key = (name or "").strip()
        if key:
            self.vars[key] = value
