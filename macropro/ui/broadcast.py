# -*- coding: utf-8 -*-
"""📡 멀티 타겟(여러 방) 빌더 — 방 위치들 + 공통 문구 → broadcast 동작 하나로.

실행하면 등록한 모든 방에 차례로 [클릭 → 문구 입력 → 엔터] 를 보낸다.
"""
import tkinter as tk
from tkinter import messagebox

from . import theme as T
from . import widgets as W


class Broadcast(tk.Toplevel):
    def __init__(self, app, macro, on_added=None):
        super().__init__(app.root, bg=T.COLORS["bg"])
        self.app = app
        self.macro = macro
        self.on_added = on_added
        self.targets = []          # [[x,y], ...]
        self.capturing = False
        self.title("📡 멀티 타겟 (여러 방)")
        self.geometry("480x600")
        self.transient(app.root)

        tk.Label(self, text="📡  여러 방에 한 번에 보내기", bg=T.COLORS["bg"], fg=T.COLORS["ink"],
                 font=T.font(13, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="방 위치들을 찍고 공통 문구를 쓰면, 실행 때 모든 방에 클릭→입력→엔터.",
                 bg=T.COLORS["bg"], fg=T.COLORS["sub"], font=T.font(9)).pack(anchor="w", padx=16)

        # 타겟 목록
        tc = W.Card(self, "① 방 위치 (순서대로)")
        tc.pack(fill="both", expand=True, padx=14, pady=(8, 0))
        self.lb = tk.Listbox(tc.body, height=6, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                             selectbackground=T.COLORS["accentSoft"], relief="flat", highlightthickness=0,
                             activestyle="none")
        self.lb.pack(fill="both", expand=True)
        row = tk.Frame(tc.body, bg=T.COLORS["surface"])
        row.pack(fill="x", pady=(6, 0))
        self.capbtn = W.RoundButton(row, "📍 방 위치 찍기 시작 (F8)", self._toggle_capture,
                                    bg=T.COLORS["amber"], hover=T.COLORS["amberDk"], width=180, height=32,
                                    radius=10, font=T.font(9, "bold"))
        self.capbtn.pack(side="left", padx=2)
        W.RoundButton(row, "🗑 삭제", self._del, bg=T.COLORS["red"], hover=T.COLORS["redDk"],
                      width=72, height=32, radius=10, font=T.font(9, "bold")).pack(side="left", padx=2)
        W.RoundButton(row, "전체", self._clear, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=56, height=32, radius=10, font=T.font(9, "bold")).pack(side="left", padx=2)

        # 창 제목으로 방 추가 (좌표 대신 — 창 겹쳐 있어도 안정)
        wrow = tk.Frame(tc.body, bg=T.COLORS["surface"])
        wrow.pack(fill="x", pady=(6, 0))
        W.label(wrow, "창 제목으로:").pack(side="left", padx=(0, 4))
        self.wtitle = tk.StringVar()
        W.entry(wrow, self.wtitle, 18).pack(side="left")
        W.RoundButton(wrow, "🪟 창 추가", self._add_win, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=86, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=4)

        # 📚 저장 대상(🔧 변수·대상에서 만든 것)에서 바로 넣기
        saved = getattr(self.app.set, "targets", None) or []
        if saved:
            from tkinter import ttk
            srow = tk.Frame(tc.body, bg=T.COLORS["surface"])
            srow.pack(fill="x", pady=(6, 0))
            W.label(srow, "저장 대상:").pack(side="left", padx=(0, 4))
            self._saved = saved
            self.sv = tk.StringVar()
            ttk.Combobox(srow, textvariable=self.sv, state="readonly", width=16,
                         values=[t.get("name", "") for t in saved]).pack(side="left")
            W.RoundButton(srow, "➕ 넣기", self._add_saved, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                          width=68, height=30, radius=10, font=T.font(9, "bold")).pack(side="left", padx=4)

        # 문구
        mcard = W.Card(self, "② 공통 문구")
        mcard.pack(fill="x", padx=14, pady=(10, 0))
        self.text = tk.Text(mcard.body, height=4, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                            relief="flat", highlightthickness=1, highlightbackground=T.COLORS["line"],
                            highlightcolor=T.COLORS["accent"], wrap="word")
        self.text.pack(fill="x")

        # 옵션
        oc = W.Card(self, "③ 옵션")
        oc.pack(fill="x", padx=14, pady=(10, 0))
        b = oc.body
        self.enter = tk.BooleanVar(value=True)
        self.cps = tk.StringVar(value="0")
        self.gap = tk.StringVar(value="300")
        self.focus_var = tk.StringVar(value="150")   # focus 는 tkinter 예약 메서드라 _var 로
        tk.Checkbutton(b, text="입력 후 엔터(전송)", variable=self.enter, bg=T.COLORS["surface"],
                       fg=T.COLORS["sub"], activebackground=T.COLORS["surface"], selectcolor="white",
                       font=T.font(9)).grid(row=0, column=0, columnspan=2, sticky="w")
        W.label(b, "타이핑 속도(자/초,0=즉시)").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        W.entry(b, self.cps, 7).grid(row=1, column=1, sticky="w")
        W.label(b, "방 사이 간격(ms)").grid(row=2, column=0, sticky="e", padx=4, pady=2)
        W.entry(b, self.gap, 7).grid(row=2, column=1, sticky="w")
        W.label(b, "클릭 후 입력 전 대기(ms)").grid(row=3, column=0, sticky="e", padx=4, pady=2)
        W.entry(b, self.focus_var, 7).grid(row=3, column=1, sticky="w")

        W.RoundButton(self, "➕ 이 매크로에 멀티타겟 추가", self._add, bg=T.COLORS["green"],
                      hover=T.COLORS["greenDk"], width=240, height=40, radius=12).pack(pady=12)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _toggle_capture(self):
        if self.capturing:
            self.capturing = False
            self.app.disarm_pick()
            self.capbtn.set_text("📍 방 위치 찍기 시작 (F8)")
        else:
            self.capturing = True
            self.app.arm_pick(self._add_target, multi=True)
            self.capbtn.set_text("■ 찍기 멈춤  (F8로 추가)")

    def _add_target(self, x, y):
        self.targets.append([x, y])
        self._refresh()

    def _add_win(self):
        t = self.wtitle.get().strip()
        if not t:
            return
        self.targets.append({"win": t})
        self.wtitle.set("")
        self._refresh()

    def _add_saved(self):
        name = self.sv.get().strip()
        for t in getattr(self, "_saved", []):
            if t.get("name") == name:
                if t.get("kind") == "window":
                    self.targets.append({"win": t.get("title", "")})
                else:
                    self.targets.append([int(t.get("x", 0)), int(t.get("y", 0))])
                self._refresh()
                return

    def _del(self):
        s = self.lb.curselection()
        if s:
            del self.targets[s[0]]
            self._refresh()

    def _clear(self):
        self.targets = []
        self._refresh()

    def _tlabel(self, i, t):
        if isinstance(t, dict) and t.get("win"):
            return f"  방 {i}  🪟 \"{t['win']}\""
        try:
            x, y = t
            return f"  방 {i}  ({x}, {y})"
        except Exception:
            return f"  방 {i}  ?"

    def _refresh(self):
        self.lb.delete(0, "end")
        for i, t in enumerate(self.targets, 1):
            self.lb.insert("end", self._tlabel(i, t))

    def _norm_targets(self):
        out = []
        for t in self.targets:
            if isinstance(t, dict) and t.get("win"):
                out.append({"win": t["win"]})
            else:
                out.append([int(t[0]), int(t[1])])
        return out

    def _add(self):
        if not self.targets:
            messagebox.showinfo("멀티 타겟", "방 위치를 먼저 찍거나(📍 F8) 창 제목으로 추가해 주세요.")
            return
        txt = self.text.get("1.0", "end").rstrip("\n")
        try:
            action = {"type": "broadcast", "delay": 0.0, "targets": self._norm_targets(),
                      "text": txt, "cps": int(float(self.cps.get() or 0)),
                      "gap_ms": int(float(self.gap.get() or 300)),
                      "focus_ms": int(float(self.focus_var.get() or 150)), "enter": self.enter.get()}
        except ValueError:
            messagebox.showwarning("옵션", "속도·간격은 숫자로.")
            return
        self.macro.actions.append(action)
        if self.on_added:
            self.on_added()
        self._close()

    def _close(self):
        self.app.disarm_pick()
        self.destroy()
