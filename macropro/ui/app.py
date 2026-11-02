# -*- coding: utf-8 -*-
"""메인 창 — 여러 매크로 관리 + F12 실행/편집 토글 + 전역 설정.

단죄 매크로 기능(목록·기록·추가·편집·복사·삭제·실행주기·한영감지·키떼기·마우스복구)을
2026 톤(둥근 버튼·웜 팔레트)으로 재구성.
"""
import tkinter as tk
from tkinter import filedialog, messagebox

from pynput import keyboard

from .. import keys as K
from ..engine import Engine
from ..model import Macro, MacroSet
from ..player import Player
from ..recorder import STOP_KEYS, Recorder
from . import theme as T
from . import widgets as W
from .editor import Editor

MODE_EDIT, MODE_RUN = "edit", "run"
CTRL_KEYS = {keyboard.Key.f8, keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f12}


class App:
    def __init__(self, root):
        self.root = root
        self.set = MacroSet()
        self.set.add(Macro(name="Macro 1"))
        self.eng = Engine()
        self.player = Player(self.eng)
        self.player.on_status = lambda t: self.root.after(0, self.toast, t)
        self.player.on_done = lambda n: self.root.after(0, self._on_play_done, n)
        self.rec = None
        self.recording = False
        self._rec_target = None
        self._rec_done = None
        self.mode = MODE_EDIT
        self.pick_cb = None
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

    # ── 레이아웃 ──────────────────────────────────────────
    def _build(self):
        r = self.root
        r.title("⚡ 매크로 PRO")
        r.geometry("600x680")
        r.minsize(560, 640)

        head = tk.Frame(r, bg=T.COLORS["bg"])
        head.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(head, text="⚡ 매크로 PRO", bg=T.COLORS["bg"], fg=T.COLORS["ink"],
                 font=T.font(17, "bold")).pack(side="left")
        self.pill = W.Pill(head, "편집 모드", T.COLORS["slate"], width=150, height=30)
        self.pill.pack(side="right")
        tk.Label(r, textvariable=self.mousev, bg=T.COLORS["bg"], fg=T.COLORS["sub"],
                 font=T.font(9)).pack(anchor="e", padx=20)

        # 매크로 목록
        listcard = W.Card(r, "📋 매크로 목록  (F12 = 실행↔편집 전환)")
        listcard.pack(fill="x", padx=14, pady=(4, 0))
        inner = tk.Frame(listcard.body, bg=T.COLORS["surface"])
        inner.pack(fill="both", expand=True)
        self.lb = tk.Listbox(inner, height=6, font=T.font(11), bg="white", fg=T.COLORS["ink"],
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

        # 선택 매크로 설정
        mc = W.Card(r, "🎛 선택 매크로")
        mc.pack(fill="x", padx=14, pady=(10, 0))
        b = mc.body
        self.m_hot = tk.StringVar()
        self.m_loop = tk.StringVar(value="1")
        self.m_speed = tk.StringVar(value="1.0")
        W.label(b, "실행 단축키 (예 f1)").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_hot, 8).grid(row=0, column=1, sticky="w")
        W.label(b, "반복(0=무한)").grid(row=0, column=2, sticky="e", padx=4)
        W.entry(b, self.m_loop, 6).grid(row=0, column=3, sticky="w")
        W.label(b, "배속").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.m_speed, 6).grid(row=1, column=1, sticky="w")
        for v in (self.m_hot, self.m_loop, self.m_speed):
            v.trace_add("write", lambda *a: self._save_sel())
        W.RoundButton(b, "▶ 테스트 실행", self.test_run, bg=T.COLORS["green"], hover=T.COLORS["greenDk"],
                      width=120, height=32, radius=10, font=T.font(9, "bold")).grid(row=1, column=2, columnspan=2, padx=4)

        # 전역 설정
        gc = W.Card(r, "⚙ 전역 설정")
        gc.pack(fill="x", padx=14, pady=(10, 0))
        b = gc.body
        self.cycle = tk.StringVar(value=str(self.set.cycle_ms))
        self.jit = tk.StringVar(value=str(self.set.jitter_pct))
        W.label(b, "이벤트 실행 주기(ms)").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        W.entry(b, self.cycle, 6).grid(row=0, column=1, sticky="w")
        W.label(b, "타이밍 랜덤 ±%").grid(row=0, column=2, sticky="e", padx=4)
        W.entry(b, self.jit, 6).grid(row=0, column=3, sticky="w")
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
                           font=T.font(9), command=self._save_global).grid(row=1 + i, column=0, columnspan=4, sticky="w", pady=1)
        for v in (self.cycle, self.jit):
            v.trace_add("write", lambda *a: self._save_global())

        # 파일 + 종료
        fc = tk.Frame(r, bg=T.COLORS["bg"])
        fc.pack(fill="x", padx=14, pady=12)
        W.RoundButton(fc, "💾 저장", self.save_file, bg=T.COLORS["accent"], hover=T.COLORS["accentDk"],
                      width=100, height=38).pack(side="left", padx=4)
        W.RoundButton(fc, "📂 불러오기", self.load_file, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=110, height=38).pack(side="left", padx=4)
        W.RoundButton(fc, "■ 정지", self.stop_play, bg=T.COLORS["red"], hover=T.COLORS["redDk"],
                      width=90, height=38).pack(side="left", padx=4)
        W.RoundButton(fc, "종료", self._quit, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=80, height=38).pack(side="right", padx=4)

        self.statusbar = tk.Label(r, textvariable=self.status, bg=T.COLORS["bg"], fg=T.COLORS["accentDk"],
                                  font=T.font(10, "bold"), anchor="w")
        self.statusbar.pack(fill="x", padx=20, pady=(0, 8))

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
        self.lb_quiet_refresh()

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
        self.set.ime_detect = self.c_ime.get()
        self.set.release_on_stop = self.c_rel.get()
        self.set.restore_mouse = self.c_res.get()
        self.set.record_moves = self.c_mov.get()

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
            self._rec_done()
        self.refresh_macros()

    # ── 재생 ──────────────────────────────────────────────
    def test_run(self):
        m = self._sel_macro()
        if m:
            self._play(m)

    def _play(self, macro):
        if self.recording or self.player.playing or not macro.actions:
            if not macro.actions:
                self.toast("동작이 없어요 (기록/편집)")
            return
        self._save_global()
        self.player.play(
            macro.actions, loops=macro.loops, speed=macro.speed,
            jitter=self.set.jitter_pct / 100.0, cycle=self.set.cycle_ms / 1000.0,
            ime_lock=self.set.ime_detect, release_all=self.set.release_on_stop,
            restore_mouse=self.set.restore_mouse)
        self.toast(f"▶ '{macro.name}' 실행")

    def stop_play(self):
        self.player.stop()

    def _on_play_done(self, n):
        self.toast(f"실행 끝 ({n}회)")

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
        if key == keyboard.Key.f8 and self.pick_cb:
            x, y = self.eng.get_pos()
            cb = self.pick_cb
            self.pick_cb = None
            self.root.after(0, lambda: cb(int(x), int(y)))
            return
        if key == keyboard.Key.f12:
            self.root.after(0, self.toggle_mode)
            return
        if key == keyboard.Key.f9:
            self.root.after(0, self.toggle_record)
            return
        if key == keyboard.Key.f10:
            self.root.after(0, self.stop_play)
            return
        if self.mode == MODE_RUN and not self.player.playing:
            name = K.key_name(key)
            for m in self.set.macros:
                if m.hotkey and m.hotkey == name:
                    self.root.after(0, lambda mm=m: self._play(mm))
                    break

    # 편집창이 좌표 찍기 요청
    def arm_pick(self, cb):
        self.pick_cb = cb

    def disarm_pick(self):
        self.pick_cb = None

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
        try:
            x, y = self.eng.get_pos()
            self.mousev.set(f"🖱 ({int(x)}, {int(y)})")
        except Exception:
            pass
        self.root.after(90, self._tick)

    def _quit(self):
        try:
            self.player.stop()
            if self.recording and self.rec:
                self.rec.stop()
            self._hk.stop()
        except Exception:
            pass
        self.root.destroy()
