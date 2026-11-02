# -*- coding: utf-8 -*-
"""동작 편집 창 — 매크로 하나의 동작 목록을 보고/추가/수정/정렬.

상단: 동작 목록(Listbox)
하단: 동작 추가 패널 (종류 선택 → 값 입력 → 추가), 좌표 찍기(F8)
"""
import tkinter as tk
from tkinter import messagebox, ttk

from .. import model
from . import theme as T
from . import widgets as W

TYPES = [("click", "🖱 클릭"), ("type", "✎ 문구 입력"), ("hotkey", "🔑 단축키"),
         ("move", "➡ 이동"), ("wait", "⏱ 대기"), ("scroll", "🖲 스크롤"), ("image", "🖼 이미지 클릭")]
LABELS = {
    "click": ("좌표 x,y", "버튼 left/right/middle", "횟수 (,흔들기px)"),
    "type": ("문구 (타이핑할 글)", "초당 글자수(0=즉시)", "앞 대기(ms)"),
    "hotkey": ("조합 ctrl+c / alt+tab", "앞 대기(ms)", "—"),
    "move": ("좌표 x,y", "걸리는 시간(초,0=순간)", "앞 대기(ms)"),
    "wait": ("대기 밀리초(ms)", "—", "—"),
    "scroll": ("양(+위/-아래)", "앞 대기(ms)", "—"),
    "image": ("이미지 경로(.png)", "정확도 0~1", "버튼 left/right"),
}


class Editor(tk.Toplevel):
    def __init__(self, app, macro):
        super().__init__(app.root, bg=T.COLORS["bg"])
        self.app = app
        self.macro = macro
        self.title(f"동작 편집 — {macro.name}")
        self.geometry("560x600")
        self.configure(bg=T.COLORS["bg"])
        self.transient(app.root)

        tk.Label(self, text=f"✎  {macro.name}  동작 편집", bg=T.COLORS["bg"], fg=T.COLORS["ink"],
                 font=T.font(13, "bold")).pack(anchor="w", padx=18, pady=(14, 6))

        listcard = W.Card(self)
        listcard.pack(fill="both", expand=True, padx=14)
        self.lb = tk.Listbox(listcard.body, height=11, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                             selectbackground=T.COLORS["accentSoft"], selectforeground=T.COLORS["ink"],
                             relief="flat", highlightthickness=0, activestyle="none")
        self.lb.pack(fill="both", expand=True)
        self._refresh()

        row = tk.Frame(self, bg=T.COLORS["bg"])
        row.pack(fill="x", padx=14, pady=8)
        for txt, cmd, col, hov in [("▲ 위", lambda: self._move(-1), T.COLORS["slate"], T.COLORS["slateDk"]),
                                   ("▼ 아래", lambda: self._move(1), T.COLORS["slate"], T.COLORS["slateDk"]),
                                   ("🗑 삭제", self._del, T.COLORS["red"], T.COLORS["redDk"]),
                                   ("● 이 매크로에 녹화", self._record, T.COLORS["accent"], T.COLORS["accentDk"])]:
            W.RoundButton(row, txt, cmd, bg=col, hover=hov, width=120 if "녹화" in txt else 78,
                          height=34, radius=11, font=T.font(9, "bold")).pack(side="left", padx=3)

        add = W.Card(self, "➕ 동작 추가")
        add.pack(fill="x", padx=14, pady=(2, 10))
        b = add.body
        self.vtype = tk.StringVar(value=TYPES[0][1])
        self.tmap = {v: k for k, v in TYPES}
        cb = ttk.Combobox(b, textvariable=self.vtype, state="readonly", width=16, values=[v for _, v in TYPES])
        cb.grid(row=0, column=0, padx=2, pady=4, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._relabel())
        self.l1 = W.label(b, "좌표 x,y"); self.l1.grid(row=1, column=0, sticky="e", pady=2)
        self.v1 = tk.StringVar(); W.entry(b, self.v1, 24).grid(row=1, column=1, padx=4)
        self.l2 = W.label(b, "버튼"); self.l2.grid(row=2, column=0, sticky="e", pady=2)
        self.v2 = tk.StringVar(); W.entry(b, self.v2, 24).grid(row=2, column=1, padx=4)
        self.l3 = W.label(b, "횟수"); self.l3.grid(row=3, column=0, sticky="e", pady=2)
        self.v3 = tk.StringVar(); W.entry(b, self.v3, 24).grid(row=3, column=1, padx=4)
        W.RoundButton(b, "📍 좌표 찍기 (F8)", self._arm_pick, bg=T.COLORS["amber"], hover=T.COLORS["amberDk"],
                      width=130, height=32, radius=10, font=T.font(9, "bold")).grid(row=1, column=2, padx=6)
        W.RoundButton(b, "➕ 추가", self._add, bg=T.COLORS["green"], hover=T.COLORS["greenDk"],
                      width=130, height=32, radius=10, font=T.font(9, "bold")).grid(row=3, column=2, padx=6)
        self._relabel()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _refresh(self):
        self.lb.delete(0, "end")
        for a in self.macro.actions:
            self.lb.insert("end", "  " + model.action_label(a))

    def _sel(self):
        s = self.lb.curselection()
        return s[0] if s else None

    def _move(self, d):
        i = self._sel()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(self.macro.actions):
            self.macro.actions[i], self.macro.actions[j] = self.macro.actions[j], self.macro.actions[i]
            self._refresh()
            self.lb.selection_set(j)

    def _del(self):
        i = self._sel()
        if i is not None:
            del self.macro.actions[i]
            self._refresh()

    def _record(self):
        self.app.record_into(self.macro, on_done=self._refresh)

    def _relabel(self):
        t = self.tmap[self.vtype.get()]
        a, b, c = LABELS[t]
        self.l1.config(text=a); self.l2.config(text=b); self.l3.config(text=c)

    def _arm_pick(self):
        self.app.arm_pick(self._set_coord)
        self.app.toast("📍 원하는 위치에서 F8")

    def _set_coord(self, x, y):
        self.v1.set(f"{x},{y}")

    def _add(self):
        t = self.tmap[self.vtype.get()]
        try:
            a = self._make(t)
        except Exception as ex:
            messagebox.showwarning("입력", f"값 확인: {ex}")
            return
        self.macro.actions.append(a)
        self._refresh()
        self.v1.set(""); self.v2.set(""); self.v3.set("")

    def _make(self, t):
        v1, v2, v3 = self.v1.get().strip(), self.v2.get().strip(), self.v3.get().strip()
        pre = (float(v3 or 0) / 1000.0) if t in ("type", "move") else \
              (float(v2 or 0) / 1000.0) if t in ("hotkey", "scroll") else 0.0
        if t == "click":
            xy = v1.split(",")
            a = {"type": "click", "delay": 0.0, "x": int(xy[0]), "y": int(xy[1]),
                 "button": v2 or "left", "count": int((v3.split(",")[0] or "1"))}
            if "," in v3:
                a["jitter"] = int(v3.split(",")[1])
            return a
        if t == "type":
            return {"type": "type", "delay": pre, "text": self.v1.get(), "cps": int(float(v2 or 0))}
        if t == "hotkey":
            return {"type": "hotkey", "delay": pre, "combo": v1}
        if t == "move":
            xy = v1.split(",")
            return {"type": "move", "delay": pre, "x": int(xy[0]), "y": int(xy[1]), "dur": float(v2 or 0)}
        if t == "wait":
            return {"type": "wait", "delay": float(v1) / 1000.0}
        if t == "scroll":
            return {"type": "scroll", "delay": pre, "dx": 0, "dy": int(float(v1))}
        if t == "image":
            return {"type": "image", "delay": 0.0, "path": v1, "confidence": float(v2 or 0.8), "button": v3 or "left"}
        raise ValueError("종류")

    def _close(self):
        self.app.disarm_pick()
        self.app.refresh_macros()
        self.destroy()
