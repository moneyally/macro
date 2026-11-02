# -*- coding: utf-8 -*-
"""재생기(Execution Controller) — 매크로를 별도 스레드에서 실행.

옵션:
  · loops/speed/jitter/cycle/ime_lock/release_all/restore_mouse/rand_min·max (기존)
  · context   값·목록(RunContext) — {번호}·변수·CSV 치환
  · mset      저장 대상(창 기준 좌표·broadcast)
  · default_err  동작 오류 기본 처리(stop|skip)
실행 흐름:
  - 동작을 순서대로. 'if' 는 조건 판단 후 then/else 를 재귀 실행.
  - 'if_image' 는 옛 방식(다음 N개 건너뛰기) 그대로.
  - 동작마다 on_error(stop|skip|retry)+retry_count 로 오류 대응.
  - 진행 상황을 on_progress 로 알림(메인스레드가 받아 표시).
절대 시각 스케줄이라 오래 돌려도 타이밍이 안 밀림.
"""
import random
import threading

from . import conditions, ime, model
from . import values as V
from .timing import Scheduler, hrsleep


class Player:
    def __init__(self, engine):
        self.eng = engine
        self._stop = threading.Event()
        self._thread = None
        self.on_status = None       # 콜백(text)
        self.on_done = None         # 콜백(loops_done)
        self.on_progress = None     # 콜백(dict: name·i·total·label·rep)
        self._cur_name = ""

    @property
    def playing(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self._stop.set()

    def play(self, actions, *, loops=1, speed=1.0, jitter=0.0, cycle=0.0,
             ime_lock=False, release_all=True, restore_mouse=False,
             rand_min=0.0, rand_max=0.0, mset=None, macro=None, default_err="stop",
             name=""):
        if self.playing or not actions:
            return False
        self._stop.clear()
        jitter = min(1.0, max(0.0, jitter))          # 100%↑ 면 딜레이 음수 되던 것 막기
        rand_min = max(0.0, rand_min)
        rand_max = max(rand_min, rand_max)
        self._cur_name = name
        ctx = None
        try:
            ctx = V.RunContext(mset, macro)
        except Exception:
            ctx = None
        self._thread = threading.Thread(
            target=self._run,
            args=(list(actions), loops, max(0.05, speed), jitter, max(0.0, cycle),
                  ime_lock, release_all, restore_mouse, rand_min, rand_max,
                  ctx, mset, default_err),
            daemon=True)
        self._thread.start()
        return True

    def _status(self, t):
        cb = self.on_status          # 지역으로 한 번만 읽기 (종료 중 null 되는 경쟁 방지)
        if cb:
            cb(t)

    def _progress(self, label, done, total, rep):
        cb = self.on_progress
        if cb:
            try:
                cb({"name": self._cur_name, "done": done, "total": total,
                    "label": label, "rep": rep})
            except Exception:
                pass

    # ── 한 동작 앞의 대기(절대 스케줄) ────────────────────
    def _wait(self, a, sched, off, speed, jitter, cycle, rmin, rmax):
        dt = a.get("delay", 0.0) / speed
        if jitter and dt:
            dt *= random.uniform(1 - jitter, 1 + jitter)
        if rmax > 0:
            dt += random.uniform(rmin, rmax)
        if cycle and dt < cycle:
            dt = cycle
        off[0] += dt
        sched.wait_until(off[0])

    # ── 동작 1개 실행 + 오류 대응 ─────────────────────────
    # 반환: ("ok",) · ("skip", n) · ("stop",)
    def _do(self, a, default_err):
        policy = a.get("on_error", default_err)
        tries = int(a.get("retry_count", 0)) if policy == "retry" else 0
        delay = max(0, int(a.get("retry_delay_ms", 300))) / 1000.0
        attempt = 0
        while True:
            try:
                skip = self.eng.run_action(a, self._stop)
                if isinstance(skip, int) and skip > 0:
                    return ("skip", skip)
                return ("ok",)
            except Exception as ex:
                if policy == "retry" and attempt < tries and not self._stop.is_set():
                    attempt += 1
                    # 재시도 때 전체 키를 떼지 않음 — 걸쳐 누른 수식키·홀드가 풀리면 안 됨(게임 매크로)
                    hrsleep(delay)
                    continue
                if policy == "skip":
                    return ("ok",)                   # 건너뛰고 계속
                self._status(f"오류: {ex}")
                return ("stop",)

    # ── 동작 목록 실행(재귀: if 의 then/else) ─────────────
    # 반환: True(계속) · False(매크로 중단)
    def _exec(self, actions, sched, off, speed, jitter, cycle, rmin, rmax,
              default_err, prog, total, rep):
        i = 0
        na = len(actions)
        while i < na:
            if self._stop.is_set():
                return True
            a = actions[i]
            t = a.get("type")
            self._wait(a, sched, off, speed, jitter, cycle, rmin, rmax)
            if self._stop.is_set():
                return True
            if t == "if":                            # 🧠 공통 조건 분기
                ok = conditions.evaluate(self.eng, a.get("condition", {}), self.eng.ctx)
                branch = a.get("then", []) if ok else a.get("else", [])
                prog[0] += 1
                self._progress("🧠 조건", prog[0], total, rep)
                if branch:
                    if self._exec(branch, sched, off, speed, jitter, cycle, rmin, rmax,
                                  default_err, prog, total, rep) is False:
                        return False
                i += 1
                continue
            res = self._do(a, default_err)
            if res[0] == "stop":
                return False
            prog[0] += 1
            try:
                label = model.action_label(a)
            except Exception:
                label = a.get("type", "")
            self._progress(label, prog[0], total, rep)
            if res[0] == "skip":
                i += res[1]
            i += 1
        return True

    def _run(self, actions, loops, speed, jitter, cycle, ime_lock, release_all, restore_mouse,
             rand_min, rand_max, ctx, mset, default_err):
        self.eng.ctx = ctx
        self.eng.mset = mset
        start_pos = self.eng.get_pos()
        prev_hangul = None
        if ime_lock:
            prev_hangul = ime.is_hangul()
            ime.set_hangul(False)        # 영문으로 고정
        sched = Scheduler()
        n = 0
        total = _count_actions(actions)
        list_mode = ctx is not None and ctx.has_list()   # 목록 있으면 목록이 끝까지 돌림(반복횟수 무시)
        try:
            while not self._stop.is_set():
                sched.start()
                off = [0.0]
                prog = [0]
                rep = ctx.rep if ctx is not None else n
                cont = self._exec(actions, sched, off, speed, jitter, cycle, rand_min, rand_max,
                                  default_err, prog, total, rep)
                if self._stop.is_set():          # 정지 중이면 회차·목록커서 더 안 건드리고 바로 끝
                    break
                n += 1
                self._status(f"▶ 실행 {n}회" + ("" if loops == 0 else f"/{loops}"))
                if cont is False:
                    break
                if not list_mode and loops and n >= loops:
                    break
                if ctx is not None and not ctx.next_rep():   # 목록 끝 → 멈춤
                    break
        except Exception as ex:
            self._status(f"오류: {ex}")
        finally:
            if release_all:
                self.eng.release_all()
            if restore_mouse:
                try:
                    self.eng.set_pos(*start_pos)
                except Exception:
                    pass
            if ime_lock and prev_hangul:
                ime.set_hangul(True)         # 원래 한글이었으면 되돌림
            self.eng.ctx = None
            self.eng.mset = None
            cb = self.on_done                # 지역으로 한 번만 (종료 중 null 경쟁 방지)
            if cb:
                cb(n)


def _count_actions(actions):
    """진행률 표시용 대략 동작 수(if 안쪽은 then/else 중 긴 쪽으로 — done 이 total 안 넘게)."""
    total = 0
    for a in actions:
        total += 1
        if a.get("type") == "if":
            total += max(_count_actions(a.get("then", [])), _count_actions(a.get("else", [])))
    return total
