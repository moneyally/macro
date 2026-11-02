# -*- coding: utf-8 -*-
"""둥근(라운드) 커스텀 위젯 — Canvas 로 진짜 둥근 모서리 구현.

tkinter 기본 버튼은 각져서, 2026 톤에 맞게 Canvas 로 둥근 버튼/칩/카드를 그린다.
"""
import tkinter as tk

from . import theme as T


def round_rect_points(x1, y1, x2, y2, r):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class RoundButton(tk.Canvas):
    """둥근 버튼 (호버 시 색 진해짐)."""
    def __init__(self, parent, text, command=None, bg=None, fg="white",
                 hover=None, width=130, height=40, radius=T.RADIUS, font=None,
                 kr=True, bold=True):
        self.bg_parent = parent["bg"] if "bg" in parent.keys() else T.COLORS["bg"]
        super().__init__(parent, width=width, height=height, bg=self.bg_parent,
                         highlightthickness=0, bd=0)
        self.command = command
        self._bg = bg or T.COLORS["accent"]
        self._hover = hover or T.COLORS["accentDk"]
        self._fg = fg
        self._w, self._h, self._r = width, height, radius
        self._font = font or T.font(10, "bold" if bold else "normal", kr)
        self._text = text
        self._draw(self._bg)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._draw(self._hover))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.configure(cursor="hand2")

    def _draw(self, color):
        self.delete("all")
        pts = round_rect_points(2, 2, self._w - 2, self._h - 2, self._r)
        self.create_polygon(pts, smooth=True, splinesteps=36, fill=color, outline=color)
        self.create_text(self._w / 2, self._h / 2, text=self._text, fill=self._fg, font=self._font)

    def _click(self, _e):
        if self.command:
            self.command()

    def set_text(self, t):
        self._text = t
        self._draw(self._bg)

    def set_color(self, bg, hover=None):
        self._bg = bg
        self._hover = hover or bg
        self._draw(self._bg)


class Card(tk.Frame):
    """둥근 느낌의 카드 (경계선 + 패딩). tk 는 진짜 라운드 프레임이 없어 미세 라운드로 흉내."""
    def __init__(self, parent, title=None, pad=14):
        super().__init__(parent, bg=T.COLORS["bg"])
        self._canvas = tk.Canvas(self, bg=T.COLORS["bg"], highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self._canvas, bg=T.COLORS["surface"])
        self._win = self._canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self._canvas.bind("<Configure>", self._resize)
        self.inner.bind("<Configure>", self._resize)
        self._pad = pad
        self._title = title
        if title:
            tk.Label(self.inner, text=title, bg=T.COLORS["surface"], fg=T.COLORS["ink"],
                     font=T.font(11, "bold")).pack(anchor="w", padx=pad, pady=(pad, 4))
        self.body = tk.Frame(self.inner, bg=T.COLORS["surface"])
        self.body.pack(fill="both", expand=True, padx=pad, pady=(0, pad))

    def _resize(self, _e=None):
        w = self._canvas.winfo_width()
        self.inner.configure(width=w)
        self._canvas.itemconfig(self._win, width=w)
        self._canvas.configure(height=self.inner.winfo_reqheight())
        self._canvas.delete("bgpanel")
        h = self.inner.winfo_reqheight()
        pts = round_rect_points(1, 1, w - 1, h - 1, 16)
        self._canvas.create_polygon(pts, smooth=True, splinesteps=36,
                                    fill=T.COLORS["surface"], outline=T.COLORS["line"], tags="bgpanel")
        self._canvas.tag_lower("bgpanel")


class Pill(tk.Canvas):
    """상태 알약(둥근 배지)."""
    def __init__(self, parent, text="", bg=None, fg="white", width=180, height=30):
        pbg = parent["bg"] if "bg" in parent.keys() else T.COLORS["bg"]
        super().__init__(parent, width=width, height=height, bg=pbg, highlightthickness=0, bd=0)
        self._w, self._h = width, height
        self._fg = fg
        self.set(text, bg or T.COLORS["green"])

    def set(self, text, bg):
        self.delete("all")
        pts = round_rect_points(2, 2, self._w - 2, self._h - 2, self._h / 2)
        self.create_polygon(pts, smooth=True, splinesteps=24, fill=bg, outline=bg)
        self.create_text(self._w / 2, self._h / 2, text=text, fill=self._fg, font=T.font(10, "bold"))


def entry(parent, textvar, width=10):
    """둥근 느낌의 입력칸 (얇은 경계)."""
    e = tk.Entry(parent, textvariable=textvar, width=width, relief="flat",
                 bg=T.COLORS["surface2"], fg=T.COLORS["ink"], insertbackground=T.COLORS["ink"],
                 highlightthickness=1, highlightbackground=T.COLORS["line"],
                 highlightcolor=T.COLORS["accent"], font=T.font(10))
    return e


def label(parent, text, bg=None, fg=None, size=10, weight="normal"):
    return tk.Label(parent, text=text, bg=bg or T.COLORS["surface"],
                    fg=fg or T.COLORS["ink"], font=T.font(size, weight))
