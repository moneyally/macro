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
        self._cw, self._h, self._r = width, height, radius   # _w 는 tkinter 예약(위젯 이름)이라 _cw 사용
        self._font = font or T.font(10, "bold" if bold else "normal", kr)
        self._text = text
        self._draw(self._bg)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._draw(self._hover))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.configure(cursor="hand2")

    def _draw(self, color):
        self.delete("all")
        pts = round_rect_points(2, 2, self._cw - 2, self._h - 2, self._r)
        self.create_polygon(pts, smooth=True, splinesteps=36, fill=color, outline=color)
        self.create_text(self._cw / 2, self._h / 2, text=self._text, fill=self._fg, font=self._font)

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
    """깔끔한 카드 — 표면색 + 얇은 경계선 + 패딩 (Configure 재귀 없음, 안전)."""
    def __init__(self, parent, title=None, pad=14):
        super().__init__(parent, bg=T.COLORS["surface"],
                         highlightbackground=T.COLORS["line"], highlightcolor=T.COLORS["line"],
                         highlightthickness=1, bd=0)
        if title:
            tk.Label(self, text=title, bg=T.COLORS["surface"], fg=T.COLORS["ink"],
                     font=T.font(11, "bold")).pack(anchor="w", padx=pad, pady=(pad, 4))
        self.body = tk.Frame(self, bg=T.COLORS["surface"])
        self.body.pack(fill="both", expand=True, padx=pad, pady=(0, pad))


class Pill(tk.Canvas):
    """상태 알약(둥근 배지)."""
    def __init__(self, parent, text="", bg=None, fg="white", width=180, height=30):
        pbg = parent["bg"] if "bg" in parent.keys() else T.COLORS["bg"]
        super().__init__(parent, width=width, height=height, bg=pbg, highlightthickness=0, bd=0)
        self._cw, self._h = width, height
        self._fg = fg
        self.set(text, bg or T.COLORS["green"])

    def set(self, text, bg):
        self.delete("all")
        pts = round_rect_points(2, 2, self._cw - 2, self._h - 2, self._h / 2)
        self.create_polygon(pts, smooth=True, splinesteps=24, fill=bg, outline=bg)
        self.create_text(self._cw / 2, self._h / 2, text=text, fill=self._fg, font=T.font(10, "bold"))


class NavButton(tk.Frame):
    """사이드바 메뉴 항목 — 왼쪽 정렬 아이콘+글자, 호버·활성 표시(Codex식)."""
    def __init__(self, parent, text, command):
        self._idle = T.COLORS["side"]
        self._hoverbg = T.COLORS["sideHover"]
        self._activebg = T.COLORS["accent"]
        super().__init__(parent, bg=self._idle, cursor="hand2")
        self.command = command
        self._on = False
        self.lbl = tk.Label(self, text=text, bg=self._idle, fg=T.COLORS["sideInk"],
                            font=T.font(11, "bold"), anchor="w", padx=14, pady=10)
        self.lbl.pack(fill="x")
        for w in (self, self.lbl):
            w.bind("<Button-1>", lambda e: self.command() if self.command else None)
            w.bind("<Enter>", lambda e: self._paint(hover=True))
            w.bind("<Leave>", lambda e: self._paint(hover=False))

    def _paint(self, hover=False):
        if self._on:
            bg, fg = self._activebg, "white"
        elif hover:
            bg, fg = self._hoverbg, "white"
        else:
            bg, fg = self._idle, T.COLORS["sideInk"]
        self.configure(bg=bg)
        self.lbl.configure(bg=bg, fg=fg)

    def set_active(self, on):
        self._on = on
        self._paint()


class MacroRow(tk.Frame):
    """사이드바 매크로 줄 — 이름 + 작은 설명, 선택·호버 표시(밝은 목록형)."""
    def __init__(self, parent, command):
        super().__init__(parent, bg=T.COLORS["panel"], cursor="hand2")
        self.command = command
        self._on = False
        self.t1 = tk.Label(self, bg=T.COLORS["panel"], fg=T.COLORS["ink"],
                           font=T.font(10, "bold"), anchor="w")
        self.t1.pack(fill="x", padx=12, pady=(6, 0))
        self.t2 = tk.Label(self, bg=T.COLORS["panel"], fg=T.COLORS["sub"],
                           font=T.font(8), anchor="w")
        self.t2.pack(fill="x", padx=12, pady=(0, 6))
        for w in (self, self.t1, self.t2):
            w.bind("<Button-1>", lambda e: self.command() if self.command else None)
            w.bind("<Enter>", lambda e: self._paint(True))
            w.bind("<Leave>", lambda e: self._paint(False))

    def set(self, name, meta):
        self.t1.config(text=name)
        self.t2.config(text=meta)

    def _paint(self, hover):
        bg = T.COLORS["rowOn"] if self._on else (T.COLORS["rowHover"] if hover else T.COLORS["panel"])
        self.config(bg=bg)
        self.t1.config(bg=bg)
        self.t2.config(bg=bg)

    def set_active(self, on):
        self._on = on
        self._paint(False)


class SideLink(tk.Label):
    """사이드바 아래쪽 한 줄 메뉴(설정·기록·도움말)."""
    def __init__(self, parent, text, command):
        super().__init__(parent, text=text, bg=T.COLORS["panel"], fg=T.COLORS["ink"],
                         font=T.font(10), anchor="w", padx=12, pady=6, cursor="hand2")
        self._cmd = command
        self._on = False
        self.bind("<Button-1>", lambda e: self._cmd() if self._cmd else None)
        self.bind("<Enter>", lambda e: (not self._on) and self.config(bg=T.COLORS["rowHover"]))
        self.bind("<Leave>", lambda e: self.config(bg=T.COLORS["rowOn"] if self._on else T.COLORS["panel"]))

    def set_active(self, on):
        self._on = on
        self.config(bg=T.COLORS["rowOn"] if on else T.COLORS["panel"])


class ScrollFrame(tk.Frame):
    """세로 스크롤 되는 영역 — 내용은 `.body` 에 넣는다.

    표준 패턴: Canvas + 내부 Frame(create_window) + Scrollbar + 마우스휠(플랫폼별).
    ⚠️ Configure 핸들러는 **스크롤 영역만** 갱신하고 위젯 크기는 안 바꿈 → 무한 재귀 없음.
    참고: VerticalScrolledFrame(gist JackTheEngineer) · ActiveState 580640.
    """
    def __init__(self, parent, bg=None):
        bg = bg or T.COLORS["bg"]
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body)      # 내용 높이 바뀌면 스크롤영역만 갱신
        self.canvas.bind("<Configure>", self._on_canvas)  # 창 너비 바뀌면 내부 폭만 맞춤
        self.canvas.bind("<Enter>", self._wheel_on)        # 마우스 올라올 때만 휠 잡기
        self.canvas.bind("<Leave>", self._wheel_off)

    def _on_body(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)

    def _wheel_on(self, _e):
        self.canvas.bind_all("<MouseWheel>", self._wheel)      # Windows / macOS
        self.canvas.bind_all("<Button-4>", self._wheel_lin)    # Linux 위로
        self.canvas.bind_all("<Button-5>", self._wheel_lin)    # Linux 아래로

    def _wheel_off(self, _e):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _wheel(self, e):
        if e.delta:
            self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def _wheel_lin(self, e):
        self.canvas.yview_scroll(-1 if getattr(e, "num", 5) == 4 else 1, "units")


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
