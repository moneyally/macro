# -*- coding: utf-8 -*-
"""icon.ico 생성 — 웜 코랄 배경 + 번개 (Anthropic 톤)."""
try:
    from PIL import Image, ImageDraw
except Exception:
    print("Pillow 없음 -> 아이콘 없이 빌드")
    raise SystemExit(0)

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# 둥근 코랄 배경
d.rounded_rectangle([10, 10, S - 10, S - 10], radius=56, fill=(217, 119, 87, 255))     # clay
d.rounded_rectangle([10, 10, S - 10, S - 10], radius=56, outline=(193, 95, 60, 255), width=6)
# 크림색 번개
bolt = [(150, 40), (92, 142), (130, 142), (100, 220), (184, 102), (140, 102), (170, 40)]
shadow = [(p[0] + 4, p[1] + 5) for p in bolt]
d.polygon(shadow, fill=(120, 55, 35, 90))
d.polygon(bolt, fill=(244, 241, 234, 255))
img.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon.ico created")
