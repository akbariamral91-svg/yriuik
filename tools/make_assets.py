# -*- coding: utf-8 -*-
"""ساخت آیکون، اسپلش و گرافیک‌های فروشگاه با Pillow (قابل اجرای دوباره):  python tools/make_assets.py
خروجی: assets/icon.png, assets/splash.png, assets/splash_dark.png, assets/favicon.png, store/icon_512.png, store/feature_graphic.png"""
import math, os
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_A, GOLD_B = (245, 196, 83), (255, 159, 67)
BG_TOP, BG_BOTTOM, INDIGO = (14, 22, 54), (6, 10, 24), (58, 79, 192)

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def gradient(size, c1, c2, vertical=True):
    w, h = size; img = Image.new("RGB", size); px = img.load()
    for y in range(h):
        for x in range(w): px[x, y] = lerp(c1, c2, (y / max(1, h - 1)) if vertical else (x / max(1, w - 1)))
    return img

def star_mask(size, radius, cx, cy, p=0.58, ss=3):
    """ستارهٔ چهارپر با ضلع‌های خمیده (ابرمنحنی)؛ با فوق‌نمونه‌برداری برای لبهٔ نرم."""
    W, H = size[0] * ss, size[1] * ss; m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m); pts = []
    for i in range(720):
        t = 2 * math.pi * i / 720; c, s = math.cos(t), math.sin(t)
        pts.append((cx * ss + radius * ss * math.copysign(abs(c) ** (2 / p), c), cy * ss + radius * ss * math.copysign(abs(s) ** (2 / p), s)))
    d.polygon(pts, fill=255)
    return m.resize(size, Image.LANCZOS)

def draw_star(base, radius, cx, cy, glow=True):
    size = base.size; mask = star_mask(size, radius, cx, cy)
    if glow:
        halo = Image.new("RGBA", size, GOLD_A + (0,)); halo.putalpha(mask.filter(ImageFilter.GaussianBlur(radius * .22)).point(lambda v: int(v * .55)))
        base.alpha_composite(halo)
    fill = gradient(size, GOLD_A, GOLD_B).convert("RGBA"); fill.putalpha(mask); base.alpha_composite(fill)

def background(size):
    bg = gradient(size, BG_TOP, BG_BOTTOM).convert("RGBA")
    light = Image.new("RGBA", size, INDIGO + (0,)); a = Image.new("L", size, 0); d = ImageDraw.Draw(a)
    w, h = size; d.ellipse([w * .35, -h * .35, w * 1.35, h * .65], fill=110); light.putalpha(a.filter(ImageFilter.GaussianBlur(w * .12)))
    bg.alpha_composite(light); return bg

def icon(n=1024):
    img = background((n, n)); u = n / 1024
    draw_star(img, 300 * u, n * .5, n * .5)                     # محتوا داخل ناحیهٔ امن آیکون تطبیقی اندروید (۶۶٪ مرکز)
    draw_star(img, 92 * u, n * .5 + 235 * u, n * .5 - 235 * u)
    draw_star(img, 52 * u, n * .5 - 250 * u, n * .5 + 215 * u)
    return img.convert("RGB")

def splash(n=512):
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0)); draw_star(img, n * .30, n * .5, n * .5, glow=False); return img

def feature_graphic():
    W, H = 1024, 500; img = background((W, H)); draw_star(img, 150, 800, 250); draw_star(img, 46, 930, 120); draw_star(img, 30, 660, 380)
    d = ImageDraw.Draw(img); fonts = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    kw = {"layout_engine": ImageFont.Layout.RAQM} if features.check("raqm") else {}
    try:
        big, small = ImageFont.truetype(fonts[0], 86, **kw), ImageFont.truetype(fonts[1], 38, **kw)
        d.text((70, 150), "Get Better", font=big, fill=(238, 241, 251))
        d.text((74, 270), "برنامه‌ریز آمادگی آزمون", font=small, fill=GOLD_A, direction="rtl", language="fa", features=["-liga"] if kw else None) if kw else None
    except OSError: pass
    return img.convert("RGB")

if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True); os.makedirs(os.path.join(ROOT, "store"), exist_ok=True)
    ic = icon(1024); ic.save(os.path.join(ROOT, "assets", "icon.png"), optimize=True)
    ic.resize((512, 512), Image.LANCZOS).save(os.path.join(ROOT, "store", "icon_512.png"), optimize=True)
    ic.resize((64, 64), Image.LANCZOS).save(os.path.join(ROOT, "assets", "favicon.png"), optimize=True)
    sp = splash(); sp.save(os.path.join(ROOT, "assets", "splash.png"), optimize=True); sp.save(os.path.join(ROOT, "assets", "splash_dark.png"), optimize=True)
    feature_graphic().save(os.path.join(ROOT, "store", "feature_graphic.png"), optimize=True)
    print("assets ready")
