# -*- coding: utf-8 -*-
"""디자인 토큰 — Anthropic 느낌의 웜 팔레트 + 모던 타이포.

실제 Anthropic 폰트(Styrene/Tiempos)는 독점이라 번들 불가 →
시스템에서 가장 가까운 산세리프로 대체하고, 색 언어로 그 톤을 낸다.
"""
import sys

_WIN = sys.platform.startswith("win")

# ── 색 (웜 크림 배경 · 코랄 액센트 · 잉크 텍스트) ─────────
COLORS = {
    "bg":        "#F0EEE6",   # 웜 크림 배경
    "surface":   "#FBFAF7",   # 카드
    "surface2":  "#FFFFFF",   # 입력칸
    "ink":       "#1A1915",   # 거의 검정 텍스트
    "sub":       "#6E6B61",   # 보조 텍스트
    "line":      "#E3DFD3",   # 경계선
    "accent":    "#D97757",   # 코랄(Anthropic clay)
    "accentDk":  "#C15F3C",   # 코랄 진하게 (hover)
    "accentSoft":"#F3E3DB",   # 코랄 연한 배경
    "green":     "#2F7D53",
    "greenDk":   "#256342",
    "red":       "#C0493B",
    "redDk":     "#9F3B30",
    "slate":     "#3B3A35",
    "slateDk":   "#2A2925",
    "amber":     "#C98A2B",
    "amberDk":   "#A9731F",
    "chipOn":    "#1F7A4D",
    "chipOff":   "#8A867A",
    # 사이드바(어두운 웜 톤 — 옛 버전 호환용)
    "side":      "#2A2925",
    "sideHover": "#3B3A35",
    "sideInk":   "#CFCABB",
    "sideSub":   "#908B7E",
    # 밝은 목록형 사이드바(Claude 앱 느낌)
    "panel":     "#F4F2EA",   # 사이드바 배경(살짝 어두운 크림)
    "panelLine": "#E0DCCF",   # 사이드바-메인 경계선
    "rowOn":     "#EDE3D7",   # 선택된 줄
    "rowHover":  "#ECE9DF",   # 마우스 올린 줄
}

_UI = "Segoe UI" if _WIN else "Noto Sans CJK KR"
_KR = "맑은 고딕" if _WIN else "Noto Sans CJK KR"


def font(size=10, weight="normal", kr=True):
    return (_KR if kr else _UI, size, weight)


RADIUS = 14          # 기본 둥근 반경
