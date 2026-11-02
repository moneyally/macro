# -*- coding: utf-8 -*-
"""메인 창 — 여러 매크로 관리 + F12 실행/편집 토글 + 전역 설정.

단죄 매크로 기능(목록·기록·추가·편집·복사·삭제·실행주기·한영감지·키떼기·마우스복구)을
2026 톤(둥근 버튼·웜 팔레트)으로 재구성.
"""
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox

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

        self.statusbar = tk.Label(main, textvariable=self.status, bg=T.COLORS["bg"], fg=T.COLORS["accentDk"],
                                  font=T.font(10, "bold"), anchor="w")
        self.statusbar.pack(side="bottom", fill="x", padx=22, pady=(0, 10))

        self.main_body = tk.Frame(main, bg=T.COLORS["bg"])
        self.main_body.pack(side="top", fill="both", expand=True)

        self.pages = {}
        self._build_page_macros()
        self._build_page_global()
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
        W.label(b, "⏰ 매일 자동 실행 (HH:MM)").grid(row=3, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_sched, 10).grid(row=3, column=1, sticky="w")
        for v in (self.m_hot, self.m_loop, self.m_speed, self.m_chain, self.m_sched):
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

    def show_page(self, key):
        for fr in self.pages.values():
            fr.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        titles = {"macros": "📋  매크로", "global": "⚙  전역 설정",
                  "history": "📜  실행 기록", "help": "❓  도움말"}
        self.page_title.set(titles.get(key, ""))
        for k, nb in self._nav.items():
            nb.set_active(k == key)
        if key == "history":
            self._refresh_history()

    def _refresh_history(self):
        self.hist_lb.delete(0, "end")
        rows = store.recent_runs(200)
        if not rows:
            self.hist_lb.insert("end", "  (아직 실행 기록 없음)")
            return
        for name, loops, ts in rows:
            when = time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
            loop = "∞회" if loops == 0 else f"{loops}회"
            self.hist_lb.insert("end", f"  {when}    {name}    ·{loop}")

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
        self.lb_quiet_refresh()
        store.save_set(self.set)

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
        self.player.play(
            macro.actions, loops=macro.loops, speed=macro.speed,
            jitter=self.set.jitter_pct / 100.0, cycle=self.set.cycle_ms / 1000.0,
            ime_lock=self.set.ime_detect, release_all=self.set.release_on_stop,
            restore_mouse=self.set.restore_mouse,
            rand_min=self.set.rand_min_ms / 1000.0, rand_max=self.set.rand_max_ms / 1000.0)
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
        store.log_run(self._last_name, n)      # 실행 기록(SQLite)
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
        # ⏰ 매일 HH:MM 자동 실행 (분당 1번만 검사, 같은 분 중복 실행 방지)
        if self.mode != MODE_RUN or self.player.playing or self.recording:
            return
        now = time.localtime()
        stamp = time.strftime("%Y-%m-%d %H:%M", now)
        hm = time.strftime("%H:%M", now)
        for m in self.set.macros:
            if m.schedule and m.schedule == hm and m.actions:
                if self._sched_fired.get(m.name) != stamp:
                    self._sched_fired[m.name] = stamp
                    self._play(m)
                    break

    def _quit(self):
        self._closing = True
        # 콜백부터 끊어 파괴된 창을 건드리지 않게
        self.player.on_status = None
        self.player.on_done = None
        try:
            self.player.stop()
            t = self.player._thread
            if t and t.is_alive():
                t.join(timeout=2)         # 재생 스레드가 눌린 키 다 떼고 끝날 때까지 기다림
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
        try:
            self.eng.release_all()        # 혹시 남은 키/버튼 최종 떼기
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
