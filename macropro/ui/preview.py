# -*- coding: utf-8 -*-
"""🧪 미리보기 — 실제 입력 없이 동작 순서를 보여주고 실행 전 검사.

빠뜨린 이미지 파일·없는 저장 대상·정의 안 된 변수 토큰·사라진 목록 파일을 미리 알려 준다.
키보드/마우스는 전혀 움직이지 않음(데이터만 확인).
"""
import os
import re
import tkinter as tk

from .. import model, targets
from . import theme as T
from . import widgets as W

_TOKEN = re.compile(r"\{([^{}]{1,40})\}")
_BUILTINS = {"번호", "순번", "no", "n", "index", "i1", "반복", "회차0", "rep", "i", "i0",
             "날짜", "date", "시간", "time", "날짜시간", "datetime", "요일", "weekday"}


def _known_vars(mset, macro):
    names = set(_BUILTINS)
    for v in (getattr(mset, "variables", None) or []):
        if v.get("name"):
            names.add(str(v["name"]).strip())
    # 목록 열 이름(헤더) 읽어서 포함
    ls = getattr(macro, "list_source", None) or {}
    p = ls.get("path", "")
    if p and os.path.exists(p):
        try:
            if p.lower().endswith(".csv"):
                with open(p, encoding="utf-8-sig") as f:
                    first = f.readline().strip()
                for col in first.split(","):
                    names.add(col.strip())
            else:
                names.add("값")
        except Exception:
            pass
    return names


def _iter_text(actions):
    for a in actions:
        if a.get("type") in ("type", "paste", "broadcast"):
            yield a.get("text", "")
        if a.get("type") == "set":
            yield str(a.get("value", ""))
        if a.get("type") == "if":
            yield from _iter_text(a.get("then", []))
            yield from _iter_text(a.get("else", []))


def validate(mset, macro):
    warns = []
    # 이미지 파일
    for a in macro.actions:
        t = a.get("type")
        if t in ("image", "wait_image", "if_image"):
            p = a.get("path", "")
            if p and not os.path.exists(p):
                warns.append(f"🖼 이미지 파일 없음: {p}")
        if t == "ifcond" and a.get("condition", {}).get("source") == "image":
            p = a.get("condition", {}).get("value", "")
            if p and not os.path.exists(p):
                warns.append(f"🖼 조건 이미지 없음: {p}")
        if t == "broadcast":
            miss = targets.missing_targets(mset, a)
            if miss:
                warns.append(f"📚 저장 대상 없음: {', '.join(miss)}")
    # 목록 파일
    ls = getattr(macro, "list_source", None) or {}
    if ls.get("path") and not os.path.exists(ls["path"]):
        warns.append(f"📄 목록 파일 없음: {ls['path']}")
    # 정의 안 된 변수 토큰
    known = _known_vars(mset, macro)
    seen = set()
    for text in _iter_text(macro.actions):
        for tok in _TOKEN.findall(text or ""):
            tok = tok.strip()
            if tok and tok not in known and tok not in seen:
                seen.add(tok)
                warns.append(f"🔢 정의 안 된 변수 {{{tok}}} (🔧 변수에서 추가하거나 목록 열 이름 확인)")
    return warns


class Preview(tk.Toplevel):
    def __init__(self, app, macro):
        super().__init__(app.root, bg=T.COLORS["bg"])
        self.title(f"🧪 미리보기 — {macro.name}")
        self.geometry("520x560")
        self.transient(app.root)

        tk.Label(self, text=f"🧪  '{macro.name}' 실행 순서 (실제로 안 움직임)", bg=T.COLORS["bg"],
                 fg=T.COLORS["ink"], font=T.font(13, "bold")).pack(anchor="w", padx=16, pady=(14, 4))

        card = W.Card(self, "동작 순서")
        card.pack(fill="both", expand=True, padx=14, pady=(2, 6))
        lb = tk.Listbox(card.body, font=T.font(10), bg="white", fg=T.COLORS["ink"],
                        selectbackground=T.COLORS["accentSoft"], relief="flat",
                        highlightthickness=0, activestyle="none")
        lb.pack(fill="both", expand=True)
        if not macro.actions:
            lb.insert("end", "  (동작이 없어요 — 기록/편집에서 추가)")
        for i, a in enumerate(macro.actions, 1):
            try:
                lab = model.action_label(a)
            except Exception:
                lab = str(a.get("type", ""))
            lb.insert("end", f"  {i:>2}. {lab}")

        warns = validate(app.set, macro)
        wc = W.Card(self, "⚠ 실행 전 검사")
        wc.pack(fill="x", padx=14, pady=(0, 6))
        wt = tk.Text(wc.body, height=6, wrap="word", bg="white",
                     fg=T.COLORS["ink"], relief="flat", highlightthickness=0, font=T.font(9))
        wt.pack(fill="x")
        if warns:
            wt.insert("1.0", "\n".join(warns))
        else:
            wt.insert("1.0", "✅ 문제 없음 — 바로 실행해도 됩니다.")
        wt.configure(state="disabled")

        W.RoundButton(self, "닫기", self.destroy, bg=T.COLORS["slate"], hover=T.COLORS["slateDk"],
                      width=90, height=36).pack(pady=(0, 12))
