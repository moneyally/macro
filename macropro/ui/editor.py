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
from .broadcast import Broadcast

TYPES = [("click", "🖱 클릭"), ("type", "✎ 문구 입력"), ("paste", "📋 붙여넣기(빠름)"),
         ("hotkey", "🔑 단축키"), ("move", "➡ 이동"), ("wait", "⏱ 대기"),
         ("scroll", "🖲 스크롤"), ("image", "🖼 이미지 보이면 클릭"),
         ("wait_image", "⏳ 이미지 뜰 때까지"), ("if_image", "🔀 이미지 조건"),
         ("ifcond", "🧠 조건(값·창·픽셀)"), ("wclick", "🪟 창 기준 클릭"),
         ("increment", "🔢 변수 +1"), ("window", "🪟 창 조절")]
# 고급 모드에서만 보이는 동작 (쉬움 모드에선 숨김)
ADV_TYPES = {"wait_image", "if_image", "ifcond", "wclick", "increment"}
LABELS = {
    "click": ("좌표 x,y", "버튼 left/right/middle", "횟수 (,흔들기px)"),
    "type": ("문구 (타이핑할 글, {번호}·{날짜}·변수 가능)", "초당 글자수(0=즉시)", "앞 대기(ms)"),
    "paste": ("붙여넣을 문구 ({번호}·변수 가능)", "앞 대기(ms)", "—"),
    "hotkey": ("조합 ctrl+c / alt+tab", "앞 대기(ms)", "—"),
    "move": ("좌표 x,y", "걸리는 시간(초,0=순간)", "앞 대기(ms)"),
    "wait": ("대기 밀리초(ms)", "—", "—"),
    "scroll": ("양(+위/-아래)", "앞 대기(ms)", "—"),
    "image": ("이미지 경로(.png)", "정확도 0~1", "버튼 left/right"),
    "wait_image": ("이미지 경로(.png)", "정확도 0~1", "최대 대기(초)"),
    "if_image": ("이미지 경로(.png)", "있을때 found / 없을때 notfound", "조건 안 맞으면 건너뛸 동작 수"),
    "ifcond": ("종류 window/active_title/clipboard/pixel/image", "비교 exists/contains/near/equals", "기준값 (pixel 은 #RRGGBB@x,y)"),
    "wclick": ("창 제목(일부)", "가로 비율 0~1 (예 0.5)", "세로 비율 0~1"),
    "increment": ("변수 이름 (예 번호)", "증가값 (기본 1)", "—"),
    "window": ("창 제목(일부만)", "activate/min/max/close/move/resize", "move=x,y  resize=w,h"),
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
        row.pack(fill="x", padx=14, pady=(8, 2))
        for txt, cmd, col, hov in [("▲ 위", lambda: self._move(-1), T.COLORS["slate"], T.COLORS["slateDk"]),
                                   ("▼ 아래", lambda: self._move(1), T.COLORS["slate"], T.COLORS["slateDk"]),
                                   ("🗑 삭제", self._del, T.COLORS["red"], T.COLORS["redDk"]),
                                   ("● 이 매크로에 녹화", self._record, T.COLORS["accent"], T.COLORS["accentDk"])]:
            W.RoundButton(row, txt, cmd, bg=col, hover=hov, width=120 if "녹화" in txt else 78,
                          height=34, radius=11, font=T.font(9, "bold")).pack(side="left", padx=3)

        row2 = tk.Frame(self, bg=T.COLORS["bg"])
        row2.pack(fill="x", padx=14, pady=(0, 6))
        self._mcap = False
        self._mcbtn = W.RoundButton(row2, "🎯 연속 찍기", self._toggle_multiclick, bg=T.COLORS["amber"],
                                    hover=T.COLORS["amberDk"], width=120, height=34, radius=11, font=T.font(9, "bold"))
        self._mcbtn.pack(side="left", padx=3)
        W.RoundButton(row2, "📡 멀티 타겟 (여러 방)", self._open_broadcast, bg=T.COLORS["green"],
                      hover=T.COLORS["greenDk"], width=170, height=34, radius=11, font=T.font(9, "bold")).pack(side="left", padx=3)

        add = W.Card(self, "➕ 동작 추가")
        add.pack(fill="x", padx=14, pady=(2, 10))
        b = add.body
        self.vtype = tk.StringVar(value=TYPES[0][1])
        adv = getattr(app.set, "advanced", False)
        types = TYPES if adv else [t for t in TYPES if t[0] not in ADV_TYPES]
        self.vtype.set(types[0][1])
        self.tmap = {v: k for k, v in types}
        cb = ttk.Combobox(b, textvariable=self.vtype, state="readonly", width=16, values=[v for _, v in types])
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

    def _toggle_multiclick(self):
        if self._mcap:
            self._mcap = False
            self.app.disarm_pick()
            self._mcbtn.set_text("🎯 연속 찍기")
        else:
            self._mcap = True
            self.app.arm_pick(self._append_click, multi=True)
            self._mcbtn.set_text("■ 찍기 멈춤 (F8)")
            self.app.toast("🎯 F8 누를 때마다 그 자리 클릭 동작 추가")

    def _append_click(self, x, y):
        self.macro.actions.append({"type": "click", "delay": 0.0, "x": x, "y": y, "button": "left", "count": 1})
        self._refresh()

    def _open_broadcast(self):
        Broadcast(self.app, self.macro, on_added=self._refresh)

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
              (float(v2 or 0) / 1000.0) if t in ("hotkey", "scroll", "paste") else 0.0
        if t == "increment":
            return {"type": "increment", "delay": 0.0, "name": v1, "step": int(float(v2 or 1))}
        if t == "wclick":
            return {"type": "click", "delay": 0.0, "coordinate_mode": "window_relative",
                    "window": v1, "x": float(v2 or 0.5), "y": float(v3 or 0.5),
                    "button": "left", "count": 1}
        if t == "ifcond":
            src = (v1 or "window").lower()
            cond = {"source": src, "operator": (v2 or "exists"), "value": v3}
            if src == "pixel" and "@" in v3:
                val, xy = v3.split("@", 1)
                cond["value"] = val.strip()
                if "," in xy:
                    xx, yy = (xy.split(",") + ["0", "0"])[:2]
                    cond["x"], cond["y"] = int(xx), int(yy)
            return {"type": "ifcond", "delay": 0.0, "condition": cond, "when": "true", "skip": 1}
        if t == "paste":
            return {"type": "paste", "delay": pre, "text": self.v1.get()}
        if t == "wait_image":
            return {"type": "wait_image", "delay": 0.0, "path": v1,
                    "confidence": float(v2 or 0.8), "timeout": float(v3 or 10)}
        if t == "if_image":
            when = "notfound" if v2.lower().startswith("not") else "found"
            return {"type": "if_image", "delay": 0.0, "path": v1, "when": when,
                    "skip": int(float(v3 or 1))}
        if t == "window":
            op = (v2 or "activate").lower()
            d = {"type": "window", "delay": 0.0, "op": op, "title": v1}
            if "," in v3:
                aa, bb = (v3.split(",") + ["", ""])[:2]
                if op == "move":
                    d["x"], d["y"] = int(aa), int(bb)
                elif op == "resize":
                    d["w"], d["h"] = int(aa), int(bb)
            return d
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
        if getattr(self.app, "_rec_done", None) == self._refresh:
            self.app._rec_done = None      # 이 창이 건 녹화 콜백 떼기 (닫힌 뒤 호출되면 터짐)
        self.app.refresh_macros()
        self.destroy()
