# -*- coding: utf-8 -*-
"""Condition Evaluator — 상황을 판단하는 공통 부품.

조건 = 데이터: {"source": 종류, "operator": 비교, "value": 기준값, ...}
종류(source): image / window / active_title / pixel / clipboard
이미지 조건(if_image)도 이 부품을 거친다. 임의 코드 없음.

반환: True/False. 조회 자체가 실패(클립보드 접근 불가·창 조회 실패)하면
      '조건 불일치(False)'와 구분해서 None 을 돌려줄 수 있음 → 호출부가 결정.
"""


def _as_str(v):
    return "" if v is None else str(v)


def _hex_rgb(s):
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return None


def _str_cmp(op, left, right):
    left = _as_str(left)
    right = _as_str(right)
    if op in ("contains", "포함"):
        return right in left
    if op in ("not_contains", "미포함"):
        return right not in left
    if op in ("equals", "=", "같음"):
        return left == right
    if op in ("not_equals", "!=", "다름"):
        return left != right
    if op in ("empty", "비어있음"):
        return left.strip() == ""
    if op in ("not_empty", "있음"):
        return left.strip() != ""
    if op in ("startswith",):
        return left.startswith(right)
    if op in ("endswith",):
        return left.endswith(right)
    return False


def evaluate(engine, cond, ctx=None):
    """조건 하나를 판단. 모르는 조건/오류는 False (안전)."""
    r = _evaluate_raw(engine, cond, ctx)
    return bool(r)


def _evaluate_raw(engine, cond, ctx=None):
    if not isinstance(cond, dict):
        return False
    source = cond.get("source", "image")
    op = cond.get("operator", "exists")
    value = cond.get("value", "")
    if ctx is not None and isinstance(value, str):
        value = ctx.substitute(value)

    if source == "image":
        path = value if isinstance(value, str) else cond.get("value", "")
        found = engine.locate_image(path, cond.get("confidence", 0.8)) is not None
        return found if op in ("exists", "있음", "near", "equals", "같음") else (not found)

    if source == "window":
        try:
            from . import winctl
            exists = winctl.exists(value)
        except Exception:
            return False
        return exists if op in ("exists", "있음") else (not exists)

    if source == "active_title":
        try:
            from . import winctl
            title = winctl.active_title()
        except Exception:
            title = ""
        return _str_cmp(op, title, value)

    if source == "pixel":
        want = _hex_rgb(value if isinstance(value, str) else cond.get("value", ""))
        got = engine.pixel(int(cond.get("x", 0)), int(cond.get("y", 0)))
        if want is None or got is None:
            return False
        tol = int(cond.get("tol", 10))
        near = all(abs(a - b) <= tol for a, b in zip(got, want))
        # 기본은 '가까우면 참'. '다름/not_near' 일 때만 뒤집음 (operator 비워 둬도 안 뒤집히게)
        return (not near) if op in ("not_near", "다름", "!=", "not_equals") else near

    if source == "clipboard":
        try:
            from .clipboard import get_clipboard
            text = get_clipboard()
        except Exception:
            text = ""
        return _str_cmp(op, text, value)

    return False
