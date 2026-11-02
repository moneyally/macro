# -*- coding: utf-8 -*-
"""⚡ 매크로 PRO 실행 진입점.   python run.py"""
import tkinter as tk

from macropro.timing import disable_high_res_timer, enable_high_res_timer
from macropro.ui.app import App


def main():
    enable_high_res_timer()
    root = tk.Tk()
    try:
        # exe/py 옆의 icon.ico 있으면 창 아이콘으로
        import os
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(ico):
            root.iconbitmap(ico)
    except Exception:
        pass
    App(root)
    try:
        root.mainloop()
    finally:
        disable_high_res_timer()


if __name__ == "__main__":
    main()
