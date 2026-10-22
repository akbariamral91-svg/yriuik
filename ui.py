# -*- coding: utf-8 -*-
"""سیستم طراحی Get Better: پالت، آیکون‌ها، کامپوننت‌ها و انیمیشن‌های ریز.

هیچ منطق کسب‌وکاری اینجا نیست؛ فقط ظاهر. main.py از این ماژول استفاده می‌کند.
همهٔ رنگ‌ها از دیکشنری زندهٔ `P` خوانده می‌شوند و با `set_mode()` عوض می‌شوند.
"""
import os, threading, time
import flet as ft
from jalali import fa

# ───────────────────────── پالت ─────────────────────────
DARK = dict(bg="#060A18", bg2="#0C1330", card="#111A38", card2="#1A2650", text="#EEF1FB", muted="#8E9AC2",
            gold="#F5C453", amber="#FF9F43", green="#34D399", red="#FF6B7A", blue="#7C9BFF", violet="#A78BFA",
            line="#FFFFFF", glass_a="#18234F", glass_b="#0F1836", hero=["#3A4FC0", "#1C2866", "#0F1740"], on_accent="#0A1128")
LIGHT = dict(bg="#F4F6FD", bg2="#E8EDFB", card="#FFFFFF", card2="#EDF0FB", text="#131A36", muted="#5C6788",
             gold="#C58A0C", amber="#F08A24", green="#0E9F6E", red="#D64555", blue="#4263EB", violet="#7048E8",
             line="#131A36", glass_a="#FFFFFF", glass_b="#F6F8FF", hero=["#FFE9A8", "#FFF3D3", "#FFFFFF"], on_accent="#FFFFFF")
P = dict(DARK)                        # دیکشنری زنده؛ جایگزین نمی‌شود، فقط به‌روز می‌شود
_mode = {"dark": True}

def set_mode(dark):
    _mode["dark"] = bool(dark); P.clear(); P.update(DARK if dark else LIGHT)
def is_dark(): return _mode["dark"]
def alpha(color, a): return ft.Colors.with_opacity(a, color)
def tone(key, a): return alpha(P[key], a)

# ───────────────────────── فونت ─────────────────────────
FONT = "Vazirmatn"
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
_FONT_FILES = {"": "Vazirmatn-Regular.ttf", "-Medium": "Vazirmatn-Medium.ttf", "-Bold": "Vazirmatn-Bold.ttf"}
_have = {k: os.path.exists(os.path.join(_FONT_DIR, f)) for k, f in _FONT_FILES.items()}
HAS_FONT = _have[""]

def setup_fonts(page):
    """هر وزنی که فایلش موجود باشد ثبت می‌شود؛ بقیه به وزن نزدیک می‌افتند."""
    if HAS_FONT:
        page.fonts = {FONT + k: "fonts/" + f for k, f in _FONT_FILES.items() if _have[k]}

def family(weight):
    if not HAS_FONT: return None
    w = str(weight or "")
    if any(x in w for x in ("W_7", "W_8", "W_9", "BOLD")) and _have["-Bold"]: return FONT + "-Bold"
    if "W_6" in w and _have["-Medium"]: return FONT + "-Medium"
    if "W_5" in w and _have["-Medium"]: return FONT + "-Medium"
    return FONT

# ───────────────────────── آیکون‌ها ─────────────────────────
def ic(name, style="rounded"):
    """آیکون هم‌خانوادهٔ Material. اگر نسخهٔ rounded/outlined نبود، به نسخهٔ پایه برمی‌گردد."""
    suffix = {"rounded": "_ROUNDED", "outlined": "_OUTLINED", "base": ""}[style]
    for n in (name + suffix, name):
        v = getattr(ft.Icons, n, None)
        if v is not None: return v
    return ft.Icons.CIRCLE

PRAYER_ICONS = {"prayer_fajr": "WB_TWILIGHT", "prayer_dhuhr": "WB_SUNNY", "prayer_asr": "LIGHT_MODE", "prayer_maghrib": "NIGHTLIGHT", "prayer_isha": "BEDTIME"}
ACHIEVEMENT_ICONS = {"first_step": ("ECO", "green"), "ten_missions": ("LOOKS_ONE", "blue"), "fifty_missions": ("SETTINGS_SUGGEST", "violet"),
                     "streak_3": ("LOCAL_FIRE_DEPARTMENT", "red"), "streak_7": ("BOLT", "gold"), "streak_30": ("WORKSPACE_PREMIUM", "gold"),
                     "level_5": ("ROCKET_LAUNCH", "blue"), "mastered_1": ("SCHOOL", "green"), "exam_1": ("EDIT_NOTE", "violet"),
                     "perfect": ("GRADE", "gold"), "focus_5h": ("CENTER_FOCUS_STRONG", "green"), "xp_1000": ("DIAMOND", "blue")}

# ───────────────────────── انیمیشن‌های ریز ─────────────────────────
EASE = ft.AnimationCurve.EASE_OUT_CUBIC
BACK = ft.AnimationCurve.EASE_OUT_BACK
ELASTIC = ft.AnimationCurve.ELASTIC_OUT
def anim(ms=300, curve=EASE): return ft.Animation(ms, curve)

class Motion:
    """صف کارهای «بعد از رندر». کامپوننت‌ها کار ثبت می‌کنند و main.render() بعد از page.update() اجرایشان می‌کند.
    هر رندر جدید، اجرای قبلی را باطل می‌کند (gen).

    سرعت: همهٔ حلقه‌ها، شمارنده‌ها و نوارها با «یک» رشتهٔ زمان‌بنیاد (ticker) جلو می‌روند و تغییرِ هر فریم
    با یک پیام (page.update(*controls)) به رابط می‌رسد؛ قبلاً هر کنترل در هر گام پیام جدا می‌فرستاد."""
    FRAME = .04                                          # ~۲۵ فریم در ثانیه
    def __init__(self):
        self.jobs, self.loops, self.sets, self.tweens, self.gen, self.page_w, self.prev, self.animate = [], [], [], [], 0, 400, {}, True
        self.page, self.base = None, 0.0
    def after(self, fn, delay=0.0): self.jobs.append((delay, fn))
    def first(self, fn, delay=0.0): self.jobs.insert(0, (delay, fn))
    def start(self, key, final):
        """مقدار شروع انیمیشن: صفحهٔ تازه از صفر؛ رندر دوباره‌ی همان صفحه از مقدار قبلی (بدون پرش)."""
        base = 0 if self.animate else final
        v = self.prev.get(key, base) if key is not None else base
        if key is not None: self.prev[key] = final
        return v
    def ambient(self, fn): self.loops.append(fn)
    def reset(self): self.jobs, self.loops, self.sets, self.tweens, self.base = [], [], [], [], 0.0
    def push(self, ctrls):
        """چند کنترل را با یک پیام به‌روز می‌کند؛ اگر نشد، تک‌تک."""
        ctrls = [c for c in ctrls if c is not None]
        if not ctrls: return
        if self.page is not None:
            try: self.page.update(*ctrls); return
            except Exception: pass
        for c in ctrls:
            try: c.update()
            except Exception: pass
    def flush(self):
        jobs, loops, sets, tweens = self.jobs, self.loops, self.sets, self.tweens
        self.jobs, self.loops, self.sets, self.tweens = [], [], [], []
        self.gen += 1; gen = self.gen; base = self.base
        if not (jobs or loops or sets or tweens): return
        def run():
            time.sleep(.06)
            for d, fn in jobs:
                if self.gen != gen: return
                if d: time.sleep(d)
                try: fn()
                except Exception: pass
            tick = 0
            while loops and self.gen == gen:                  # حرکت‌های آرام و بی‌پایان (نفس‌کشیدن)
                dirty = []
                for fn in loops:
                    try:
                        c = fn(tick)
                        if c is not None: dirty.append(c)
                    except Exception: pass
                self.push(dirty)
                tick += 1; time.sleep(1.4)
        def ticker():
            time.sleep(.06 + base)                            # اول ورود پلکانی بخش‌ها، بعد پر شدن نوار و حلقه‌ها
            t0 = time.monotonic()
            pend = [(t0 + d, fn, c) for d, fn, c in sets]
            act = [(t0 + dl, s_, a, b, dur, c) for s_, a, b, dur, dl, c in tweens]
            while (pend or act) and self.gen == gen:
                now = time.monotonic(); dirty = []
                keep = []
                for st, fn, c in pend:
                    if now < st: keep.append((st, fn, c)); continue
                    try: fn(); dirty.append(c)
                    except Exception: pass
                pend = keep; keep = []
                for st, s_, a, b, dur, c in act:
                    if now < st: keep.append((st, s_, a, b, dur, c)); continue
                    t = 1.0 if dur <= 0 else min(1.0, (now - st) / dur)
                    try: s_(a + (b - a) * (1 - (1 - t) ** 3))   # کاهندهٔ مکعبی؛ بر پایهٔ ساعت واقعی، پس با کندی دستگاه کند نمی‌شود
                    except Exception: continue
                    dirty.append(c)
                    if t < 1: keep.append((st, s_, a, b, dur, c))
                act = keep
                if self.gen != gen: return
                self.push(dirty)
                time.sleep(self.FRAME)
        if jobs or loops: threading.Thread(target=run, daemon=True).start()
        if sets or tweens: threading.Thread(target=ticker, daemon=True).start()
    def set_at(self, ctrl, fn, delay=0.0):
        """fn() را بعد از delay اجرا می‌کند و تغییر کنترل را در همان پیامِ فریم می‌فرستد (برای نوار پیشرفت)."""
        self.sets.append((delay, fn, ctrl))
    def tween(self, setter, a, b, dur=.7, steps=16, delay=0.0, ctrl=None):
        """تغییر تدریجی یک عدد (شمارندهٔ بالا‌رونده، حلقهٔ پیشرفت). اگر ctrl داده شود setter نباید update بزند."""
        self.tweens.append((setter, a, b, dur, delay, ctrl))
M = Motion()

def later(fn, delay=.2):
    def run():
        time.sleep(delay)
        try: fn()
        except Exception: pass
    threading.Thread(target=run, daemon=True).start()

def pulse(c, big=1.12, small=1.0):
    """نفس‌کشیدن ملایم یک کنترل (برای آیکون شعله و غیره)."""
    c.animate_scale = anim(1100, ft.AnimationCurve.EASE_IN_OUT)
    def f(tick): c.scale = big if tick % 2 == 0 else small; return c       # به‌روزرسانی را حلقهٔ مشترک یک‌جا می‌فرستد
    M.ambient(f)

def pop_in(c, delay=0.0, start=.4, live=False):
    """ظاهر شدن با جهش (تیک انجام‌شده، دستاورد…). live=True برای دیالوگ‌ها که بیرون از رندر صفحه‌اند."""
    c.scale = start; c.animate_scale = anim(520, ELASTIC)
    def f(): c.scale = 1; c.update()
    (later(f, .25 + delay) if live else M.after(f, delay))
    return c

# ───────────────────────── اجزای بصری ─────────────────────────
def txt(t, size=14, w=None, color=None, **kw):
    c = P[color] if color in P else (color or P["text"])
    fam = family(w)
    if fam and "font_family" not in kw: kw["font_family"] = fam
    return ft.Text(str(t), size=size, weight=w, color=c, **kw)

def ibadge(icon, color="gold", size=40, filled=False, radius=None):
    """نشان آیکون: مربع گرد با گرادیان ملایم و حاشیهٔ ظریف؛ نسخهٔ filled برای عناصر مهم."""
    col = P[color] if color in P else color
    r = radius if radius is not None else size * .34
    if filled:
        return ft.Container(ft.Icon(icon, size=size * .52, color=P["on_accent"]), width=size, height=size, border_radius=r, alignment=ft.alignment.center,
                            gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[col, P["amber"] if color == "gold" else alpha(col, .72)]),
                            shadow=ft.BoxShadow(blur_radius=14, spread_radius=-2, color=alpha(col, .45), offset=ft.Offset(0, 4)))
    return ft.Container(ft.Icon(icon, size=size * .52, color=col), width=size, height=size, border_radius=r, alignment=ft.alignment.center,
                        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[alpha(col, .26), alpha(col, .08)]),
                        border=ft.border.all(1, alpha(col, .28)))

def card(content, pad=16, bg=None, on_click=None, grad=False, margin=None, border=None, radius=24, tint=None, shadow=True, **kw):
    dark = is_dark()
    if grad: gradient = ft.LinearGradient(begin=ft.alignment.top_right, end=ft.alignment.bottom_left, colors=P["hero"])
    elif bg is None and tint is None: gradient = ft.LinearGradient(begin=ft.alignment.top_center, end=ft.alignment.bottom_center, colors=[P["glass_a"], P["glass_b"]])
    else: gradient = None
    if tint: gradient = ft.LinearGradient(begin=ft.alignment.top_right, end=ft.alignment.bottom_left, colors=[alpha(P[tint], .20), alpha(P[tint], .06)])
    edge = alpha(P["gold"], .34) if grad and dark else alpha(P["line"], .08 if dark else .07)
    if tint: edge = alpha(P[tint], .30)
    return ft.Container(content=content, padding=pad, border_radius=radius, on_click=on_click, margin=margin, gradient=gradient,
                        bgcolor=bg if (bg is not None and not tint) else None,
                        border=border or ft.border.all(1, edge),
                        shadow=ft.BoxShadow(blur_radius=18, spread_radius=-6, color=alpha("#000000", .45 if dark else .12), offset=ft.Offset(0, 8)) if shadow else None,
                        ink=bool(on_click), animate=anim(280), **kw)

def chip(label, color, icon=None, on_click=None, solid=False):
    fg = P["on_accent"] if solid else P[color]
    row = [ft.Icon(icon, size=13, color=fg)] if icon else []
    row.append(txt(label, 11, ft.FontWeight.W_600, fg))
    return ft.Container(ft.Row(row, spacing=4, tight=True), padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=20, on_click=on_click, animate=anim(220),
                        bgcolor=P[color] if solid else alpha(P[color], .13), border=None if solid else ft.border.all(1, alpha(P[color], .24)))

def title(t, sub=None):
    c = [txt(t, 26, ft.FontWeight.W_800)]
    if sub: c.append(txt(sub, 12, color="muted"))
    return ft.Column(c, spacing=2)

def section(t, action=None, icon=None):
    lead = ibadge(icon, "gold", 26, radius=9) if icon else ft.Container(width=4, height=18, border_radius=3,
            gradient=ft.LinearGradient(begin=ft.alignment.top_center, end=ft.alignment.bottom_center, colors=[P["gold"], P["violet"]]))
    return ft.Row([ft.Row([lead, txt(t, 16, ft.FontWeight.W_800)], spacing=8), action or ft.Container()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

def empty(icon, msg, action=None):
    halo = ft.Container(ft.Container(ibadge(icon, "gold", 58, filled=True, radius=20), width=96, height=96, border_radius=48, alignment=ft.alignment.center,
                                     bgcolor=alpha(P["gold"], .09), border=ft.border.all(1, alpha(P["gold"], .18))),
                        width=124, height=124, border_radius=62, alignment=ft.alignment.center, bgcolor=alpha(P["gold"], .04))
    pulse(halo, 1.05)
    col = [halo, txt(msg, 13, color="muted", text_align=ft.TextAlign.CENTER)]
    if action: col.append(action)
    return ft.Container(ft.Column(col, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12), padding=26, alignment=ft.alignment.center)

def btn(label, on_click, icon=None, primary=True):
    return ft.ElevatedButton(label, icon=icon, on_click=on_click, height=48,
                             style=ft.ButtonStyle(bgcolor=P["gold"] if primary else P["card2"], color=P["on_accent"] if primary else P["text"],
                                                  shape=ft.RoundedRectangleBorder(radius=16), elevation=8 if primary else 0, shadow_color=alpha(P["gold"], .55),
                                                  overlay_color=alpha(P["text"], .08)))

def field(label, value="", **kw):
    return ft.TextField(label=label, value=value, border_radius=16, filled=True, bgcolor=alpha(P["card2"], .9), border_color="transparent",
                        focused_border_color=P["gold"], border_width=0, focused_border_width=1.6, cursor_color=P["gold"],
                        content_padding=ft.padding.symmetric(horizontal=16, vertical=14), text_size=14,
                        label_style=ft.TextStyle(color=P["muted"], size=13), **kw)

_DIGITS = "0-9۰-۹٠-٩"          # ارقام لاتین، فارسی و عربی

def num_field(label, value="", **kw):
    """ورودی فقط‌عددی: حرف و علامت اصلاً وارد نمی‌شود و روی گوشی کیبورد عددی باز می‌شود."""
    kw.setdefault("keyboard_type", ft.KeyboardType.NUMBER)
    kw.setdefault("input_filter", ft.InputFilter(allow=True, regex_string=f"[{_DIGITS}]", replacement_string=""))
    return field(label, value, **kw)

def fmt_time_digits(raw):
    """فقط ارقام را نگه می‌دارد و «:» را خودکار می‌گذارد: ۱۶۳۰ → ۱۶:۳۰ ، ۹۳۰ → ۹:۳۰ ، ۰۶۰۵ → ۰۶:۰۵."""
    from jalali import en
    d = "".join(c for c in en(raw) if c in "0123456789")
    hl = 1 if d[:1] > "2" else 2           # ساعتِ تک‌رقمی فقط وقتی رقم اول ۳ تا ۹ باشد
    d = d[:hl + 2]
    return d if len(d) <= hl else f"{d[:hl]}:{d[hl:]}"

def time_field(label, value="", **kw):
    """ورودی ساعت: کیبورد عددی، فقط رقم؛ دونقطه خودکار گذاشته می‌شود (هر ساعتی را می‌شود نوشت)."""
    def changed(e):
        f = fmt_time_digits(e.control.value or "")
        if f != e.control.value: e.control.value = f; e.control.update()
    kw.setdefault("input_filter", ft.InputFilter(allow=True, regex_string=f"[{_DIGITS}:]", replacement_string=""))
    kw.setdefault("on_change", changed)
    kw.setdefault("hint_text", "HH:MM")
    return num_field(label, value, **kw)

def dd(value, options, width=None, **kw):
    return ft.Dropdown(value=value, options=[ft.dropdown.Option(k, t) for k, t in options], width=width, border_radius=16, filled=True,
                       bgcolor=alpha(P["card2"], .9), border_color="transparent", text_size=13, **kw)

def seg(selected, options, on_change=None):
    return ft.SegmentedButton(selected={str(selected)}, allow_multiple_selection=False, on_change=on_change,
                              segments=[ft.Segment(value=str(k), label=txt(v, 12)) for k, v in options])

def snack_bar(msg, ok=True):
    col = P["on_accent"] if ok else "#FFFFFF"
    return ft.SnackBar(ft.Row([ft.Icon(ic("CHECK_CIRCLE" if ok else "ERROR"), color=col, size=20), txt(msg, 13, ft.FontWeight.W_600, col, expand=True)], spacing=10),
                       bgcolor=P["gold"] if ok else P["red"], behavior=ft.SnackBarBehavior.FLOATING, shape=ft.RoundedRectangleBorder(radius=16),
                       margin=ft.margin.only(left=16, right=16, bottom=96), duration=2400)

def pbar(frac, color="gold", h=8, width=None, off=76, delay=.05, key=None):
    """نوار پیشرفت با انیمیشن پر شدن. width = عرض کامل؛ در غیر این‌صورت عرض صفحه منهای off."""
    frac = max(0.0, min(1.0, float(frac))); full = width or max(60, M.page_w - off)
    st = M.start(key, frac)
    fill = ft.Container(width=(max(h, full * st) if st else 0), height=h, border_radius=h, animate=anim(900, EASE),
                        gradient=ft.LinearGradient(colors=[P[color], P["amber"] if color == "gold" else alpha(P[color], .7)]),
                        shadow=ft.BoxShadow(blur_radius=10, spread_radius=-2, color=alpha(P[color], .5)) if frac else None)
    def go(): fill.width = max(h, full * frac) if frac else 0
    if abs(st - frac) > 1e-6: M.set_at(fill, go, delay)
    return ft.Container(ft.Row([fill], alignment=ft.MainAxisAlignment.START), width=full, height=h, border_radius=h, bgcolor=alpha(P["text"], .10), clip_behavior=ft.ClipBehavior.ANTI_ALIAS)

def progress_ring(**kw):
    """ProgressRing با سرِ گرد؛ اگر نسخهٔ Flet پارامتر stroke_cap را نداشت بدون آن ساخته می‌شود."""
    try: return ft.ProgressRing(stroke_cap=ft.StrokeCap.ROUND, **kw)
    except Exception: return ft.ProgressRing(**kw)

def ring(frac, size=78, stroke=8, color="gold", center=None, delay=.1, key=None):
    """حلقهٔ پیشرفت که از صفر تا مقدار هدف پر می‌شود."""
    frac = max(0.0, min(1.0, float(frac)))
    st = M.start(key, frac)
    pr = progress_ring(value=st, width=size, height=size, stroke_width=stroke, color=P[color], bgcolor=alpha(P["text"], .10))
    def set_(v): pr.value = v
    if abs(st - frac) > 1e-6: M.tween(set_, st, frac, .9, 18, delay, ctrl=pr)
    layers = [pr] + ([ft.Container(center, alignment=ft.alignment.center, width=size, height=size)] if center is not None else [])
    return ft.Stack(layers, width=size, height=size)

def count_up(value, size=20, w=ft.FontWeight.W_800, color=None, suffix="", delay=.1, key=None):
    """عدد بالا‌رونده؛ مقدار نهایی با اعداد فارسی."""
    value = int(value); st = M.start(key, value)
    t = txt(fa(int(st)) + suffix, size, w, color)
    def set_(v): t.value = fa(int(round(v))) + suffix
    if int(st) != value: M.tween(set_, st, value, .8, 16, delay, ctrl=t)
    return t

def divider(): return ft.Container(height=1, bgcolor=alpha(P["line"], .07), margin=ft.margin.symmetric(vertical=2))
def spacer(h=104): return ft.Container(height=h)

def glow(size, color="gold", a=.10, **pos):
    return ft.Container(width=size, height=size, border_radius=size // 2, **pos,
                        gradient=ft.RadialGradient(center=ft.alignment.center, radius=.5, colors=[alpha(P[color], a * 2.2), alpha(P[color], 0)]))
