# -*- coding: utf-8 -*-
"""키/마우스 버튼 직렬화 + 조합키(ctrl+c) 파싱.

pynput Key/KeyCode/Button 을 JSON 으로 저장 가능한 형태로 바꾸고 되돌린다.
"""
from pynput import keyboard, mouse

# 이름 → 특수키
NAMED = {
    "ctrl": keyboard.Key.ctrl, "control": keyboard.Key.ctrl,
    "lctrl": keyboard.Key.ctrl_l, "rctrl": keyboard.Key.ctrl_r,
    "alt": keyboard.Key.alt, "lalt": keyboard.Key.alt_l, "ralt": keyboard.Key.alt_r,
    "shift": keyboard.Key.shift, "lshift": keyboard.Key.shift_l, "rshift": keyboard.Key.shift_r,
    "win": keyboard.Key.cmd, "cmd": keyboard.Key.cmd, "super": keyboard.Key.cmd,
    "enter": keyboard.Key.enter, "return": keyboard.Key.enter, "tab": keyboard.Key.tab,
    "esc": keyboard.Key.esc, "escape": keyboard.Key.esc, "space": keyboard.Key.space,
    "backspace": keyboard.Key.backspace, "bs": keyboard.Key.backspace,
    "delete": keyboard.Key.delete, "del": keyboard.Key.delete,
    "up": keyboard.Key.up, "down": keyboard.Key.down, "left": keyboard.Key.left, "right": keyboard.Key.right,
    "home": keyboard.Key.home, "end": keyboard.Key.end,
    "pageup": keyboard.Key.page_up, "pgup": keyboard.Key.page_up,
    "pagedown": keyboard.Key.page_down, "pgdn": keyboard.Key.page_down,
    "insert": keyboard.Key.insert, "ins": keyboard.Key.insert,
    "capslock": keyboard.Key.caps_lock, "caps": keyboard.Key.caps_lock,
}
for _i in range(1, 25):
    _k = getattr(keyboard.Key, f"f{_i}", None)
    if _k is not None:
        NAMED[f"f{_i}"] = _k

BUTTONS = {"left": mouse.Button.left, "right": mouse.Button.right, "middle": mouse.Button.middle}
for _bn in ("x1", "x2", "button8", "button9"):   # 마우스 옆버튼(있으면)
    _bt = getattr(mouse.Button, _bn, None)
    if _bt is not None:
        BUTTONS[_bn] = _bt


def ser_key(key):
    """pynput 키 → dict."""
    if isinstance(key, keyboard.KeyCode):
        if key.char is not None:
            return {"k": "char", "v": key.char}
        return {"k": "vk", "v": key.vk}
    return {"k": "special", "v": key.name}


def deser_key(d):
    """dict → pynput Controller 가 받는 키(문자 또는 Key/KeyCode)."""
    if d["k"] == "char":
        return d["v"]
    if d["k"] == "special":
        return getattr(keyboard.Key, d["v"])
    return keyboard.KeyCode.from_vk(d["v"])


def key_name(key):
    """단축키 매칭용 표준 이름. 'f1', 'a', '1' 등."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return f"vk{key.vk}"
    return key.name  # 'f1', 'space' ...


def parse_combo(spec):
    """'ctrl+shift+s' → [Key.ctrl, Key.shift, 's'] (마지막이 실제 키)."""
    out = []
    for p in (spec or "").replace(" ", "").lower().split("+"):
        if p:
            out.append(NAMED.get(p, p))
    return out


def button_of(name):
    return BUTTONS.get(name, mouse.Button.left)
