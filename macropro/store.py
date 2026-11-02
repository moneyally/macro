# -*- coding: utf-8 -*-
"""영구 저장소 — 자동 저장(JSON) + 실행 기록(SQLite).

- 매크로는 끌 때·바꿀 때마다 autosave.json 에 저장, 켤 때 자동 불러옴 (작업 안 날아감).
- 실행할 때마다 history.db(SQLite) 에 기록(이름·반복·시각).
위치: Windows = %APPDATA%\\MacroPRO , 그 외 = ~/.macropro
"""
import json
import os
import sqlite3
import sys
import time


def data_dir():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "MacroPRO")
    else:
        d = os.path.join(os.path.expanduser("~"), ".macropro")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.abspath(".")
    return d


def _autosave_path():
    return os.path.join(data_dir(), "autosave.json")


def save_set(mset):
    try:
        tmp = _autosave_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mset.to_dict(), f, ensure_ascii=False)
        os.replace(tmp, _autosave_path())
        return True
    except Exception:
        return False


def load_set():
    from .model import MacroSet
    p = _autosave_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return MacroSet.from_dict(json.load(f))
    except Exception:
        return None


# ── 실행 기록 (SQLite) ────────────────────────────────────
def _db():
    con = sqlite3.connect(os.path.join(data_dir(), "history.db"), timeout=5)
    con.execute("CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT, loops INTEGER, ts INTEGER)")
    # 상세 실행 기록: 실행마다 ID 부여, 시작·종료·진행·상태
    con.execute("CREATE TABLE IF NOT EXISTS run_log(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT, started INTEGER, ended INTEGER, loops INTEGER, "
                "total INTEGER, done INTEGER, status TEXT, note TEXT)")
    return con


def start_run(name, total=0):
    """실행 시작 기록 → run_id. 실패하면 None (기록 실패해도 실행은 계속)."""
    try:
        con = _db()
        try:
            cur = con.execute("INSERT INTO run_log(name, started, status, total, done, loops) "
                              "VALUES(?,?,?,?,0,0)", (name, int(time.time()), "running", int(total)))
            con.commit()
            return cur.lastrowid
        finally:
            con.close()
    except Exception:
        return None


def finish_run(run_id, loops=0, done=0, status="done", note=""):
    if not run_id:
        return
    try:
        con = _db()
        try:
            con.execute("UPDATE run_log SET ended=?, loops=?, done=?, status=?, note=? WHERE id=?",
                        (int(time.time()), int(loops), int(done), status, (note or "")[:300], run_id))
            # 상세 기록도 최근 2000개만
            con.execute("DELETE FROM run_log WHERE id < (SELECT MAX(id) FROM run_log) - 2000")
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def recent_run_log(n=200):
    try:
        con = _db()
        try:
            return con.execute("SELECT name, started, ended, loops, total, done, status "
                               "FROM run_log ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        finally:
            con.close()
    except Exception:
        return []


def log_run(name, loops):
    try:
        con = _db()
        try:
            con.execute("INSERT INTO runs(name, loops, ts) VALUES(?,?,?)", (name, int(loops), int(time.time())))
            # 기록이 무한정 커지지 않게 최근 2000개만 유지
            con.execute("DELETE FROM runs WHERE id < (SELECT MAX(id) FROM runs) - 2000")
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def recent_runs(n=30):
    try:
        con = _db()
        try:
            return con.execute("SELECT name, loops, ts FROM runs ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        finally:
            con.close()
    except Exception:
        return []


def clear_runs():
    try:
        con = _db()
        try:
            con.execute("DELETE FROM runs")
            con.commit()
        finally:
            con.close()
        return True
    except Exception:
        return False
