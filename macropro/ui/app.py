# -*- coding: utf-8 -*-
"""메인 창 — 여러 매크로 관리 + F12 실행/편집 토글 + 전역 설정.

단죄 매크로 기능(목록·기록·추가·편집·복사·삭제·실행주기·한영감지·키떼기·마우스복구)을
2026 톤(둥근 버튼·웜 팔레트)으로 재구성.
"""
import os
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _basename(p):
    try:
        return os.path.basename(p) or p
    except Exception:
        return p

from pynput import keyboard

from .. import keys as K
from .. import store
from ..engine import Engine
from ..model import Macro, MacroSet
from ..player import Player
from ..recorder import STOP_KEYS, Recorder
from . import theme as T
from . import widgets as W
from .editor import Editor

MODE_EDIT, MODE_RUN = "edit", "run"
CTRL_KEYS = {keyboard.Key.f8, keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f12}

HELP_TEXT = """⚡ 매크로 PRO — 빠른 사용법

● 3줄 요약
 1) 왼쪽 📋 매크로 → ＋ 추가로 매크로 만들기
 2) ✎ 편집에서 동작 쌓기(클릭·문구·붙여넣기…) 또는 ● 기록으로 직접 녹화
 3) 그 매크로에 '실행 단축키'(예 f1) 적고 → F12로 실행 모드 → f1 누르면 돎

● 단축키
 F8 좌표 찍기 · F9 녹화 시작/정지 · F10 정지 · F12 실행↔편집 전환

● 동작 종류
 🖱 클릭 / ✎ 문구 입력 / 📋 붙여넣기(긴 글·빠름) / 🔑 단축키 / ➡ 이동
 ⏱ 대기 / 🖲 스크롤 / 🖼 이미지 보이면 클릭 / ⏳ 이미지 뜰 때까지
 🔀 이미지 조건(없으면 N개 건너뛰기) / 🪟 창 조절(제목으로 띄우기·이동·크기)

● 여러 방에 한 번에 (✎ 편집 → 📡 멀티 타겟)
 방 위치를 F8로 찍거나 '창 제목'으로 등록 → 공통 문구 → 한 번에 모든 방에
 클릭→입력→엔터. 창이 겹쳐 있으면 '창 제목'이 더 안정적.

● 선택 매크로 설정
 반복(0=무한) · 배속 · 🔗 끝나면 다음 매크로(체인) · ⏰ 매일 자동 실행(HH:MM)

● 전역 설정
 실행 주기 · 타이밍 랜덤 · 🎲 동작마다 랜덤 대기(사람처럼) · 한/영 감지 ·
 종료 시 키 떼기 / 마우스 복구

● 저장
 작업은 자동 저장(꺼도 안 날아감). 💾 저장으로 .m 파일 따로 보관도 가능.

━━━ 고급 (🔧 변수·대상 / 편집기 새 동작) ━━━

● 🔢 자동 번호·변수
 문구에 {번호}(실행마다 1,2,3…) {날짜} {시간} {요일} 를 그냥 쓰면 돼.
 나만의 변수는 🔧 변수·대상에서 이름·시작·증가 정하고 {이름} 으로. 🔢변수+1 동작으로 올림.

● 📄 엑셀·TXT 목록 (한 줄씩 다른 값)
 📋 매크로 → 선택 매크로 → 📄 목록 에서 CSV/TXT 선택.
 문구에 {열이름}(CSV) 또는 {값}(TXT) → 줄마다 다른 내용으로 자동 반복. (목록이 끝까지 돎)

● 🧠 조건 (상황 보고 분기)
 편집기 '🧠 조건' = 창 있나/활성창 제목/클립보드 글/픽셀 색/이미지 보고
 안 맞으면 다음 동작 건너뛰기. (팝업 뜨면 닫기, 특정 창일 때만 실행 등)

● 🪟 창 기준 클릭
 편집기 '🪟 창 기준 클릭' = 창 제목 + 가로·세로 비율(0~1).
 창을 옮겨도 같은 버튼을 클릭 (좌표가 안 틀어짐).

● ⏰ 요일·기간 예약 / 🔗 체인 / ⚠ 오류 시 처리
 선택 매크로에서 요일·기간·오류(멈춤/건너뛰기)·끝나면 다음 매크로.

● 🧪 미리보기
 실행 전 [🧪 미리보기]로 순서·빠진 이미지·없는 변수 먼저 확인 (실제로 안 움직임).

⚠️ 매크로 탐지하는 게임·프로그램엔 쓰지 마세요(계정 정지 위험)."""


class App:
    def __init__(self, root):
        self.root = root
        self.set = store.load_set() or MacroSet()   # 자동저장 불러오기 (작업 안 날아감)
        if not self.set.macros:
            self.set.add(Macro(name="Macro 1"))
        self.eng = Engine()
        self.player = Player(self.eng)
        # 재생/리스너 스레드 → 큐로만 넘기고, 창(tkinter)은 메인스레드(_tick)에서만 건드림
        self._evtq = queue.Queue()
        self.player.on_status = lambda t: self._evtq.put(("status", t))
        self.player.on_done = lambda n: self._evtq.put(("done", n))
        self.player.on_progress = lambda d: self._evtq.put(("progress", d))
        self._run_id = None
        self._run_done = 0
        self.rec = None
        self.recording = False
        self._rec_target = None
        self._rec_done = None
        self.mode = MODE_EDIT
        self.pick_cb = None
        self._pick_multi = False
        self._last_name = "?"
        self._last_macro = None       # 체인(끝나면 다음 매크로)용
        self._chain_seen = set()      # 체인 무한루프 방지
        self._sched_fired = {}        # 예약 실행: {매크로이름: 'YYYY-MM-DD HH:MM'}
        self._closing = False
        self.path = None

        self.status = tk.StringVar(value="편집 모드")
        self.mousev = tk.StringVar(value="🖱 (0, 0)")
        self.prog = tk.StringVar(value="")        # 실행 진행 표시
        STOP_KEYS.clear()
        STOP_KEYS.update(CTRL_KEYS)

        self._style()
        self._build()
        self._hk = keyboard.Listener(on_press=self._on_key)
        self._hk.start()
        self.root.after(80, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.refresh_macros()

    def _style(self):
        self.root.configure(bg=T.COLORS["bg"])

    # ── 레이아웃 (사이드바 + 메인, Codex/ChatGPT 식 app-shell) ──
    def _build(self):
        r = self.root
        r.title("⚡ 매크로 PRO")
        r.geometry("820x600")
        r.minsize(720, 460)
        # grid: 사이드바(col0 고정) + 메인(col1 늘어남) — CustomTkinter 공식 예제 구조
        r.grid_columnconfigure(1, weight=1)
        r.grid_rowconfigure(0, weight=1)

        self._build_sidebar(r)

        # ── 메인 ──
        main = tk.Frame(r, bg=T.COLORS["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        topbar = tk.Frame(main, bg=T.COLORS["bg"])
        topbar.pack(side="top", fill="x", padx=22, pady=(16, 6))
        self.page_title = tk.StringVar(value="📋  매크로")
        tk.Label(topbar, textvariable=self.page_title, bg=T.COLORS["bg"], fg=T.COLORS["ink"],
                 font=T.font(15, "bold")).pack(side="left")
        tk.Label(topbar, textvariable=self.mousev, bg=T.COLORS["bg"], fg=T.COLORS["sub"],
                 font=T.font(9)).pack(side="right")

        # 실행 진행 표시줄 (실행 중일 때만 글자 뜸)
        tk.Label(main, textvariable=self.prog, bg=T.COLORS["bg"], fg=T.COLORS["green"],
                 font=T.font(9, "bold"), anchor="w").pack(side="top", fill="x", padx=22, pady=(0, 2))

        self.statusbar = tk.Label(main, textvariable=self.status, bg=T.COLORS["bg"], fg=T.COLORS["accentDk"],
                                  font=T.font(10, "bold"), anchor="w")
        self.statusbar.pack(side="bottom", fill="x", padx=22, pady=(0, 10))

        self.main_body = tk.Frame(main, bg=T.COLORS["bg"])
        self.main_body.pack(side="top", fill="both", expand=True)

        self.pages = {}
        self._build_page_macros()
        self._build_page_global()
        self._build_page_settings()
        self._build_page_history()
        self._build_page_help()
        self.show_page("macros")

    def _build_sidebar(self, r):
        side = tk.Frame(r, bg=T.COLORS["side"], width=200)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.pack_propagate(False)
        tk.Label(side, text="⚡  매크로 PRO", bg=T.COLORS["side"], fg=T.COLORS["sideInk"],
                 font=T.font(13, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        pf = tk.Frame(side, bg=T.COLORS["side"])
        pf.pack(anchor="w", padx=16, pady=(2, 14))
        self.pill = W.Pill(pf, "편집 모드", T.COLORS["slate"], width=150, height=28)
        self.pill.pack(anchor="w")

        self._nav = {}
        for key, text in [("macros", "📋   매크로"), ("global", "⚙   전역 설정"),
                          ("settings", "🔧   변수·대상"),
                          ("history", "📜   실행 기록"), ("help", "❓   도움말")]:
            nb = W.NavButton(side, text, lambda k=key: self.show_page(k))
            nb.pack(fill="x", padx=10, pady=1)
            self._nav[key] = nb

        tk.Frame(side, bg=T.COLORS["side"]).pack(fill="both", expand=True)   # 아래로 밀기(spacer)

        for row in (
            [("💾 저장", self.save_file, "accent"), ("📂 열기", self.load_file, "slate")],
            [("■ 정지", self.stop_play, "red"), ("종료", self._quit, "slate")],
        ):
            bar = tk.Frame(side, bg=T.COLORS["side"])
            bar.pack(fill="x", padx=10, pady=(0, 6))
            for txt, cmd, ck in row:
                W.RoundButton(bar, txt, cmd, bg=T.COLORS[ck], hover=T.COLORS[ck + "Dk"],
                              width=84, height=34, radius=10, font=T.font(9, "bold")).pack(side="left", expand=True, fill="x", padx=2)

    # ── 페이지들 ──────────────────────────────────────────
    def _page_frame(self, key):
        f = tk.Frame(self.main_body, bg=T.COLORS["bg"])
        self.pages[key] = f
        return f

    def _build_page_macros(self):
        f = self._page_frame("macros")
        sc = W.ScrollFrame(f)
        sc.pack(fill="both", expand=True)
        host = sc.body

        listcard = W.Card(host, "📋 매크로 목록  (F12 = 실행↔편집 전환)")
        listcard.pack(fill="x", padx=14, pady=(4, 0))
        inner = tk.Frame(listcard.body, bg=T.COLORS["surface"])
        inner.pack(fill="both", expand=True)
        self.lb = tk.Listbox(inner, height=7, font=T.font(11), bg="white", fg=T.COLORS["ink"],
                             selectbackground=T.COLORS["accentSoft"], selectforeground=T.COLORS["ink"],
                             relief="flat", highlightthickness=0, activestyle="none")
        self.lb.pack(side="left", fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda e: self._sync_sel())
        btns = tk.Frame(inner, bg=T.COLORS["surface"])
        btns.pack(side="right", fill="y", padx=(10, 0))
        specs = [("● 기록", self.toggle_record, "accent"), ("＋ 추가", self.add_macro, "slate"),
                 ("✎ 편집", self.edit_macro, "slate"), ("⧉ 복사", self.copy_macro, "slate"),
                 ("🗑 삭제", self.del_macro, "red"), ("▲", lambda: self.move_macro(-1), "slate"),
                 ("▼", lambda: self.move_macro(1), "slate")]
        self._recbtn = None
        for txt, cmd, ck in specs:
            b = W.RoundButton(btns, txt, cmd, bg=T.COLORS[ck], hover=T.COLORS[ck + "Dk"],
                              width=96, height=32, radius=10, font=T.font(9, "bold"))
            b.pack(pady=3)
            if "기록" in txt:
                self._recbtn = b

        mc = W.Card(host, "🎛 선택 매크로")
        mc.pack(fill="x", padx=14, pady=(10, 12))
        b = mc.body
        self.m_hot = tk.StringVar()
        self.m_loop = tk.StringVar(value="1")
        self.m_speed = tk.StringVar(value="1.0")
        self.m_chain = tk.StringVar()
        self.m_sched = tk.StringVar()
        W.label(b, "실행 단축키 (예 f1)").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_hot, 8).grid(row=0, column=1, sticky="w")
        W.label(b, "반복(0=무한)").grid(row=0, column=2, sticky="e", padx=4)
        W.entry(b, self.m_loop, 6).grid(row=0, column=3, sticky="w")
        W.label(b, "배속").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_speed, 6).grid(row=1, column=1, sticky="w")
        W.RoundButton(b, "▶ 테스트 실행", self.test_run, bg=T.COLORS["green"], hover=T.COLORS["greenDk"],
                      width=120, height=32, radius=10, font=T.font(9, "bold")).grid(row=1, column=2, columnspan=2, padx=4)
        W.label(b, "🔗 끝나면 실행할 매크로").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_chain, 16).grid(row=2, column=1, columnspan=3, sticky="w")
        W.label(b, "⏰ 자동 실행 (HH:MM)").grid(row=3, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_sched, 10).grid(row=3, column=1, sticky="w")
        # 요일 제한 (아무것도 안 고르면 매일)
        W.label(b, "요일").grid(row=4, column=0, sticky="e", padx=4, pady=3)
        dfr = tk.Frame(b, bg=T.COLORS["surface"])
        dfr.grid(row=4, column=1, columnspan=3, sticky="w")
        self.m_days = []
        for i, dn in enumerate("월화수목금토일"):
            bv = tk.BooleanVar(value=False)
            tk.Checkbutton(dfr, text=dn, variable=bv, bg=T.COLORS["surface"], fg=T.COLORS["sub"],
                           activebackground=T.COLORS["surface"], selectcolor="white",
                           font=T.font(9), command=self._save_sel).pack(side="left")
            self.m_days.append(bv)
        W.label(b, "기간(시작~종료 YYYY-MM-DD)").grid(row=5, column=0, sticky="e", padx=4, pady=3)
        self.m_start = tk.StringVar(); self.m_end = tk.StringVar()
        pfr = tk.Frame(b, bg=T.COLORS["surface"])
        pfr.grid(row=5, column=1, columnspan=3, sticky="w")
        W.entry(pfr, self.m_start, 11).pack(side="left")
        tk.Label(pfr, text=" ~ ", bg=T.COLORS["surface"], fg=T.COLORS["sub"]).pack(side="left")
        W.entry(pfr, self.m_end, 11).pack(side="left")
        # 오류 기본 + 목록 + 미리보기
        W.label(b, "오류 시").grid(row=6, column=0, sticky="e", padx=4, pady=3)
        self.m_err = tk.StringVar(value="멈춤")
        ttk.Combobox(b, textvariable=self.m_err, state="readonly", width=8,
                     values=["멈춤", "건너뛰기"]).grid(row=6, column=1, sticky="w")
        W.RoundButton(b, "📄 목록", self._pick_list, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=72, height=30, radius=10, font=T.font(9, "bold")).grid(row=6, column=2, padx=2)
        W.RoundButton(b, "🧪 미리보기", self._preview, bg=T.COLORS["amber"], hover=T.COLORS["amberDk"],
                      width=92, height=30, radius=10, font=T.font(9, "bold")).grid(row=6, column=3, padx=2)
        self.m_listlbl = tk.StringVar(value="")
        tk.Label(b, textvariable=self.m_listlbl, bg=T.COLORS["surface"], fg=T.COLORS["sub"],
                 font=T.font(8)).grid(row=7, column=0, columnspan=4, sticky="w")
        for v in (self.m_hot, self.m_loop, self.m_speed, self.m_chain, self.m_sched,
                  self.m_start, self.m_end, self.m_err):
            v.trace_add("write", lambda *a: self._save_sel())

    def _build_page_global(self):
        f = self._page_frame("global")
        sc = W.ScrollFrame(f)
        sc.pack(fill="both", expand=True)
        host = sc.body
        gc = W.Card(host, "⚙ 전역 설정 (모든 매크로 공통)")
        gc.pack(fill="x", padx=14, pady=(4, 12))
        b = gc.body
        self.cycle = tk.StringVar(value=str(self.set.cycle_ms))
        self.jit = tk.StringVar(value=str(self.set.jitter_pct))
        self.rmin = tk.StringVar(value=str(self.set.rand_min_ms))
        self.rmax = tk.StringVar(value=str(self.set.rand_max_ms))
        W.label(b, "이벤트 실행 주기(ms)").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.cycle, 6).grid(row=0, column=1, sticky="w")
        W.label(b, "타이밍 랜덤 ±%").grid(row=0, column=2, sticky="e", padx=4)
        W.entry(b, self.jit, 6).grid(row=0, column=3, sticky="w")
        W.label(b, "🎲 동작마다 랜덤 대기(ms) 최소").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.rmin, 6).grid(row=1, column=1, sticky="w")
        W.label(b, "최대").grid(row=1, column=2, sticky="e", padx=4)
        W.entry(b, self.rmax, 6).grid(row=1, column=3, sticky="w")
        self.c_ime = tk.BooleanVar(value=self.set.ime_detect)
        self.c_rel = tk.BooleanVar(value=self.set.release_on_stop)
        self.c_res = tk.BooleanVar(value=self.set.restore_mouse)
        self.c_mov = tk.BooleanVar(value=self.set.record_moves)
        for i, (txt, var) in enumerate([("한/영(IME) 감지 → 실행 중 영문 고정", self.c_ime),
                                        ("종료 시 눌린 키·버튼 모두 떼기", self.c_rel),
                                        ("종료 시 마우스 위치 복구", self.c_res),
                                        ("녹화할 때 마우스 '이동'도 기록", self.c_mov)]):
            tk.Checkbutton(b, text=txt, variable=var, bg=T.COLORS["surface"], fg=T.COLORS["sub"],
                           activebackground=T.COLORS["surface"], selectcolor="white",
                           font=T.font(9), command=self._save_global).grid(row=2 + i, column=0, columnspan=4, sticky="w", pady=1)
        for v in (self.cycle, self.jit, self.rmin, self.rmax):
            v.trace_add("write", lambda *a: self._save_global())

    def _build_page_history(self):
        f = self._page_frame("history")
        row = tk.Frame(f, bg=T.COLORS["bg"])
        row.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        W.RoundButton(row, "🔄 새로고침", self._refresh_history, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=104, height=34, radius=10, font=T.font(9, "bold")).pack(side="left", padx=3)
        W.RoundButton(row, "🗑 기록 비우기", self._clear_history, bg=T.COLORS["red"], hover=T.COLORS["redDk"],
                      width=118, height=34, radius=10, font=T.font(9, "bold")).pack(side="left", padx=3)
        card = W.Card(f, "📜 언제 어떤 매크로를 몇 번 돌렸나")
        card.pack(side="top", fill="both", expand=True, padx=14, pady=(4, 6))
        self.hist_lb = tk.Listbox(card.body, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                                  selectbackground=T.COLORS["accentSoft"], selectforeground=T.COLORS["ink"],
                                  relief="flat", highlightthickness=0, activestyle="none")
        self.hist_lb.pack(fill="both", expand=True)

    def _build_page_help(self):
        f = self._page_frame("help")
        card = W.Card(f)
        card.pack(fill="both", expand=True, padx=14, pady=(4, 8))
        txt = tk.Text(card.body, wrap="word", bg="white", fg=T.COLORS["ink"], relief="flat",
                      highlightthickness=0, font=T.font(10), padx=12, pady=10)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", HELP_TEXT)
        txt.configure(state="disabled")

    # ── 🔧 변수 · 대상 페이지 ─────────────────────────────
    def _build_page_settings(self):
        f = self._page_frame("settings")
        sc = W.ScrollFrame(f)
        sc.pack(fill="both", expand=True)
        host = sc.body

        # 🔢 변수 (자동 번호)
        vc = W.Card(host, "🔢 변수 (문구에 {이름} 으로 넣기 · 자동 번호)")
        vc.pack(fill="x", padx=14, pady=(4, 0))
        self.var_lb = tk.Listbox(vc.body, height=4, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                                 selectbackground=T.COLORS["accentSoft"], selectforeground=T.COLORS["ink"],
                                 relief="flat", highlightthickness=0, activestyle="none")
        self.var_lb.pack(fill="x")
        vr = tk.Frame(vc.body, bg=T.COLORS["surface"])
        vr.pack(fill="x", pady=(6, 0))
        self.vn = tk.StringVar(); self.vs = tk.StringVar(value="1"); self.vstep = tk.StringVar(value="1")
        W.label(vr, "이름").pack(side="left", padx=(0, 2)); W.entry(vr, self.vn, 8).pack(side="left", padx=2)
        W.label(vr, "시작").pack(side="left", padx=(6, 2)); W.entry(vr, self.vs, 5).pack(side="left", padx=2)
        W.label(vr, "증가").pack(side="left", padx=(6, 2)); W.entry(vr, self.vstep, 4).pack(side="left", padx=2)
        W.RoundButton(vr, "＋ 추가", self._add_var, bg=T.COLORS["green"], hover=T.COLORS["greenDk"],
                      width=74, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=4)
        W.RoundButton(vr, "🗑", self._del_var, bg=T.COLORS["red"], hover=T.COLORS["redDk"],
                      width=40, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=2)
        tk.Label(vc.body, text="예) 문구에  공지 {번호}번  → 실행마다 1,2,3…  (기본 {번호}{날짜}{시간}{요일} 은 그냥 쓰면 됨)",
                 bg=T.COLORS["surface"], fg=T.COLORS["sub"], font=T.font(8)).pack(anchor="w", pady=(4, 0))

        # 📚 저장 대상
        tc = W.Card(host, "📚 저장 대상 (자주 쓰는 방/창 — 멀티 타겟에서 재사용)")
        tc.pack(fill="x", padx=14, pady=(10, 0))
        self.tgt_lb = tk.Listbox(tc.body, height=4, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                                 selectbackground=T.COLORS["accentSoft"], selectforeground=T.COLORS["ink"],
                                 relief="flat", highlightthickness=0, activestyle="none")
        self.tgt_lb.pack(fill="x")
        tr = tk.Frame(tc.body, bg=T.COLORS["surface"])
        tr.pack(fill="x", pady=(6, 0))
        self.tn = tk.StringVar(); self.tw = tk.StringVar()
        W.label(tr, "이름").pack(side="left", padx=(0, 2)); W.entry(tr, self.tn, 8).pack(side="left", padx=2)
        W.label(tr, "창 제목(일부)").pack(side="left", padx=(6, 2)); W.entry(tr, self.tw, 14).pack(side="left", padx=2)
        W.RoundButton(tr, "🪟 창 추가", self._add_tgt_win, bg=T.COLORS["green"], hover=T.COLORS["greenDk"],
                      width=86, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=4)
        W.RoundButton(tr, "📍 좌표(F8)", self._add_tgt_coord, bg=T.COLORS["amber"], hover=T.COLORS["amberDk"],
                      width=90, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=2)
        W.RoundButton(tr, "🗑", self._del_tgt, bg=T.COLORS["red"], hover=T.COLORS["redDk"],
                      width=40, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=2)

        # ⚠ 오류 기본 처리 안내
        ec = W.Card(host, "⚠ 실행 오류 · 미리보기")
        ec.pack(fill="x", padx=14, pady=(10, 12))
        tk.Label(ec.body, text="동작마다 '오류 시 처리'(멈춤/건너뛰기/재시도)는 편집 창에서 동작별로 정할 수 있어요.\n"
                               "매크로를 처음 돌리기 전엔 📋 매크로에서 [🧪 미리보기]로 순서·내용을 확인하세요.",
                 bg=T.COLORS["surface"], fg=T.COLORS["sub"], font=T.font(9), justify="left").pack(anchor="w")

    def _refresh_vars(self):
        if not hasattr(self, "var_lb"):
            return
        self.var_lb.delete(0, "end")
        for v in (self.set.variables or []):
            self.var_lb.insert("end", f"  {v.get('name','')}  = 시작 {v.get('start',1)} · 증가 {v.get('step',1)}")
        if not self.set.variables:
            self.var_lb.insert("end", "  (없음 — 아래에서 추가)")

    def _add_var(self):
        name = self.vn.get().strip()
        if not name:
            return
        from .. import values as _V
        self.set.variables = [v for v in (self.set.variables or []) if v.get("name") != name]
        self.set.variables.append({"name": name, "start": _V.to_num(self.vs.get(), 1),
                                   "step": _V.to_num(self.vstep.get(), 1), "reset": "run"})
        self.vn.set("")
        self._refresh_vars()
        store.save_set(self.set)

    def _del_var(self):
        s = self.var_lb.curselection()
        if s and s[0] < len(self.set.variables or []):
            del self.set.variables[s[0]]
            self._refresh_vars()
            store.save_set(self.set)

    def _refresh_targets(self):
        if not hasattr(self, "tgt_lb"):
            return
        self.tgt_lb.delete(0, "end")
        for t in (self.set.targets or []):
            if t.get("kind") == "window":
                self.tgt_lb.insert("end", f"  {t.get('name','')}  🪟 \"{t.get('title','')}\"")
            else:
                self.tgt_lb.insert("end", f"  {t.get('name','')}  📍 ({t.get('x',0)}, {t.get('y',0)})")
        if not self.set.targets:
            self.tgt_lb.insert("end", "  (없음 — 아래에서 추가)")

    def _new_tid(self):
        import time as _t
        return "t" + str(int(_t.time() * 1000) % 100000000)

    def _add_tgt_win(self):
        name = self.tn.get().strip()
        title = self.tw.get().strip()
        if not name or not title:
            self.toast("대상 이름과 창 제목을 넣어줘")
            return
        self.set.targets.append({"id": self._new_tid(), "name": name, "kind": "window", "title": title})
        self.tn.set(""); self.tw.set("")
        self._refresh_targets()
        store.save_set(self.set)

    def _add_tgt_coord(self):
        name = self.tn.get().strip()
        if not name:
            self.toast("대상 이름 먼저 넣고 📍")
            return
        self.arm_pick(lambda x, y: self._save_tgt_coord(name, x, y))
        self.toast("📍 그 방 입력칸 위치에서 F8")

    def _save_tgt_coord(self, name, x, y):
        self.set.targets.append({"id": self._new_tid(), "name": name, "kind": "coord", "x": x, "y": y})
        self.tn.set("")
        self.disarm_pick()
        self._refresh_targets()
        store.save_set(self.set)
        self.toast(f"대상 '{name}' ({x},{y}) 저장")

    def _del_tgt(self):
        s = self.tgt_lb.curselection()
        if s and s[0] < len(self.set.targets or []):
            del self.set.targets[s[0]]
            self._refresh_targets()
            store.save_set(self.set)

    def show_page(self, key):
        for fr in self.pages.values():
            fr.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        titles = {"macros": "📋  매크로", "global": "⚙  전역 설정", "settings": "🔧  변수 · 대상 · 목록",
                  "history": "📜  실행 기록", "help": "❓  도움말"}
        self.page_title.set(titles.get(key, ""))
        for k, nb in self._nav.items():
            nb.set_active(k == key)
        if key == "history":
            self._refresh_history()
        elif key == "settings":
            self._refresh_vars()
            self._refresh_targets()

    def _refresh_history(self):
        self.hist_lb.delete(0, "end")
        rows = store.recent_run_log(200)
        if not rows:
            self.hist_lb.insert("end", "  (아직 실행 기록 없음)")
            return
        st = {"done": "✅", "running": "⏳", "stopped": "■", "error": "⚠"}
        for name, started, ended, loops, total, done, status in rows:
            when = time.strftime("%m-%d %H:%M:%S", time.localtime(started)) if started else ""
            mark = st.get(status, "·")
            prog = f"{done}/{total}" if total else f"{loops}회"
            self.hist_lb.insert("end", f"  {mark} {when}   {name}   ·{prog}")

    def _clear_history(self):
        store.clear_runs()
        self._refresh_history()

    # ── 매크로 목록 ───────────────────────────────────────
    def refresh_macros(self):
        sel = self._sel_index()
        self.lb.delete(0, "end")
        for m in self.set.macros:
            hk = f"  [{m.hotkey}]" if m.hotkey else ""
            loop = "∞" if m.loops == 0 else f"×{m.loops}"
            self.lb.insert("end", f"  {m.name}{hk}   ·{len(m.actions)}동작 {loop}")
        if self.set.macros:
            self.lb.selection_clear(0, "end")
            self.lb.selection_set(min(sel if sel is not None else 0, len(self.set.macros) - 1))
        self._sync_sel()
        store.save_set(self.set)        # 자동 저장

    def _sel_index(self):
        s = self.lb.curselection()
        return s[0] if s else None

    def _sel_macro(self):
        i = self._sel_index()
        return self.set.macros[i] if i is not None and i < len(self.set.macros) else None

    def _sync_sel(self):
        m = self._sel_macro()
        if not m:
            return
        self._loading = True
        self.m_hot.set(m.hotkey); self.m_loop.set(str(m.loops)); self.m_speed.set(str(m.speed))
        self.m_chain.set(m.chain); self.m_sched.set(m.schedule)
        days = getattr(m, "sched_days", None) or []
        for i, bv in enumerate(self.m_days):
            bv.set(i in days)
        self.m_start.set(getattr(m, "sched_start", "") or "")
        self.m_end.set(getattr(m, "sched_end", "") or "")
        self.m_err.set("건너뛰기" if getattr(m, "err", "stop") == "skip" else "멈춤")
        ls = getattr(m, "list_source", None) or {}
        self.m_listlbl.set(("📄 목록: " + _basename(ls.get("path", ""))) if ls.get("path") else "")
        self._loading = False

    def _save_sel(self):
        if getattr(self, "_loading", False):
            return
        m = self._sel_macro()
        if not m:
            return
        m.hotkey = self.m_hot.get().strip().lower()
        try:
            m.loops = int(self.m_loop.get())
        except ValueError:
            pass
        try:
            m.speed = max(0.05, float(self.m_speed.get()))
        except ValueError:
            pass
        m.chain = self.m_chain.get().strip()
        m.schedule = self._clean_time(self.m_sched.get())
        m.sched_days = [i for i, bv in enumerate(self.m_days) if bv.get()]
        m.sched_start = self.m_start.get().strip()
        m.sched_end = self.m_end.get().strip()
        m.err = "skip" if self.m_err.get() == "건너뛰기" else "stop"
        self.lb_quiet_refresh()
        store.save_set(self.set)

    def _pick_list(self):
        m = self._sel_macro()
        if not m:
            return
        p = filedialog.askopenfilename(title="목록 파일 (CSV 또는 TXT)",
                                       filetypes=[("목록 파일", "*.csv *.txt"), ("모든 파일", "*.*")])
        if not p:
            return
        m.list_source = {"path": p, "header": True, "on_end": "stop"}
        self.m_listlbl.set("📄 목록: " + _basename(p) + "  (끝나면 멈춤)")
        store.save_set(self.set)
        self.toast("목록 연결됨 — 문구에 {열이름} 또는 {값} 으로 쓰면 줄마다 들어가")

    def _preview(self):
        m = self._sel_macro()
        if not m:
            return
        from .preview import Preview
        Preview(self, m)

    @staticmethod
    def _clean_time(s):
        """'9:5' '0930' 등 → 'HH:MM' 로 정리, 이상하면 빈값."""
        s = (s or "").strip()
        if not s:
            return ""
        s = s.replace("：", ":")
        try:
            if ":" in s:
                h, m = s.split(":", 1)
            elif len(s) == 4 and s.isdigit():
                h, m = s[:2], s[2:]
            else:
                return ""
            h, m = int(h), int(m)
            if 0 <= h < 24 and 0 <= m < 60:
                return f"{h:02d}:{m:02d}"
        except Exception:
            pass
        return ""

    def lb_quiet_refresh(self):
        i = self._sel_index()
        self.lb.delete(0, "end")
        for m in self.set.macros:
            hk = f"  [{m.hotkey}]" if m.hotkey else ""
            loop = "∞" if m.loops == 0 else f"×{m.loops}"
            self.lb.insert("end", f"  {m.name}{hk}   ·{len(m.actions)}동작 {loop}")
        if i is not None:
            self.lb.selection_set(i)

    def _save_global(self):
        try:
            self.set.cycle_ms = max(0, int(float(self.cycle.get())))
        except ValueError:
            pass
        try:
            self.set.jitter_pct = max(0, int(float(self.jit.get())))
        except ValueError:
            pass
        try:
            self.set.rand_min_ms = max(0, int(float(self.rmin.get())))
        except ValueError:
            pass
        try:
            self.set.rand_max_ms = max(0, int(float(self.rmax.get())))
        except ValueError:
            pass
        self.set.ime_detect = self.c_ime.get()
        self.set.release_on_stop = self.c_rel.get()
        self.set.restore_mouse = self.c_res.get()
        self.set.record_moves = self.c_mov.get()
        store.save_set(self.set)

    def add_macro(self):
        self.set.add()
        self.refresh_macros()
        self.lb.selection_clear(0, "end")
        self.lb.selection_set("end")
        self._sync_sel()

    def copy_macro(self):
        m = self._sel_macro()
        if m:
            self.set.macros.append(m.copy())
            self.refresh_macros()

    def del_macro(self):
        i = self._sel_index()
        if i is None:
            return
        if len(self.set.macros) <= 1:
            messagebox.showinfo("매크로", "최소 1개는 있어야 해요.")
            return
        del self.set.macros[i]
        self.refresh_macros()

    def move_macro(self, d):
        i = self._sel_index()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(self.set.macros):
            self.set.macros[i], self.set.macros[j] = self.set.macros[j], self.set.macros[i]
            self.refresh_macros()
            self.lb.selection_clear(0, "end")
            self.lb.selection_set(j)
            self._sync_sel()

    def edit_macro(self):
        if self.mode == MODE_RUN:
            self.toast("실행 모드에선 편집 불가 (F12로 편집 모드)")
            return
        m = self._sel_macro()
        if m:
            Editor(self, m)

    # ── 녹화 ──────────────────────────────────────────────
    def toggle_record(self):
        if self.mode == MODE_RUN:
            self.toast("실행 모드에선 녹화 불가 (F12)")
            return
        if self.recording:
            self._stop_record()
        else:
            m = self._sel_macro()
            if m:
                self.record_into(m)

    def record_into(self, macro, on_done=None):
        if self.recording or self.player.playing:
            return
        self._save_global()
        self.rec = Recorder(record_moves=self.set.record_moves)
        self._rec_target = macro
        self._rec_done = on_done
        self.recording = True
        if self._recbtn:
            self._recbtn.set_text("■ 정지")
        self.rec.start()
        self.toast(f"● '{macro.name}' 녹화 중…  (F9 정지)")

    def _stop_record(self):
        if not self.recording:
            return
        actions = self.rec.stop()
        self._rec_target.actions = actions
        self.recording = False
        if self._recbtn:
            self._recbtn.set_text("● 기록")
        self.toast(f"녹화 끝 · {len(actions)}동작")
        if self._rec_done:
            try:                        # 편집창이 이미 닫혔으면 죽은 위젯 건드려 터질 수 있음
                self._rec_done()
            except Exception:
                pass
            self._rec_done = None
        self.refresh_macros()

    # ── 재생 ──────────────────────────────────────────────
    def test_run(self):
        m = self._sel_macro()
        if m:
            self._play(m)

    def _play(self, macro, reset_chain=True):
        if self._closing:
            return
        if self.recording or self.player.playing or not macro.actions:
            if not macro.actions:
                self.toast("동작이 없어요 (기록/편집)")
            return
        self._save_global()
        self._last_name = macro.name
        self._last_macro = macro
        if reset_chain:
            self._chain_seen = {macro.name}
        self._run_done = 0
        self._run_id = store.start_run(macro.name, len(macro.actions))   # 상세 실행 기록 시작
        self.player.play(
            macro.actions, loops=macro.loops, speed=macro.speed,
            jitter=self.set.jitter_pct / 100.0, cycle=self.set.cycle_ms / 1000.0,
            ime_lock=self.set.ime_detect, release_all=self.set.release_on_stop,
            restore_mouse=self.set.restore_mouse,
            rand_min=self.set.rand_min_ms / 1000.0, rand_max=self.set.rand_max_ms / 1000.0,
            mset=self.set, macro=macro, default_err=getattr(macro, "err", "stop"),
            name=macro.name)
        self.toast(f"▶ '{macro.name}' 실행")

    def stop_play(self):
        self._chain_seen = set()      # 정지하면 체인도 끊음
        self.player.stop()

    def _find_macro(self, name):
        name = (name or "").strip()
        for m in self.set.macros:
            if m.name == name:
                return m
        return None

    def _on_play_done(self, n):
        self.toast(f"실행 끝 ({n}회)")
        self.prog.set("")
        store.log_run(self._last_name, n)      # 실행 기록(SQLite)
        store.finish_run(self._run_id, n, self._run_done, "done")   # 상세 기록 마감
        self._run_id = None
        # 🔗 체인: 끝나면 이어서 다음 매크로 (무한루프 방지 — 이미 돈 건 안 함)
        m = self._last_macro
        if m and m.chain and not self._closing:
            nxt = self._find_macro(m.chain)
            if nxt and nxt.name not in self._chain_seen and nxt.actions:
                self._chain_seen.add(nxt.name)
                self.root.after(120, lambda: self._play(nxt, reset_chain=False))

    # ── 모드 토글 (F12) ───────────────────────────────────
    def toggle_mode(self):
        if self.player.playing:
            self.player.stop()
        if self.recording:
            self._stop_record()
        self.mode = MODE_RUN if self.mode == MODE_EDIT else MODE_EDIT
        if self.mode == MODE_RUN:
            self.pill.set("▶ 실행 대기 (단축키)", T.COLORS["green"])
            self.status.set("실행 모드 — 각 매크로 단축키로 실행")
        else:
            self.pill.set("편집 모드", T.COLORS["slate"])
            self.status.set("편집 모드")

    # ── 전역 단축키 ───────────────────────────────────────
    def _on_key(self, key):
        # 이 콜백은 pynput 리스너(딴 스레드)에서 옴 → 창은 직접 못 건드림, 큐로만 넘김
        if self._closing:
            return
        if key == keyboard.Key.f8 and self.pick_cb:
            x, y = self.eng.get_pos()
            cb = self.pick_cb
            if not self._pick_multi:           # 멀티면 계속 찍기, 아니면 한 번만
                self.pick_cb = None
            self._evtq.put(("call", lambda cx=int(x), cy=int(y): cb(cx, cy)))
            return
        if key == keyboard.Key.f12:
            self._evtq.put(("call", self.toggle_mode))
            return
        if key == keyboard.Key.f9:
            self._evtq.put(("call", self.toggle_record))
            return
        if key == keyboard.Key.f10:
            self._evtq.put(("call", self.stop_play))
            return
        if self.mode == MODE_RUN and not self.player.playing:
            name = K.key_name(key)
            for m in self.set.macros:
                if m.hotkey and m.hotkey == name:
                    self._evtq.put(("call", lambda mm=m: self._play(mm)))
                    break

    # 편집창이 좌표 찍기 요청
    def arm_pick(self, cb, multi=False):
        self.pick_cb = cb
        self._pick_multi = multi

    def disarm_pick(self):
        self.pick_cb = None
        self._pick_multi = False

    # ── 파일 ──────────────────────────────────────────────
    def save_file(self):
        self._save_global()
        p = filedialog.asksaveasfilename(defaultextension=".m", filetypes=[("매크로 파일", "*.m"), ("모든 파일", "*.*")])
        if not p:
            return
        try:
            self.set.save(p)
            self.path = p
            self.toast(f"저장됨 · {len(self.set.macros)}개 매크로")
        except Exception as ex:
            messagebox.showwarning("저장", str(ex))

    def load_file(self):
        p = filedialog.askopenfilename(filetypes=[("매크로 파일", "*.m"), ("모든 파일", "*.*")])
        if not p:
            return
        try:
            self.set = MacroSet.load(p)
            self.path = p
            if not self.set.macros:
                self.set.add(Macro(name="Macro 1"))
            self.cycle.set(str(self.set.cycle_ms)); self.jit.set(str(self.set.jitter_pct))
            self.rmin.set(str(self.set.rand_min_ms)); self.rmax.set(str(self.set.rand_max_ms))
            self.c_ime.set(self.set.ime_detect); self.c_rel.set(self.set.release_on_stop)
            self.c_res.set(self.set.restore_mouse); self.c_mov.set(self.set.record_moves)
            self.refresh_macros()
            self.toast(f"불러옴 · {len(self.set.macros)}개 매크로")
        except Exception as ex:
            messagebox.showwarning("불러오기", str(ex))

    # ── 기타 ──────────────────────────────────────────────
    def toast(self, t):
        self.status.set(t)

    def _tick(self):
        # 딴 스레드가 큐에 넣은 일을 여기(메인스레드)서 처리 — tkinter 안전
        for _ in range(200):
            try:
                kind, val = self._evtq.get_nowait()
            except queue.Empty:
                break
            try:
                if kind == "status":
                    self.toast(val)
                elif kind == "done":
                    self._on_play_done(val)
                elif kind == "progress":
                    self._run_done = val.get("done", self._run_done)
                    tot = val.get("total", 0)
                    self.prog.set(f"▶ {val.get('done',0)}/{tot}  ·  {str(val.get('label',''))[:34]}")
                elif kind == "call":
                    val()
            except Exception:
                pass
        try:
            x, y = self.eng.get_pos()
            self.mousev.set(f"🖱 ({int(x)}, {int(y)})")
        except Exception:
            pass
        self._check_schedule()
        if not self._closing:
            self.root.after(90, self._tick)

    def _check_schedule(self):
        # ⏰ 예약 실행 — 시각 + 요일 + 기간. 분당 1번 검사, 같은 분 중복 방지.
        if self.mode != MODE_RUN or self.player.playing or self.recording:
            return
        now = time.localtime()
        stamp = time.strftime("%Y-%m-%d %H:%M", now)
        hm = time.strftime("%H:%M", now)
        today = time.strftime("%Y-%m-%d", now)
        wday = now.tm_wday   # 0=월 .. 6=일
        for m in self.set.macros:
            if not (m.schedule and m.schedule == hm and m.actions):
                continue
            days = getattr(m, "sched_days", None) or []
            if days and wday not in days:            # 요일 제한
                continue
            start = getattr(m, "sched_start", "") or ""
            end = getattr(m, "sched_end", "") or ""
            if start and today < start:              # 기간 전
                continue
            if end and today > end:                  # 기간 후
                continue
            if self._sched_fired.get(m.name) != stamp:
                self._sched_fired[m.name] = stamp
                self._play(m)
                break

    def _quit(self):
        self._closing = True
        # 콜백부터 끊어 파괴된 창을 건드리지 않게
        self.player.on_status = None
        self.player.on_done = None
        self.player.on_progress = None
        alive = False
        try:
            self.player.stop()
            t = self.player._thread
            if t and t.is_alive():
                t.join(timeout=4)         # 재생 스레드가 눌린 키 다 떼고 끝날 때까지 기다림
                alive = t.is_alive()      # 그래도 안 끝났으면(긴 타이핑 등) 표시
        except Exception:
            pass
        try:
            if self.recording and self.rec:
                self.rec.stop()
        except Exception:
            pass
        try:
            self._hk.stop()
        except Exception:
            pass
        if not alive:                     # 스레드가 끝났을 때만 최종 떼기(살아있으면 그 스레드가 뗌 → 경쟁 방지)
            try:
                self.eng.release_all()
            except Exception:
                pass
        try:
            store.finish_run(self._run_id, 0, self._run_done, "stopped")  # 끄는 중이면 '중단'으로 마감
            self._run_id = None
        except Exception:
            pass
        try:
            store.save_set(self.set)      # 끌 때 자동 저장
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
