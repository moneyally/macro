# -*- coding: utf-8 -*-
"""Target Resolver — '어디에' 를 푸는 공통 부품.

- 저장 대상(MacroSet.targets): 자주 쓰는 방/창을 한 번 등록해 여러 매크로가 재사용.
    {"id": "room_01", "name": "1번방", "kind": "coord", "x":.., "y":..}
    {"id": "room_02", "name": "공지방", "kind": "window", "title": "텔레그램 … 방"}
- 창 기준 상대좌표: 창이 움직여도 같은 버튼 클릭. (x,y)=창 안쪽 영역 비율(0~1).
방 이름을 코드에 하드코딩하지 않음 — 전부 사용자 값.
"""


def find(mset, target_id):
    for t in (getattr(mset, "targets", None) or []):
        if t.get("id") == target_id:
            return t
    return None


def window_point(title, rx, ry):
    """창 안쪽 영역의 비율(rx,ry: 0~1) → 화면좌표 (x,y). 못 찾으면 None."""
    try:
        from . import winctl
        rect = winctl.client_rect(title)
    except Exception:
        rect = None
    if not rect:
        return None
    x, y, w, h = rect
    rx = min(1.0, max(0.0, float(rx)))
    ry = min(1.0, max(0.0, float(ry)))
    return (int(x + w * rx), int(y + h * ry))


def resolve_click_point(engine, a, mset=None):
    """click/move 동작의 실제 화면좌표. 창 기준이면 변환, 아니면 그대로.
    못 찾으면 None (호출부가 오류 규칙대로 처리)."""
    mode = a.get("coordinate_mode", "screen")
    if mode == "window_relative":
        pt = window_point(a.get("window", ""), a.get("x", 0), a.get("y", 0))
        return pt
    return (int(a.get("x", 0)), int(a.get("y", 0)))


def resolve_broadcast(mset, a):
    """broadcast 가 돌 대상들을 순서대로. 각 항목:
      ("coord", (x,y))  또는  ("win", "창제목")
    action 의 target_ids(저장 대상) + targets(옛 인라인) 둘 다 지원."""
    out = []
    for tid in (a.get("target_ids") or []):
        t = find(mset, tid)
        if not t:
            continue
        if t.get("kind") == "window":
            out.append(("win", t.get("title", "")))
        else:
            out.append(("coord", (int(t.get("x", 0)), int(t.get("y", 0)))))
    for pt in (a.get("targets") or []):     # 옛 인라인 방식(좌표 리스트 또는 {"win":..})
        if isinstance(pt, dict) and pt.get("win"):
            out.append(("win", pt["win"]))
        else:
            try:
                out.append(("coord", (int(pt[0]), int(pt[1]))))
            except Exception:
                continue
    return out


def missing_targets(mset, a):
    """broadcast 의 target_ids 중 저장 대상에 없는 것 (실행 전 검사용)."""
    miss = []
    for tid in (a.get("target_ids") or []):
        if not find(mset, tid):
            miss.append(tid)
    return miss
