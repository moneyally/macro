# -*- coding: utf-8 -*-
"""📜 실행 기록 창 — 언제 어떤 매크로를 몇 번 돌렸는지 (SQLite 에 쌓인 것)."""
import time
import tkinter as tk

from .. import store
from . import theme as T
from . import widgets as W


class History(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root, bg=T.COLORS["bg"])
        self.app = app
        self.title("📜 실행 기록")
        self.geometry("460x520")
        self.transient(app.root)

        tk.Label(self, text="📜  실행 기록", bg=T.COLORS["bg"], fg=T.COLORS["ink"],
                 font=T.font(13, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="최근 실행 순서대로 (이름 · 반복 · 시각)",
                 bg=T.COLORS["bg"], fg=T.COLORS["sub"], font=T.font(9)).pack(anchor="w", padx=16)

        card = W.Card(self)
        card.pack(fill="both", expand=True, padx=14, pady=(8, 0))
        self.lb = tk.Listbox(card.body, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                             selectbackground=T.COLORS["accentSoft"], selectforeground=T.COLORS["ink"],
                             relief="flat", highlightthickness=0, activestyle="none")
        self.lb.pack(fill="both", expand=True)

        row = tk.Frame(self, bg=T.COLORS["bg"])
        row.pack(fill="x", padx=14, pady=12)
        W.RoundButton(row, "🔄 새로고침", self._refresh, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=110, height=36).pack(side="left", padx=4)
        W.RoundButton(row, "🗑 기록 비우기", self._clear, bg=T.COLORS["red"], hover=T.COLORS["redDk"],
                      width=120, height=36).pack(side="left", padx=4)
        W.RoundButton(row, "닫기", self.destroy, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=72, height=36).pack(side="right", padx=4)
        self._refresh()

    def _refresh(self):
        self.lb.delete(0, "end")
        rows = store.recent_runs(200)
        if not rows:
            self.lb.insert("end", "  (아직 기록 없음)")
            return
        for name, loops, ts in rows:
            when = time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
            loop = "∞회" if loops == 0 else f"{loops}회"
            self.lb.insert("end", f"  {when}   {name}   ·{loop}")

    def _clear(self):
        store.clear_runs()
        self._refresh()
