# -*- coding: utf-8 -*-
"""Get Better — برنامه‌ریز آمادگی آزمون (Flet 0.28.x + SQLite، کاملاً آفلاین)

صفحه‌ها: امروز • هفته • پیشرفت • یادداشت‌ها • مرور • تنظیمات • روتین‌ها
ظاهر و انیمیشن‌ها در ui.py (سیستم طراحی) و منطق داده در store.py است.
"""
import os, sys, sqlite3, threading, time, math, traceback
from datetime import date, datetime, timedelta
import flet as ft
import jalali as J
import meta
import ui
from jalali import fa
from ui import (P, alpha, ic, txt, ibadge, card, chip, title, section, empty, btn, field, num_field, time_field, dd, seg, pbar, ring, count_up, divider, spacer,
                glow, M, anim, pulse, pop_in, later, EASE, BACK, ELASTIC, PRAYER_ICONS, ACHIEVEMENT_ICONS)
from store import Store, log_error, read_error_log, clear_error_log, level_for_xp, xp_threshold, level_title, data_dir, ACHIEVEMENTS, REPEATS, PRAYERS, KINDS_TASK, WEEK_ORDER

PRIO = [("کم", "green"), ("متوسط", "gold"), ("زیاد", "red")]
STATUS = [("شروع‌نشده", "muted"), ("در حال یادگیری", "blue"), ("نیازمند مرور", "gold"), ("تسلط تأییدشده", "green")]
KINDS = {"practice": "تمرین", "exam": "آزمون", "review": "مرور"}
NAV = [("امروز", "HOME", 44), ("هفته", "CALENDAR_MONTH", 38), ("پیشرفت", "INSIGHTS", 52), ("یادداشت‌ها", "STICKY_NOTE_2", 78), ("مرور", "AUTO_STORIES", 36)]
VERSION = meta.VERSION

def install_error_hooks():
    """خطاهای پیش‌بینی‌نشده (حتی در رشته‌های پس‌زمینه) در errors.log ثبت می‌شوند تا برنامه بی‌صدا خراب نشود."""
    def hook(t, v, tb): log_error("unhandled", v)
    def thook(a): log_error(f"thread {getattr(a.thread, 'name', '?')}", a.exc_value)
    sys.excepthook = hook; threading.excepthook = thook

def today(): return date.today()
def fmt_minutes(m):
    m = int(m)
    return f"{fa(m)} دقیقه" if m < 60 else f"{fa(m // 60)} ساعت" + (f" و {fa(m % 60)} دقیقه" if m % 60 else "")


def main(page: ft.Page):
    install_error_hooks()
    store = Store()
    M.page = page                                  # برای ارسال دسته‌ای تغییرات انیمیشن (یک پیام در هر فریم)
    S = {"tab": 0, "nav": 0, "notes_tab": 0, "q": "", "tag": None, "day": today().isoformat(), "wk": today().isoformat(), "pop": None, "subs_open": set()}
    page.data = S                                  # برای تست‌ها و اشکال‌زدایی
    LIFE = []                                      # شنونده‌های چرخهٔ عمر (مثلاً تایمر تمرکز)
    def on_life(e):
        for cb in list(LIFE):
            try: cb(str(getattr(e, "state", None) or getattr(e, "data", "") or ""))
            except Exception as ex: log_error("lifecycle", ex)
    try: page.on_app_lifecycle_state_change = on_life
    except Exception as ex: log_error("lifecycle", ex)

    page.title = meta.APP_NAME
    try: page.on_error = lambda e: log_error("page.on_error", Exception(str(getattr(e, "data", e))))
    except Exception: pass
    page.padding = 0
    page.window.width, page.window.height = 400, 820   # فقط برای اجرای دسکتاپ/تست
    ui.setup_fonts(page)
    try: page.rtl = True
    except Exception: pass

    def apply_theme():
        ui.set_mode(store.pref("theme") != "light")
        page.theme_mode = ft.ThemeMode.DARK if ui.is_dark() else ft.ThemeMode.LIGHT
        kw = {"font_family": ui.FONT} if ui.HAS_FONT else {}
        page.theme = ft.Theme(color_scheme_seed=P["gold"], use_material3=True, **kw)
        page.dark_theme = page.theme
        page.bgcolor = P["bg"]

    def snack(msg, ok=True): page.open(ui.snack_bar(msg, ok))
    def update_width(e=None):
        try: M.page_w = int(page.width or 400)
        except Exception: M.page_w = 400
    try: page.on_resized = update_width
    except Exception: pass

    def dialog(heading, controls, on_save, save_label="ذخیره", cancel=True, icon="EDIT", color="gold"):
        head = ft.Row([ibadge(ic(icon), color, 36, radius=12), txt(heading, 18, ft.FontWeight.W_800, expand=True)], spacing=10)
        dlg = ft.AlertDialog(modal=True, bgcolor=P["card"], shape=ft.RoundedRectangleBorder(radius=28), title=head, inset_padding=ft.padding.symmetric(horizontal=16, vertical=24),
                             content=ft.Container(ft.Column(controls, tight=True, spacing=10, scroll=ft.ScrollMode.AUTO), width=340))
        def save(e):
            if on_save() is not False: page.close(dlg)
        dlg.actions = ([ft.TextButton("انصراف", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=P["muted"]))] if cancel else []) + \
                      [ft.FilledButton(save_label, on_click=save, style=ft.ButtonStyle(bgcolor=P["gold"], color=P["on_accent"], shape=ft.RoundedRectangleBorder(radius=14)))]
        page.open(dlg)
        return dlg

    def confirm(heading, msg, on_yes, danger=True):
        col = "red" if danger else "gold"
        dlg = ft.AlertDialog(modal=True, bgcolor=P["card"], shape=ft.RoundedRectangleBorder(radius=28),
                             title=ft.Row([ibadge(ic("DELETE_FOREVER" if danger else "HELP"), col, 36, radius=12), txt(heading, 18, ft.FontWeight.W_800, expand=True)], spacing=10),
                             content=txt(msg, 14, color="muted"))
        def yes(e): page.close(dlg); on_yes()
        dlg.actions = [ft.TextButton("خیر", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=P["muted"])),
                       ft.FilledButton("بله", on_click=yes, style=ft.ButtonStyle(bgcolor=P["red"] if danger else P["gold"], color="#FFFFFF" if danger else P["on_accent"], shape=ft.RoundedRectangleBorder(radius=14)))]
        page.open(dlg)

    def jdate_field(label, iso=None):
        """انتخابگر تاریخ جلالی (روز/ماه/سال) بدون دیالوگ تو در تو. خروجی: (کنترل، گرفتن ISO، تنظیم ISO)."""
        d0 = J.as_date(iso) if iso else today(); jy, jm, jd = J.to_jalali(d0)
        cur = J.to_jalali(today())[0]
        years = sorted(set(range(cur - 1, cur + 6)) | {jy})
        yr = dd(str(jy), [(str(y), fa(y)) for y in years], 104)
        mo = dd(str(jm), [(str(i + 1), n) for i, n in enumerate(J.MONTHS)], 132)
        dy = dd(str(jd), [(str(i), fa(i)) for i in range(1, 32)], 80)
        def refresh(e=None):
            ml = J.month_length(int(yr.value), int(mo.value))
            dy.options = [ft.dropdown.Option(str(i), fa(i)) for i in range(1, ml + 1)]
            if int(dy.value) > ml: dy.value = str(ml)
            if e is not None: dy.update()
        yr.on_change = mo.on_change = refresh; refresh()
        def get(): return J.from_jalali(int(yr.value), int(mo.value), int(dy.value)).isoformat()
        def set_(v):
            a, b, c = J.to_jalali(J.as_date(v))
            if str(a) not in [o.key for o in yr.options]: yr.options.append(ft.dropdown.Option(str(a), fa(a)))
            yr.value, mo.value = str(a), str(b); refresh(); dy.value = str(c)
            for x in (yr, mo, dy): x.update()
        quick = ft.Row([chip(n, "gold", on_click=lambda e, k=k: set_((today() + timedelta(days=k)).isoformat()))
                        for n, k in (("امروز", 0), ("فردا", 1), ("پس‌فردا", 2), ("هفتهٔ بعد", 7))], spacing=6, wrap=True)
        return ft.Column([txt(label, 12, color="muted"), ft.Row([dy, mo, yr], spacing=6), quick], spacing=6), get, set_

    # ================= دستاوردها =================
    def celebrate(new):
        if not new: return
        rows = []
        for aid, t, d, _e in new:
            icon, col = ACHIEVEMENT_ICONS.get(aid, ("EMOJI_EVENTS", "gold"))
            badge = pop_in(ft.Container(ibadge(ic(icon), col, 56, filled=True, radius=19)), .05, .2, live=True)
            rows.append(ft.Row([badge, ft.Column([txt(t, 15, ft.FontWeight.W_800, "gold"), txt(d, 12, color="muted")], spacing=2, expand=True)], spacing=14))
        dialog("دستاورد جدید!", rows, lambda: True, "عالیه", cancel=False, icon="EMOJI_EVENTS")
    def after_action():
        try: celebrate(store.check_achievements())
        except Exception: traceback.print_exc()

    # ================= مأموریت‌ها =================
    def norm_time(v):
        """هر ساعتی: '۱۶:۳۰' / '1630' / '930' / '16' / '9:05' → 'HH:MM'؛ خالی → ''؛ نامعتبر → None."""
        v = J.en(v).strip().replace("٫", ":").replace("：", ":").replace(".", ":")
        if not v: return ""
        if ":" in v:
            h, _, mi = v.partition(":")
            if not (h.isdigit() and mi.isdigit() and len(h) <= 2 and len(mi) == 2): return None
        elif v.isdigit() and len(v) <= 4:
            hl = 1 if v[0] > "2" else 2
            h, mi = v[:hl], (v[hl:] or "00")
            if len(mi) == 1: return None
        else: return None
        if int(h) > 23 or int(mi) > 59: return None
        return f"{int(h):02d}:{int(mi):02d}"
    def time_label(r):
        if not r["time"]: return ""
        if not r["minutes"]: return fa(r["time"])
        end = (datetime.strptime(r["time"], "%H:%M") + timedelta(minutes=r["minutes"])).strftime("%H:%M")
        return f"{fa(r['time'])}–{fa(end)}"

    def mission_form(row=None, day=None, kind=None):
        """کار: ساعت و مدت اختیاری • ریزه‌کار: کار کوچک بدون ساعت معین."""
        k0 = (row["kind"] if row else kind) or "task"
        kseg = seg(k0, list(KINDS_TASK.items()))
        t = field("عنوان", row["title"] if row else "", autofocus=True)
        sub = field("درس (اختیاری)", row["subject"] if row else "")
        tm = time_field("ساعت شروع (اختیاری، مثل ۱۶:۳۰)", row["time"] if row else "")
        mins = num_field("مدت (دقیقه، اختیاری)", str(row["minutes"]) if row and row["minutes"] else "")
        def setv(c, v): c.value = v; c.update()
        sub_chips = ft.Row([chip(s["name"], "blue", on_click=lambda e, n=s["name"]: setv(sub, n)) for s in store.all("SELECT name FROM subjects ORDER BY name")], spacing=6, scroll=ft.ScrollMode.AUTO)
        min_chips = ft.Row([chip(fa(m), "gold", on_click=lambda e, m=m: setv(mins, str(m))) for m in (15, 30, 45, 60, 90, 120)], spacing=6, scroll=ft.ScrollMode.AUTO)
        task_box = ft.Column([tm, mins, min_chips], spacing=10, visible=k0 == "task")
        def kind_changed(e): task_box.visible = list(e.control.selected)[0] == "task"; task_box.update()
        kseg.on_change = kind_changed
        dfield, get_day, _ = jdate_field("تاریخ", row["date"] if row else (day or S["day"]))
        pr = seg(row["priority"] if row else 1, [(i, n) for i, (n, _) in enumerate(PRIO)])
        def save():
            k = list(kseg.selected)[0]
            if not t.value.strip(): t.error_text = "عنوان الزامی است"; t.update(); return False
            time_s, m = "", 0
            if k == "task":
                time_s = norm_time(tm.value)
                if time_s is None: tm.error_text = "ساعت نامعتبر است (۰۰:۰۰ تا ۲۳:۵۹)"; tm.update(); return False
                try: m = min(1440, max(0, int(J.en(mins.value)))) if mins.value.strip() else 0
                except Exception: mins.error_text = "عدد وارد کنید"; mins.update(); return False
            store.save_mission(t.value.strip()[:150], sub.value.strip(), m, int(list(pr.selected)[0]), get_day(), row["id"] if row else None,
                               (row["repeat"] if row else "") or "", None, k, time_s)
            render()
        dialog("ویرایش" if row else "کار یا ریزه‌کار جدید", [kseg, t, sub, sub_chips, task_box, dfield, txt("اولویت", 12, color="muted"), pr], save, icon="TASK_ALT")

    def toggle(mid):
        if store.toggle_mission(mid):
            m = store.one("SELECT xp FROM missions WHERE id=?", (mid,)); snack(f"آفرین! +{fa(m['xp'])} XP"); S["pop"] = mid
        render(); after_action()

    def focus_dialog(m):
        """تایمر پومودورو: تمرکز/استراحت خودکار؛ زمان تمرکز روی مأموریت و آمار ثبت می‌شود."""
        work, brk = max(1, store.pref_int("pomodoro", 25)), max(1, store.pref_int("break", 5))
        st = dict(phase="work", left=float(work * 60), run=False, stop=False, spent=0.0, rounds=0)
        clock = txt("", 46, ft.FontWeight.W_800, "gold"); phase_t = txt("", 13, color="muted")
        rg = ui.progress_ring(value=0, width=200, height=200, stroke_width=11, color=P["gold"], bgcolor=alpha(P["text"], .10))
        halo = ft.Container(width=232, height=232, border_radius=116, animate=anim(900, ft.AnimationCurve.EASE_IN_OUT),
                            gradient=ft.RadialGradient(center=ft.alignment.center, radius=.5, colors=[alpha(P["gold"], .20), alpha(P["gold"], 0)]))
        main_btn = ft.FilledButton("شروع", icon=ic("PLAY_ARROW"), style=ft.ButtonStyle(bgcolor=P["gold"], color=P["on_accent"], shape=ft.RoundedRectangleBorder(radius=16)))
        def mmss(s): s = max(0, math.ceil(s)); return fa(f"{s // 60:02d}:{s % 60:02d}")
        def paint():
            total = (work if st["phase"] == "work" else brk) * 60
            clock.value = mmss(st["left"]); rg.value = min(1, max(0, 1 - st["left"] / total))
            col = P["gold"] if st["phase"] == "work" else P["green"]
            rg.color = col; clock.color = col
            halo.gradient = ft.RadialGradient(center=ft.alignment.center, radius=.5, colors=[alpha(col, .30 if st["run"] else .12), alpha(col, 0)])
            phase_t.value = ("زمان تمرکز" if st["phase"] == "work" else "استراحت کوتاه") + (f" • دور {fa(st['rounds'] + 1)}" if st["phase"] == "work" else "")
            main_btn.text = "توقف" if st["run"] else ("ادامه" if st["spent"] > 0 or st["rounds"] else "شروع")
            main_btn.icon = ic("PAUSE") if st["run"] else ic("PLAY_ARROW")
            for c in (clock, phase_t, rg, main_btn, halo):
                try: c.update()
                except Exception: pass
        lock = threading.Lock(); st.update(last=time.time(), closed=False)
        def flip():
            """تغییر مرحله (تمرکز ⇄ استراحت) فقط در وضعیت؛ رنگ‌آمیزی جداست."""
            if st["phase"] == "work": st["rounds"] += 1; st["phase"] = "break"; st["left"] = float(brk * 60)
            else: st["phase"] = "work"; st["left"] = float(work * 60)
        def advance():
            """زمان را از روی ساعت واقعی جلو می‌برد، نه از روی تیک‌های رشته؛ پس خاموش‌شدن صفحه یا رفتن به پس‌زمینه شمارش را عقب نمی‌اندازد.
            خروجی: (تعداد مرحله‌های طی‌شده، فاصلهٔ زمانی از آخرین هم‌گام‌سازی به ثانیه)."""
            with lock:
                now = time.time(); dt = max(0.0, now - st["last"]); st["last"] = now     # ساعت به عقب برود → صفر
                if not st["run"] or dt <= 0: return 0, dt
                crossed, budget = 0, dt
                while budget > 0:
                    step = min(budget, st["left"]); st["left"] -= step; budget -= step
                    if st["phase"] == "work": st["spent"] += step
                    if st["left"] <= 1e-6:
                        flip(); crossed += 1
                        if crossed >= 4 and budget > 0:      # بیش از دو چرخهٔ کامل بی‌حضور: تایمر فراموش‌شده را متوقف کن تا زمان مفت ثبت نشود
                            st["run"] = False; break
                return crossed, dt
        def sync(e=None):
            """هم‌گام‌سازی با ساعت + رنگ‌آمیزی؛ از حلقه و از رویداد چرخهٔ عمر برنامه (برگشت از پس‌زمینه) صدا زده می‌شود."""
            if st["stop"]: return
            crossed, dt = advance()
            if crossed and dt > 3: snack("تایمر در غیاب تو ادامه پیدا کرد و مرحله عوض شد")
            paint()
        def switch(e=None):
            advance(); flip(); st["last"] = time.time(); paint()
        def loop():
            while not st["stop"]:
                time.sleep(.5)
                if st["stop"]: break
                try: sync()
                except Exception as ex: log_error("تایمر تمرکز", ex)
        def run_toggle(e): advance(); st["run"] = not st["run"]; st["last"] = time.time(); paint()
        main_btn.on_click = run_toggle
        def close(complete=False, e=None):
            if st["closed"]: return                       # با «بازگشت» سیستم هم بسته می‌شود؛ ذخیره فقط یک بار
            st["closed"] = True; advance(); st["stop"] = True
            if life_cb in LIFE: LIFE.remove(life_cb)
            if st["spent"] >= 20: store.add_focus(m["id"], int(st["spent"]))
            try: page.close(dlg)
            except Exception: pass
            if complete and not store.one("SELECT done FROM missions WHERE id=?", (m["id"],))["done"]: toggle(m["id"])
            else: render(); after_action()
        life_cb = lambda state: sync()
        LIFE.append(life_cb)
        dial = ft.Stack([halo, ft.Container(rg, alignment=ft.alignment.center, width=232, height=232), ft.Container(clock, alignment=ft.alignment.center, width=232, height=232)], width=232, height=232)
        dlg = ft.AlertDialog(modal=True, bgcolor=P["card"], shape=ft.RoundedRectangleBorder(radius=28),
            title=ft.Row([ibadge(ic("CENTER_FOCUS_STRONG"), "gold", 36, radius=12), txt("حالت تمرکز", 18, ft.FontWeight.W_800)], spacing=10),
            content=ft.Container(ft.Column([txt(m["title"], 14, ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER), dial, phase_t,
                ft.Row([main_btn, ft.TextButton("رد کردن", on_click=switch, style=ft.ButtonStyle(color=P["muted"]))], alignment=ft.MainAxisAlignment.CENTER),
                txt("گوشی را کنار بگذار و فقط روی همین کار تمرکز کن؛ تایمر با ساعت واقعی می‌شمارد.", 11, color="muted", text_align=ft.TextAlign.CENTER)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, tight=True), width=300),
            on_dismiss=lambda e: close(),
            actions=[ft.TextButton("پایان و ذخیره", on_click=lambda e: close(), style=ft.ButtonStyle(color=P["muted"])),
                     ft.FilledButton("تکمیل مأموریت", on_click=lambda e: close(True), style=ft.ButtonStyle(bgcolor=P["green"], color="#FFFFFF", shape=ft.RoundedRectangleBorder(radius=14)))])
        page.open(dlg); paint()
        threading.Thread(target=loop, daemon=True).start()

    def check_button(r, size):
        done = bool(r["done"]); pname, pcol = PRIO[max(0, min(2, r["priority"]))]
        b = ft.IconButton(ic("CHECK_CIRCLE") if done else ic("RADIO_BUTTON_UNCHECKED", "outlined"), icon_size=size,
                          icon_color=P["green"] if done else alpha(P[pcol], .95), tooltip="برگرداندن" if done else "انجام شد", on_click=lambda e, i=r["id"]: toggle(i))
        if done and S.get("pop") == r["id"]:
            S["pop"] = None; return pop_in(ft.Container(b), .02, .35)
        return b

    def mission_tile(r, compact=False):
        done = bool(r["done"]); pname, pcol = PRIO[max(0, min(2, r["priority"]))]; routine = r["routine_id"] is not None
        title_w = ft.Text(r["title"], size=14 if compact else 15, color=P["muted"], font_family=ui.family(None), style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)) if done else txt(r["title"], 14 if compact else 15, ft.FontWeight.W_600)
        if routine:
            def edit_routine(e, i=r["routine_id"]):
                x = store.one("SELECT * FROM routines WHERE id=?", (i,))
                if x: routine_form(x)
            items = [ft.PopupMenuItem(text="ویرایش روتین", icon=ic("EDIT", "outlined"), on_click=edit_routine),
                     ft.PopupMenuItem(text="مدیریت روتین‌ها", icon=ic("EVENT_REPEAT"), on_click=lambda e: (S.update(tab=6), render()))]
        else:
            items = [ft.PopupMenuItem(text="ویرایش", icon=ic("EDIT", "outlined"), on_click=lambda e, x=r: mission_form(x)),
                     ft.PopupMenuItem(text="انتقال به فردا", icon=ic("EVENT_REPEAT"), on_click=lambda e, i=r["id"]: (store.move_tomorrow(i), render())),
                     ft.PopupMenuItem(text="حذف", icon=ic("DELETE", "outlined"), on_click=lambda e, i=r["id"]: confirm("حذف", "حذف شود؟ امتیاز قبلی پاک نمی‌شود.", lambda: (store.delete_mission(i), render())))]
        menu = ft.PopupMenuButton(icon=ic("MORE_VERT"), icon_color=P["muted"], items=items, tooltip="گزینه‌ها")
        if compact:      # ریزه‌کار و روتین: یک خط ساده
            sub = [txt(r["subject"], 11, color="muted")] if r["subject"] else []
            tl = time_label(r); extra = [chip(tl, "gold", ic("SCHEDULE"))] if tl else []
            return card(ft.Row([check_button(r, 26), ft.Column([title_w, *sub], spacing=0, expand=True), *extra, menu], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                        pad=ft.padding.only(left=2, right=2, top=0, bottom=0), margin=ft.margin.only(bottom=6), radius=20, shadow=False, bg=alpha(P["card"], .75) if not ui.is_dark() else None)
        meta = []
        if r["time"]: meta.append(chip(time_label(r), "gold", ic("SCHEDULE")))
        if r["minutes"]: meta.append(chip(fmt_minutes(r["minutes"]), "muted", ic("TIMER", "outlined")))
        meta += [chip(pname, pcol, ic("FLAG")), chip(f"{fa(r['xp'])} XP", "gold", ic("BOLT"))]
        if r["repeat"]: meta.append(chip(REPEATS[r["repeat"]], "blue", ic("REPEAT")))
        if r["spent_seconds"]: meta.append(chip(f"{fa(r['spent_seconds'] // 60)} دقیقه تمرکز", "green", ic("CENTER_FOCUS_STRONG")))
        trail = [ft.IconButton(ic("CENTER_FOCUS_STRONG", "outlined"), icon_color=P["gold"], tooltip="حالت تمرکز", on_click=lambda e, x=r: focus_dialog(x))] if not done else []
        body = ft.Column([title_w, txt(r["subject"], 12, color="muted") if r["subject"] else ft.Container(height=0), ft.Row(meta, spacing=6, wrap=True, run_spacing=4)], spacing=6, expand=True)
        strip = ft.Container(width=4, border_radius=4, bgcolor=P["green"] if done else P[pcol], opacity=.9)
        inner = ft.Row([strip, check_button(r, 30), body, *trail, menu], vertical_alignment=ft.CrossAxisAlignment.START, spacing=0)
        return card(ft.Container(inner, padding=ft.padding.only(right=0, top=0)), pad=ft.padding.only(left=4, right=10, top=10, bottom=12), margin=ft.margin.only(bottom=10),
                    border=ft.border.all(1, alpha(P["green"], .25)) if done else None)

    def smart_plan():
        items = store.suggest_plan(S["day"])
        if not items: snack("فعلاً مبحثی برای مرور سررسید نشده"); return
        rows = [ft.Row([ibadge(ic("AUTO_AWESOME"), "gold", 34, radius=11), ft.Column([txt(i["title"], 13, ft.FontWeight.W_600), txt(f"{i['subject']} • {fmt_minutes(i['minutes'])}", 11, color="muted")], spacing=0, expand=True)], spacing=10) for i in items]
        dialog("برنامهٔ هوشمند", [txt(f"بر اساس مرور فاصله‌دار، این {fa(len(items))} مورد برای {J.fmt(S['day'])} پیشنهاد می‌شود:", 12, color="muted"), *rows],
               lambda: (store.apply_plan(items, S["day"]), render()), "افزودن به برنامه", icon="AUTO_AWESOME")

    # ================= صفحهٔ امروز =================
    def is_prayer(r): return (r["rkey"] or "").startswith("prayer")

    def prayer_card(rows):
        short = {k: n for k, _, n in PRAYERS}; done = sum(1 for r in rows if r["done"]); items = []
        for r in sorted(rows, key=lambda x: x["rsort"]):
            ok = bool(r["done"]); icon = ic(PRAYER_ICONS.get(r["rkey"], "NIGHTS_STAY"))
            disc = ft.Container(ft.Icon(ic("CHECK") if ok else icon, size=22, color=P["on_accent"] if ok else P["muted"]), width=46, height=46, border_radius=23, alignment=ft.alignment.center,
                                bgcolor=P["green"] if ok else alpha(P["text"], .07), animate=anim(300), border=None if ok else ft.border.all(1, alpha(P["line"], .10)),
                                shadow=ft.BoxShadow(blur_radius=14, spread_radius=-2, color=alpha(P["green"], .5), offset=ft.Offset(0, 4)) if ok else None)
            if ok and S.get("pop") == r["id"]: S["pop"] = None; pop_in(disc, .02, .5)
            items.append(ft.Container(ft.Column([disc,
                txt(short.get(r["rkey"], r["title"]), 11, ft.FontWeight.W_600 if ok else None, "green" if ok else "muted")], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True, padding=ft.padding.symmetric(vertical=6), border_radius=16, ink=True, on_click=lambda e, i=r["id"]: toggle(i)))
        head = ft.Row([ft.Row([ibadge(ic("NIGHTS_STAY"), "gold", 30, radius=10), txt("نمازها", 15, ft.FontWeight.W_800)], spacing=8),
                       chip(f"{fa(done)} از {fa(len(rows))}", "green" if done == len(rows) else "gold")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        return card(ft.Column([head, ft.Row(items, spacing=2)], spacing=8), pad=14, margin=ft.margin.only(bottom=4))

    def page_home():
        store.ensure_day(S["day"])
        xp = store.xp(); lvl = level_for_xp(xp); lo, hi = xp_threshold(lvl), xp_threshold(lvl + 1)
        streak, _ = store.streaks(); goal = max(1, store.pref_int("daily_goal", 3))
        done_today = sum(1 for r in store.today_missions() if r["done"] and r["routine_id"] is None); focus_min = store.focus_seconds(today()) // 60
        goal_ok = done_today >= goal
        goal_ring = ring(min(1, done_today / goal), 76, 8, "green" if goal_ok else "gold", key="goal",
                         center=ft.Column([txt(f"{fa(done_today)}/{fa(goal)}", 15, ft.FontWeight.W_800), txt("هدف روز", 9, color="muted")], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER))
        lvl_ring = pulse_wrap(ring((xp - lo) / max(1, hi - lo), 88, 7, "gold", key="lvl",
                         center=ibadge(ic("MILITARY_TECH"), "gold", 46, filled=True, radius=16)))
        badges = [chip(f"{fa(streak)} روز پیاپی", "red" if streak else "muted", ic("LOCAL_FIRE_DEPARTMENT"))]
        if focus_min: badges.append(chip(f"{fa(focus_min)} دقیقه تمرکز", "green", ic("CENTER_FOCUS_STRONG")))
        hero = card(ft.Column([
            ft.Row([lvl_ring, ft.Column([ft.Row([txt(f"سطح {fa(lvl)}", 12, ft.FontWeight.W_600, "muted")]), txt(level_title(lvl), 24, ft.FontWeight.W_800, "gold"),
                    ft.Row([ft.Icon(ic("BOLT"), size=15, color=P["gold"]), count_up(xp, 14, ft.FontWeight.W_800, "gold", " XP", key="xp")], spacing=2)], spacing=1, expand=True),
                    goal_ring], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            pbar(min(1, (xp - lo) / max(1, hi - lo)), "gold", 8, off=76, key="xpbar"),
            ft.Row([txt("پیشرفت سطح", 11, color="muted"), txt(f"{fa(hi - xp)} امتیاز تا سطح بعد", 11, color="muted")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(badges, spacing=8, wrap=True)], spacing=12), pad=20, grad=True, radius=28)
        hero = ft.Container(ft.Stack([hero, glow(190, "gold", .10, left=-60, top=-70), glow(120, "violet", .12, right=-30, bottom=-40)]), border_radius=28, clip_behavior=ft.ClipBehavior.ANTI_ALIAS)

        sel = date.fromisoformat(S["day"]); ws = J.week_start(sel); load = store.day_load(ws); tiles = []
        for i in range(7):
            d = ws + timedelta(days=i); k = d.isoformat(); tot, dn = load[k]; is_sel = k == S["day"]
            dot = P["green"] if tot and dn == tot else (P["gold"] if tot else "transparent")
            fg = P["on_accent"] if is_sel else None
            tiles.append(ft.Container(ft.Column([txt(J.WEEKDAY_SHORT[d.weekday()], 11, color=P["on_accent"] if is_sel else "muted"),
                txt(fa(J.to_jalali(d)[2]), 16, ft.FontWeight.W_800, fg),
                ft.Container(width=6, height=6, border_radius=3, bgcolor=P["on_accent"] if (is_sel and tot) else dot, animate=anim(250))], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=9), border_radius=18, expand=True, ink=True, on_click=lambda e, k=k: (S.update(day=k), render()),
                bgcolor=P["gold"] if is_sel else alpha(P["card"], .85), animate=anim(260, EASE), scale=1.04 if is_sel else 1, animate_scale=anim(300, BACK),
                shadow=ft.BoxShadow(blur_radius=18, spread_radius=-2, color=alpha(P["gold"], .45), offset=ft.Offset(0, 6)) if is_sel else None,
                border=ft.border.all(1.5, P["gold"]) if d == today() and not is_sel else ft.border.all(1, alpha(P["line"], .07))))
        jy, jm, _ = J.to_jalali(sel)
        shift = lambda n: (lambda e: (S.update(day=(sel + timedelta(days=n)).isoformat()), render()))
        strip_head = ft.Row([ft.Row([ft.Icon(ic("CALENDAR_TODAY"), size=16, color=P["gold"]), txt(f"{J.MONTHS[jm - 1]} {fa(jy)}", 14, ft.FontWeight.W_700)], spacing=6),
            ft.Row([ft.IconButton(ic("CHEVRON_RIGHT"), icon_color=P["muted"], on_click=shift(-7)),
                    chip("امروز", "gold", ic("TODAY"), on_click=lambda e: (S.update(day=today().isoformat()), render())) if S["day"] != today().isoformat() else ft.Container(),
                    ft.IconButton(ic("CHEVRON_LEFT"), icon_color=P["muted"], on_click=shift(7))], spacing=0)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        h = datetime.now().hour; greet = "شب" if h >= 21 or h < 4 else "صبح" if h < 12 else "روز" if h < 17 else "عصر"
        out = [title(f"{greet} بخیر", J.fmt(today(), "full")), hero, strip_head, ft.Row(tiles, spacing=6)]

        over = store.overdue()
        if over and S["day"] == today().isoformat():
            out.append(card(ft.Row([ibadge(ic("WARNING_AMBER"), "red", 40), ft.Column([txt(f"{fa(len(over))} کار عقب‌افتاده", 14, ft.FontWeight.W_700), txt("بی‌خیال نشو؛ به امروز منتقلشون کن", 11, color="muted")], spacing=2, expand=True),
                chip("انتقال به امروز", "red", ic("EAST") , on_click=lambda e: (store.move_overdue_to_today(), render()))], spacing=10), tint="red", pad=12, radius=22, shadow=False))
        due = store.due_topics()
        if due:
            names = "، ".join(t["name"] for t in due[:3]) + ("…" if len(due) > 3 else "")
            out.append(card(ft.Row([ibadge(ic("AUTO_AWESOME"), "gold", 40), ft.Column([txt(f"{fa(len(due))} مبحث آمادهٔ مرور است", 14, ft.FontWeight.W_700), txt(names, 11, color="muted", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=2, expand=True),
                chip("برنامهٔ هوشمند", "gold", ic("AUTO_AWESOME"), on_click=lambda e: smart_plan())], spacing=10), tint="gold", pad=12, radius=22, shadow=False))

        rows = store.missions_on(S["day"])
        prayers = [r for r in rows if is_prayer(r)]; routine = sorted([r for r in rows if r["routine_id"] is not None and not is_prayer(r)], key=lambda r: (r["done"], r["rsort"]))
        tasks = [r for r in rows if r["routine_id"] is None and (r["kind"] or "task") == "task"]; chores = [r for r in rows if r["routine_id"] is None and (r["kind"] or "task") == "chore"]
        if prayers: out.append(prayer_card(prayers))
        if routine:
            out.append(section("روتین امروز", chip("مدیریت", "gold", ic("TUNE"), on_click=lambda e: (S.update(tab=6), render())), ic("EVENT_REPEAT")))
            out += [mission_tile(r, True) for r in routine]
        total_min = sum(r["minutes"] for r in tasks if not r["done"])
        label = "کارهای امروز" if S["day"] == today().isoformat() else f"کارهای {J.fmt(S['day'], 'long')}"
        out.append(section(label, chip("گزارش روز", "gold", ic("ASSESSMENT"), on_click=lambda e: daily_report()), ic("CHECKLIST")))
        if tasks and total_min: out.append(txt(f"{fmt_minutes(total_min)} کار باقی‌مانده", 12, color="muted"))
        out += [mission_tile(r) for r in tasks] or [empty(ic("TASK_ALT"), "کاری برای این روز نداری.\nبا دکمه ＋ بساز یا برنامهٔ هوشمند را امتحان کن", btn("برنامهٔ هوشمند", lambda e: smart_plan(), ic("AUTO_AWESOME"), False))]
        out.append(section("ریزه‌کارها", txt(f"{fa(sum(1 for r in chores if r['done']))} از {fa(len(chores))}", 12, color="muted") if chores else None, ic("PLAYLIST_ADD_CHECK")))
        def quick_chore(e):
            v = (e.control.value or "").strip()
            if v: store.save_mission(v, "", 0, 1, S["day"], kind="chore"); render()
        out.append(field("ریزه‌کار جدید… (بنویس و تأیید کن)", prefix_icon=ic("ADD_TASK"), on_submit=quick_chore))
        out += [mission_tile(r, True) for r in chores]
        return out + [spacer()]

    def pulse_wrap(c):
        w = ft.Container(c); pulse(w, 1.035); return w

    def daily_report():
        d = S["day"]; rows = store.missions_on(d); mine = [r for r in rows if r["routine_id"] is None]; c = sum(1 for r in mine if r["done"])
        rt = [r for r in rows if r["routine_id"] is not None]; pr = [r for r in rt if is_prayer(r)]
        x = store.one("SELECT COALESCE(SUM(xp),0) n FROM xp_ledger WHERE date(at)=?", (d,))["n"]; f = store.focus_seconds(d) // 60
        left = [r["title"] for r in mine if not r["done"]]
        def line(icon, col, text): return ft.Row([ibadge(ic(icon), col, 30, radius=10), txt(text, 14)], spacing=10)
        ctl = [line("TASK_ALT", "blue", f"کار و ریزه‌کار انجام‌شده: {fa(c)} از {fa(len(mine))}"), line("BOLT", "gold", f"XP کسب‌شده: {fa(x)}"), line("CENTER_FOCUS_STRONG", "green", f"زمان تمرکز: {fmt_minutes(f)}")]
        if pr: ctl.append(line("NIGHTS_STAY", "violet", f"نمازها: {fa(sum(1 for r in pr if r['done']))} از {fa(len(pr))}"))
        other = [r for r in rt if r not in pr]
        if other: ctl.append(line("EVENT_REPEAT", "blue", f"روتین: {fa(sum(1 for r in other if r['done']))} از {fa(len(other))}"))
        if left: ctl += [txt("باقی‌مانده:", 12, color="muted"), *[txt("• " + t, 12) for t in left[:6]]]
        else: ctl.append(txt("همه‌چیز انجام شد، دمت گرم!" if mine else "برای این روز کاری ثبت نشده بود.", 12, color="muted"))
        dialog("گزارش " + J.fmt(d), ctl, lambda: True, "باشه", cancel=False, icon="ASSESSMENT")

    # ================= برنامهٔ هفتگی =================
    def go_day(k):
        S.update(day=k, tab=0, nav=0); render()

    def page_week():
        ws = J.week_start(date.fromisoformat(S["wk"])); we = ws + timedelta(days=6); plan = store.week_plan(ws)
        a, b = J.to_jalali(ws), J.to_jalali(we)
        rng = f"{fa(a[2])} {J.MONTHS[a[1] - 1]} – {fa(b[2])} {J.MONTHS[b[1] - 1]} {fa(b[0])}"
        shift = lambda n: (lambda e: (S.update(wk=(ws + timedelta(days=n)).isoformat()), render()))
        tot = sum(d["total"] for d in plan); dn = sum(d["done"] for d in plan); mins = sum(r["minutes"] for d in plan for r in d["tasks"])
        head = card(ft.Column([ft.Row([ft.IconButton(ic("CHEVRON_RIGHT"), icon_color=P["gold"], on_click=shift(-7)), txt(rng, 15, ft.FontWeight.W_800, text_align=ft.TextAlign.CENTER),
                                       ft.IconButton(ic("CHEVRON_LEFT"), icon_color=P["gold"], on_click=shift(7))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            pbar((dn / tot) if tot else 0, "gold", 8, off=72, key="weekbar"),
            ft.Row([chip(f"{fa(dn)} از {fa(tot)} کار", "green" if tot and dn == tot else "gold", ic("TASK_ALT")), chip(fmt_minutes(mins) if mins else "بدون زمان‌بندی", "muted", ic("TIMER", "outlined")),
                    chip("این هفته", "gold", ic("TODAY"), on_click=lambda e: (S.update(wk=today().isoformat()), render())) if ws != J.week_start(today()) else ft.Container()],
                   spacing=8, wrap=True)], spacing=10), grad=True, pad=14)
        out = [title("برنامه هفتگی", "همهٔ کارهای هفته یک‌جا؛ برای ویرایش روی هر کار بزن"), head]
        for d in plan:
            day = d["date"]; k = day.isoformat(); is_today = day == today(); lines = []
            for r in d["tasks"]:
                ok = bool(r["done"]); tl = time_label(r); kind_chore = (r["kind"] or "task") == "chore"
                lines.append(ft.Row([ft.IconButton(ic("CHECK_CIRCLE") if ok else ic("RADIO_BUTTON_UNCHECKED", "outlined"), icon_size=22, icon_color=P["green"] if ok else P["muted"], on_click=lambda e, i=r["id"]: toggle(i)),
                    ft.Container(ft.Row([txt(tl, 11, ft.FontWeight.W_700, "gold") if tl else (txt("ریزه‌کار", 10, color="muted") if kind_chore else txt("بدون ساعت", 10, color="muted")),
                                         ft.Text(r["title"], size=13, expand=True, color=P["muted"], style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)) if ok else txt(r["title"], 13, expand=True)], spacing=8),
                                 expand=True, on_click=lambda e, x=r: mission_form(x), ink=True, border_radius=10, padding=ft.padding.symmetric(vertical=6))], spacing=0))
            badges = []
            if d["prayers"]: badges.append(chip(f"نماز {fa(d['prayer_done'])}/{fa(len(d['prayers']))}", "green" if d["prayer_done"] == len(d["prayers"]) else "muted", ic("NIGHTS_STAY")))
            if d["routine"]: badges.append(chip(f"روتین {fa(d['routine_done'])}/{fa(len(d['routine']))}", "blue", ic("EVENT_REPEAT")))
            head_row = ft.Row([ft.Container(ft.Row([ibadge(ic("TODAY" if is_today else "EVENT"), "gold" if is_today else "muted", 34, filled=is_today, radius=11),
                                                    ft.Column([txt(J.WEEKDAYS[day.weekday()], 14, ft.FontWeight.W_800, "gold" if is_today else None), txt(J.fmt(day, "long"), 11, color="muted")], spacing=0)], spacing=10),
                                            expand=True, on_click=lambda e, k=k: go_day(k), ink=True, border_radius=12),
                               chip(f"{fa(d['done'])}/{fa(d['total'])}", "green" if d["total"] and d["done"] == d["total"] else "muted") if d["total"] else ft.Container(),
                               ft.IconButton(ic("ADD_CIRCLE", "outlined"), icon_color=P["gold"], tooltip="افزودن به این روز", on_click=lambda e, k=k: mission_form(day=k))], vertical_alignment=ft.CrossAxisAlignment.CENTER)
            body_c = [head_row, *(lines or [txt("برنامه‌ای ثبت نشده", 12, color="muted")])]
            if badges: body_c.append(ft.Row(badges, spacing=6, wrap=True))
            out.append(card(ft.Column(body_c, spacing=2), pad=ft.padding.symmetric(horizontal=12, vertical=8), margin=ft.margin.only(bottom=8),
                            border=ft.border.all(1.5, alpha(P["gold"], .8)) if is_today else None))
        def copy_next():
            n = store.copy_week(ws, ws + timedelta(days=7)); snack(f"{fa(n)} مورد به هفتهٔ بعد کپی شد" if n else "چیزی برای کپی نبود (یا قبلاً کپی شده)", bool(n))
            if n: S["wk"] = (ws + timedelta(days=7)).isoformat()
            render()
        out.append(ft.Row([btn("کپی به هفتهٔ بعد", lambda e: confirm("کپی هفته", "کارها و ریزه‌کارهای این هفته (بدون روتین‌ها) به‌صورت انجام‌نشده به هفتهٔ بعد کپی شوند؟", copy_next, False), ic("CONTENT_COPY")),
                           btn("روتین‌ها و نماز", lambda e: (S.update(tab=6), render()), ic("EVENT_REPEAT"), False)], spacing=8, wrap=True))
        return out + [spacer()]

    # ================= روتین‌ها =================
    def days_label(days):
        return "هر روز" if len(days) == 7 else "، ".join(J.WEEKDAYS[d] for d in WEEK_ORDER if d in days)

    def routine_form(row=None):
        """روتین = کاری که همیشه در برنامه هست و هر روز (یا روزهای انتخابی) خودکار اضافه و صفر می‌شود."""
        k0 = row["kind"] if row else "chore"
        kseg = seg(k0, list(KINDS_TASK.items()))
        t = field("عنوان روتین (مثلاً ورزش صبحگاهی)", row["title"] if row else "", autofocus=True)
        tm = time_field("ساعت (اختیاری، مثل ۰۶:۳۰)", row["time"] if row else ""); mins = num_field("مدت (دقیقه، اختیاری)", str(row["minutes"]) if row and row["minutes"] else "")
        task_box = ft.Column([tm, mins], spacing=10, visible=k0 == "task")
        def kind_changed(e): task_box.visible = list(e.control.selected)[0] == "task"; task_box.update()
        kseg.on_change = kind_changed
        sel = set(store.routine_days(row)) if row else set(WEEK_ORDER)
        def day_chip(d):
            lab = txt(J.WEEKDAYS[d], 12, ft.FontWeight.W_600, P["muted"]); c = ft.Container(lab, padding=ft.padding.symmetric(horizontal=12, vertical=7), border_radius=20, animate=anim(220), animate_scale=anim(200, BACK))
            def paint(): on = d in sel; c.bgcolor = P["gold"] if on else alpha(P["muted"], .14); lab.color = P["on_accent"] if on else P["muted"]; c.scale = 1.06 if on else 1
            def tap(e): sel.symmetric_difference_update({d}); paint(); c.update()
            c.on_click = tap; paint(); return c
        def save():
            if not t.value.strip(): t.error_text = "عنوان الزامی است"; t.update(); return False
            if not sel: snack("حداقل یک روز را انتخاب کن", False); return False
            k = list(kseg.selected)[0]; time_s, m = "", 0
            if k == "task":
                time_s = norm_time(tm.value)
                if time_s is None: tm.error_text = "ساعت نامعتبر است (۰۰:۰۰ تا ۲۳:۵۹)"; tm.update(); return False
                try: m = max(0, int(J.en(mins.value))) if mins.value.strip() else 0
                except Exception: mins.error_text = "عدد وارد کنید"; mins.update(); return False
            store.save_routine(t.value.strip(), k, m, time_s, sel, row["id"] if row else None); render()
        dialog("ویرایش روتین" if row else "روتین جدید", [kseg, t, task_box, txt("روزهای تکرار", 12, color="muted"), ft.Row([day_chip(d) for d in WEEK_ORDER], spacing=6, run_spacing=6, wrap=True)], save, icon="EVENT_REPEAT")

    def page_routines():
        out = [ft.Row([ft.IconButton(ic("ARROW_FORWARD"), on_click=lambda e: (S.update(tab=1), render())), title("روتین‌ها", "کارهای همیشگی؛ هر روز خودکار اضافه و از نو شروع می‌شوند")]),
               card(ft.Row([ibadge(ic("INFO"), "gold", 34, radius=11), txt("نمازهای پنجگانه به‌صورت پیش‌فرض اینجا هست. هر روز تیک‌ها صفر می‌شوند و تاریخچهٔ روزهای قبل می‌ماند. با دکمهٔ ＋ روتین دلخواه بساز.", 12, color="muted", expand=True)], spacing=10), tint="gold", pad=12, shadow=False)]
        for r in store.routines():
            days = store.routine_days(r); kind = KINDS_TASK.get(r["kind"], "ریزه‌کار"); is_pr = (r["key"] or "").startswith("prayer")
            sub = f"{kind} • {days_label(days)}" + (f" • {fa(r['time'])}" if r["time"] else "") + (f" • {fmt_minutes(r['minutes'])}" if r["minutes"] else "")
            out.append(card(ft.Row([ibadge(ic(PRAYER_ICONS.get(r["key"], "NIGHTS_STAY") if is_pr else "EVENT_REPEAT"), "gold" if r["active"] else "muted", 40),
                ft.Column([txt(r["title"], 14, ft.FontWeight.W_600, None if r["active"] else "muted"), txt(sub, 11, color="muted")], spacing=2, expand=True),
                ft.Switch(value=bool(r["active"]), active_color=P["gold"], on_change=lambda e, i=r["id"]: (store.set_routine_active(i, e.control.value), render())),
                ft.PopupMenuButton(icon=ic("MORE_VERT"), icon_color=P["muted"], items=[
                    ft.PopupMenuItem(text="ویرایش", icon=ic("EDIT", "outlined"), on_click=lambda e, x=r: routine_form(x)),
                    ft.PopupMenuItem(text="حذف", icon=ic("DELETE", "outlined"), on_click=lambda e, i=r["id"]: confirm("حذف روتین", "روتین از این به بعد حذف شود؟ سابقهٔ روزهای انجام‌شده می‌ماند.", lambda: (store.delete_routine(i), render())))])], spacing=10),
                pad=ft.padding.only(left=14, right=6, top=8, bottom=8), margin=ft.margin.only(bottom=8)))
        if not store.routines(): out.append(empty(ic("EVENT_REPEAT"), "هنوز روتینی نداری. با دکمهٔ ＋ بساز"))
        return out + [spacer()]

    # ================= پیشرفت =================
    def page_progress():
        s = store.stats(); lvl = s["level"]
        def stat(icon, label, val, col, key):
            v = count_up(val, 20, ft.FontWeight.W_800, key=key) if isinstance(val, int) else txt(val, 20, ft.FontWeight.W_800)
            return ft.Container(card(ft.Column([ibadge(ic(icon), col, 38, radius=13), v, txt(label, 11, color="muted")], spacing=6), pad=14), col=6)
        grid = ft.ResponsiveRow([stat("BOLT", "XP کل", s["xp"], "gold", "s_xp"), stat("MILITARY_TECH", f"سطح • {level_title(lvl)}", lvl, "blue", "s_lvl"),
                                 stat("LOCAL_FIRE_DEPARTMENT", "بهترین استریک", f"{fa(s['best_streak'])} روز", "red", None), stat("CENTER_FOCUS_STRONG", "کل زمان تمرکز", fmt_minutes(s["focus_seconds"] // 60), "green", None),
                                 stat("CHECK_CIRCLE", "مأموریت انجام‌شده", f"{fa(s['done'])} از {fa(s['missions'])}", "green", None),
                                 stat("WORKSPACE_PREMIUM", "مباحث مسلط", f"{fa(s['mastered'])} از {fa(s['topics'])}", "gold", None)], spacing=10, run_spacing=10)

        exam = store.pref("exam_date"); goal_txt = store.pref("goal") or "هدفت را تعیین کن"; msg, sub = "تاریخ آزمون را تعیین کن", goal_txt
        if exam:
            try:
                d = J.days_until(exam)
                msg = f"{fa(d)} روز تا آزمون" if d > 0 else "آزمون امروز است، موفق باشی!" if d == 0 else "تاریخ آزمون گذشته است"
                left = s["topics"] - s["mastered"]
                sub = f"{J.fmt(exam)} • {goal_txt}" + (f" • {fa(left)} مبحث تا تسلط کامل" if left > 0 and d > 0 else "")
            except Exception: msg = "تاریخ آزمون ثبت شده است"
        countdown = card(ft.Row([ibadge(ic("EVENT_AVAILABLE"), "gold", 48, filled=True, radius=16), ft.Column([txt(msg, 16, ft.FontWeight.W_800), txt(sub, 12, color="muted")], spacing=2, expand=True),
                          ft.IconButton(ic("EDIT_CALENDAR", "outlined"), icon_color=P["gold"], on_click=lambda e: set_exam())], spacing=12), grad=True)

        # نمودار هفتگی (دقیقهٔ مطالعه)
        ws = store.week_series(); mx = max([w["minutes"] for w in ws] + [1]); bars = []
        for i, w in enumerate(ws):
            d = date.fromisoformat(w["date"]); h = max(6, int(92 * w["minutes"] / mx)) if w["minutes"] else 6; is_t = d == today()
            st = M.start(f"bar{i}", h); col = P["gold"] if w["minutes"] else alpha(P["text"], .10)
            bar = ft.Container(width=22, height=st, border_radius=8, animate=anim(750, EASE),
                               gradient=ft.LinearGradient(begin=ft.alignment.top_center, end=ft.alignment.bottom_center, colors=[P["gold"], P["amber"]]) if w["minutes"] else None,
                               bgcolor=None if w["minutes"] else col)
            if st != h:
                def grow(b=bar, h=h): b.height = h; b.update()
                M.after(grow, .02)
            bars.append(ft.Column([txt(fa(w["minutes"]) if w["minutes"] else "", 10, color="muted"), ft.Container(bar, height=96, alignment=ft.alignment.bottom_center),
                txt(J.WEEKDAY_SHORT[d.weekday()], 11, ft.FontWeight.W_800 if is_t else None, "gold" if is_t else "muted")], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True))
        week_total = sum(w["minutes"] for w in ws)
        weekly = card(ft.Column([ft.Row([ft.Row([ibadge(ic("BAR_CHART"), "gold", 28, radius=9), txt("۷ روز اخیر", 14, ft.FontWeight.W_700)], spacing=8), txt(f"{fmt_minutes(week_total)} مطالعه", 12, color="gold")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                 ft.Row(bars, vertical_alignment=ft.CrossAxisAlignment.END)], spacing=10))

        # نقشهٔ گرمایی ۵ هفته
        weeks, counts = store.heatmap(5); cols = []
        for wi, wk in enumerate(weeks):
            cells = []
            for d in wk:
                n = counts.get(d.isoformat(), 0)
                bg = "transparent" if d > today() else alpha(P["text"], .08) if n == 0 else alpha(P["gold"], .35 if n == 1 else .65 if n == 2 else 1)
                cells.append(ft.Container(width=17, height=17, border_radius=5, bgcolor=bg, border=ft.border.all(1.5, P["gold"]) if d == today() else None))
            col = ft.Column(cells, spacing=4)
            if M.animate:
                col.opacity = 0; col.animate_opacity = anim(450)
                def show(c=col): c.opacity = 1; c.update()
                M.after(show, .05)
            cols.append(col)
        heat = card(ft.Column([ft.Row([ibadge(ic("GRID_VIEW"), "gold", 28, radius=9), txt("نقشهٔ پیوستگی ۵ هفته", 14, ft.FontWeight.W_700)], spacing=8), ft.Row(cols, alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                               txt("هر خانه یک روز است؛ هرچه پررنگ‌تر، فعالیت بیشتر", 11, color="muted")], spacing=10))

        have = store.unlocked(); ach = []
        for aid, t, d, e, _ in ACHIEVEMENTS:
            ok = aid in have; icon, col = ACHIEVEMENT_ICONS.get(aid, ("EMOJI_EVENTS", "gold"))
            badge = ibadge(ic(icon), col, 46, filled=True, radius=16) if ok else ibadge(ic("LOCK", "outlined"), "muted", 46, radius=16)
            ach.append(ft.Container(card(ft.Column([badge, txt(t, 11, ft.FontWeight.W_700, "gold" if ok else "muted", text_align=ft.TextAlign.CENTER)], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                pad=10, bg=None if ok else alpha(P["card"], .45), on_click=lambda e, t=t, d=d: snack(f"{t}: {d}"), shadow=ok), col=4))

        stages = store.roadmap(); first = next((i for i, x in enumerate(stages) if x[2] < x[3]), len(stages)); tl = []
        for i, (name, rule, have_n, need) in enumerate(stages):
            ok = have_n >= need; act = i == first
            icon, col = ("CHECK_CIRCLE", "green") if ok else ("FLAG_CIRCLE" if act else "LOCK", "gold" if act else "muted")
            tl.append(card(ft.Row([ibadge(ic(icon, "rounded" if ok or act else "outlined"), col, 42, filled=act, radius=14), ft.Column([txt(name, 14, ft.FontWeight.W_700), txt(rule, 12, color="muted"),
                pbar(min(have_n, need) / need, col, 6, off=146, key=f"road{i}"), txt(f"{fa(min(have_n, need))} از {fa(need)}", 11, color=col)], spacing=6, expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                bg=None if (ok or act) else alpha(P["card"], .5), margin=ft.margin.only(bottom=8), shadow=act, border=ft.border.all(1.2, alpha(P["gold"], .55)) if act else None))
        return [title("پیشرفت", "آمار واقعی از اطلاعات ثبت‌شده"), countdown, grid, weekly, heat,
                section("دستاوردها", txt(f"{fa(len(have))} از {fa(len(ACHIEVEMENTS))}", 12, color="muted"), ic("EMOJI_EVENTS")), ft.ResponsiveRow(ach, spacing=8, run_spacing=8),
                section("نقشه مسیر", None, ic("ROUTE")), *tl, spacer()]

    def set_exam():
        dfield, get, _ = jdate_field("تاریخ آزمون", store.pref("exam_date") or (today() + timedelta(days=60)).isoformat()); holder = {}
        def clear(e): store.setpref("exam_date", ""); page.close(holder["d"]); render()
        def save(): store.setpref("exam_date", get()); render()
        holder["d"] = dialog("تاریخ آزمون", [dfield, ft.TextButton("حذف تاریخ آزمون", on_click=clear, style=ft.ButtonStyle(color=P["red"]))], save, icon="EVENT_AVAILABLE")
    def set_goal():
        f = field("هدفت چیست؟ (مثلاً قبولی در مدرسه نمونه)", store.pref("goal"))
        dialog("هدف من", [f], lambda: (store.setpref("goal", f.value.strip()), render()), icon="FLAG")

    # ================= یادداشت‌ها =================
    def note_form(row=None):
        t = field("عنوان", row["title"] if row else ""); b = field("متن یادداشت", row["body"] if row else "", multiline=True, min_lines=6, max_lines=10)
        tg = field("برچسب‌ها (با ویرگول جدا کن)", "، ".join(store.note_tag_names(row["id"])) if row else "")
        def save():
            if not (t.value.strip() or b.value.strip()): snack("عنوان یا متن را وارد کن", False); return False
            tags = [x for x in tg.value.replace("،", ",").split(",")]
            store.save_note(t.value.strip(), b.value, tags, row["id"] if row else None); render()
        dialog("ویرایش یادداشت" if row else "یادداشت جدید", [t, b, tg], save, icon="STICKY_NOTE_2")

    def event_form():
        t = field("عنوان (اختیاری)"); b = field("توضیحات", multiline=True, min_lines=2); h = time_field("ساعت (HH:MM)", datetime.now().strftime("%H:%M"))
        dfield, get, _ = jdate_field("تاریخ", S["day"])
        def save():
            time_s = norm_time(h.value)
            if not time_s: snack("ساعت نامعتبر است (مثلاً ۰۸:۳۰)", False); return False
            store.run("INSERT INTO day_events(title,body,date,time) VALUES(?,?,?,?)", (t.value, b.value, get(), time_s)); render()
        dialog("اتفاق جدید", [t, b, dfield, h], save, icon="EVENT_NOTE")

    def page_notes():
        seg_b = ft.SegmentedButton(selected={str(S["notes_tab"])}, allow_multiple_selection=False, on_change=lambda e: (S.update(notes_tab=int(list(e.control.selected)[0])), render()),
                                   segments=[ft.Segment(value="0", label=txt("یادداشت‌ها", 13), icon=ft.Icon(ic("STICKY_NOTE_2", "outlined"))),
                                             ft.Segment(value="1", label=txt("اتفاقات روز", 13), icon=ft.Icon(ic("TODAY", "outlined")))])
        out = [title("یادداشت‌ها"), seg_b]
        if S["notes_tab"] == 0:
            results = ft.Column(spacing=0)
            def note_cards():
                rows = store.search_notes(S["q"], S["tag"]); cs = []
                for r in rows:
                    pinned = bool(r["pinned"])
                    pin = ft.IconButton(ic("PUSH_PIN") if pinned else ic("PUSH_PIN", "outlined"), icon_color=P["gold"] if pinned else P["muted"],
                                        on_click=lambda e, x=r: (store.run("UPDATE notes SET pinned=? WHERE id=?", (1 - x["pinned"], x["id"])), render()))
                    dele = ft.IconButton(ic("DELETE", "outlined"), icon_color=P["muted"], on_click=lambda e, i=r["id"]: confirm("حذف", "این یادداشت حذف شود؟", lambda: (store.run("DELETE FROM notes WHERE id=?", (i,)), render())))
                    tags = store.note_tag_names(r["id"])
                    cs.append(card(ft.Column([ft.Row([txt(r["title"] or "(بدون عنوان)", 15, ft.FontWeight.W_700, expand=True), pin, dele], spacing=0),
                        txt(r["body"][:140], 13, color="muted", max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row([chip("#" + x, "blue") for x in tags], spacing=6, wrap=True) if tags else ft.Container(height=0),
                        ft.Row([ft.Icon(ic("SCHEDULE"), size=12, color=P["muted"]), txt(J.fmt(r["updated_at"][:10]) + " • " + fa(r["updated_at"][11:16]), 11, color="muted")], spacing=4)], spacing=6),
                        on_click=lambda e, x=r: note_form(x), margin=ft.margin.only(bottom=8), tint="gold" if pinned else None))
                return cs or [empty(ic("EDIT_NOTE"), "یادداشتی پیدا نشد")]
            results.controls = note_cards()
            def search(e):                      # فقط نتایج به‌روز می‌شوند، فیلد جست‌وجو و فوکوسش دست‌نخورده می‌ماند
                S["q"] = e.control.value; results.controls = note_cards(); results.update()
            out.append(field("جست‌وجو…", S["q"], prefix_icon=ic("SEARCH"), on_change=search))
            tags = store.all_tags()
            if tags:
                out.append(ft.Row([chip("همه", "gold", on_click=lambda e: (S.update(tag=None), render()), solid=S["tag"] is None),
                                   *[chip("#" + t["name"], "gold", on_click=lambda e, n=t["name"]: (S.update(tag=n), render()), solid=S["tag"] == t["name"]) for t in tags]], spacing=6, scroll=ft.ScrollMode.AUTO))
            out.append(results)
        else:
            rows = store.all("SELECT * FROM day_events ORDER BY date DESC,time")
            for r in rows:
                out.append(card(ft.Row([ft.Container(ft.Column([txt(fa(r["time"]), 14, ft.FontWeight.W_800, "gold"), txt(J.fmt(r["date"], "short"), 11, color="muted")], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER), width=62),
                    ft.Container(width=1, height=36, bgcolor=alpha(P["line"], .12)),
                    ft.Column([txt(r["title"] or "اتفاق", 14, ft.FontWeight.W_600), txt(r["body"], 12, color="muted")], spacing=2, expand=True),
                    ft.IconButton(ic("DELETE", "outlined"), icon_color=P["muted"], on_click=lambda e, i=r["id"]: (store.run("DELETE FROM day_events WHERE id=?", (i,)), render()))], spacing=8), margin=ft.margin.only(bottom=8)))
            if not rows: out.append(empty(ic("EVENT_NOTE"), "هنوز اتفاقی ثبت نکردی"))
        return out + [spacer()]

    # ================= مرور =================
    def subject_form():
        f = field("نام درس", autofocus=True)
        def save():
            if not f.value.strip(): f.error_text = "الزامی است"; f.update(); return False
            try: store.run("INSERT INTO subjects(name) VALUES(?)", (f.value.strip(),))
            except sqlite3.IntegrityError: snack("این درس از قبل وجود دارد", False); return False
            render()
        dialog("درس جدید", [f], save, icon="MENU_BOOK")

    def topic_form(row=None):
        subs = store.all("SELECT * FROM subjects ORDER BY name")
        if not subs: snack("ابتدا یک درس بساز", False); return
        dsub = dd(str(row["subject_id"] if row else subs[0]["id"]), [(str(s["id"]), s["name"]) for s in subs])
        ch, nm = field("فصل", row["chapter"] if row else ""), field("نام مبحث", row["name"] if row else "")
        nt = field("یادداشت درس", row["notes"] if row else "", multiline=True); ms = field("اشتباهات رایج", row["mistakes"] if row else "", multiline=True)
        def save():
            if not nm.value.strip(): nm.error_text = "الزامی است"; nm.update(); return False
            if row: store.run("UPDATE topics SET subject_id=?,chapter=?,name=?,notes=?,mistakes=? WHERE id=?", (int(dsub.value), ch.value, nm.value.strip(), nt.value, ms.value, row["id"]))
            else: store.run("INSERT INTO topics(subject_id,chapter,name,notes,mistakes) VALUES(?,?,?,?,?)", (int(dsub.value), ch.value, nm.value.strip(), nt.value, ms.value))
            render()
        dialog("ویرایش مبحث" if row else "مبحث جدید", [dsub, ch, nm, nt, ms], save, icon="LIBRARY_BOOKS")

    def log_form(topic_id=None):
        tps = store.all("SELECT t.*,s.name subject FROM topics t JOIN subjects s ON s.id=t.subject_id ORDER BY s.name,t.name")
        if not tps: snack("ابتدا درس و مبحث بساز", False); return
        dtop = dd(str(topic_id or tps[0]["id"]), [(str(t["id"]), f"{t['subject']} — {t['name']}") for t in tps])
        kind = seg("practice", list(KINDS.items()))
        tot, cor = num_field("تعداد سؤال", "10", expand=True), num_field("پاسخ صحیح", "8", expand=True)
        sec = num_field("زمان کل (ثانیه، اختیاری)"); dfield, get, _ = jdate_field("تاریخ", today().isoformat())
        def save():
            try:
                total, correct = int(J.en(tot.value)), int(J.en(cor.value)); seconds = int(J.en(sec.value)) if sec.value.strip() else None
                if total < 1 or correct < 0 or correct > total: raise ValueError()
            except Exception: snack("تعداد سؤال و پاسخ صحیح را بررسی کن", False); return False
            store.add_log(int(dtop.value), list(kind.selected)[0], total, correct, seconds, get())
            snack(f"ثبت شد • {fa(round(100 * correct / total))}٪ درست"); render(); after_action()
        dialog("ثبت فعالیت آموزشی", [dtop, kind, ft.Row([tot, cor], spacing=8), sec, dfield], save, "ثبت", icon="PLAYLIST_ADD_CHECK")

    CAP = 10
    def page_review():
        out = [title("مرور و یادگیری", "مرور فاصله‌دار: هرچه بهتر بدانی، دیرتر یادآوری می‌شود"),
               ft.Row([btn("ثبت فعالیت", lambda e: log_form(), ic("PLAYLIST_ADD_CHECK")), btn("درس", lambda e: subject_form(), ic("ADD"), False), btn("مبحث", lambda e: topic_form(), ic("ADD"), False)], spacing=8, wrap=True)]
        due = store.due_topics()
        if due:
            out.append(section(f"سررسید مرور ({fa(len(due))})", None, ic("ALARM")))
            for t in due[:6]:
                late = (today() - date.fromisoformat(t["next_review"])).days if t["next_review"] else 0
                out.append(card(ft.Row([ibadge(ic("ALARM"), "gold", 38), ft.Column([txt(t["name"], 14, ft.FontWeight.W_600), txt(f"{t['subject']}" + (f" • {fa(late)} روز تأخیر" if late > 0 else ""), 11, color="muted")], spacing=2, expand=True),
                    chip("ثبت مرور", "gold", ic("EDIT_NOTE"), on_click=lambda e, i=t["id"]: log_form(i))], spacing=10), pad=12, tint="gold", margin=ft.margin.only(bottom=6), shadow=False, radius=22))
        subs = store.subject_summary()
        if subs: out.append(section("درس‌ها", None, ic("MENU_BOOK")))
        for s in subs:
            tps = store.all("SELECT * FROM topics WHERE subject_id=? ORDER BY chapter,name", (s["id"],)); tiles = []
            more = len(tps) - CAP if (len(tps) > CAP and s["id"] not in S["subs_open"]) else 0      # درس‌های بزرگ: اول فقط CAP مبحث (سریع‌تر)، بقیه با یک لمس
            for t in (tps[:CAP] if more else tps):
                nm, col = STATUS[t["status"]]
                menu = [ft.PopupMenuItem(text=n, on_click=lambda e, i=t["id"], k=k: (store.set_topic_status(i, k), render())) for k, (n, _) in enumerate(STATUS)] + \
                       [ft.PopupMenuItem(text="ویرایش مبحث", icon=ic("EDIT", "outlined"), on_click=lambda e, x=t: topic_form(x)),
                        ft.PopupMenuItem(text="حذف مبحث", icon=ic("DELETE", "outlined"), on_click=lambda e, i=t["id"]: confirm("حذف مبحث", "مبحث و تمام ثبت‌هایش حذف شود؟", lambda: (store.run("DELETE FROM topics WHERE id=?", (i,)), render())))]
                nxt = ("مرور بعدی: " + J.fmt(t["next_review"])) if t["next_review"] else "هنوز مرور نشده"
                tiles.append(ft.ListTile(title=txt(t["name"], 14), subtitle=txt((t["chapter"] + " • " if t["chapter"] else "") + nxt, 11, color="muted"),
                                         leading=ft.Container(width=8, height=8, border_radius=4, bgcolor=P[col]),
                                         trailing=ft.PopupMenuButton(content=chip(nm, col), items=menu), on_click=lambda e, i=t["id"]: log_form(i), dense=True))
            if more: tiles.append(chip(f"نمایش {fa(more)} مبحث دیگر", "blue", ic("EXPAND_MORE"), on_click=lambda e, i=s["id"]: (S["subs_open"].add(i), render())))
            elif len(tps) > CAP: tiles.append(chip("نمایش کمتر", "muted", ic("EXPAND_LESS"), on_click=lambda e, i=s["id"]: (S["subs_open"].discard(i), render())))
            acc = s["acc"]
            head = ft.Row([ibadge(ic("MENU_BOOK"), "gold", 34, radius=11), txt(s["name"], 16, ft.FontWeight.W_700, expand=True),
                           chip(f"{fa(round(acc * 100))}٪ دقت", "green" if acc >= .8 else "gold" if acc >= .5 else "red", ic("TRACK_CHANGES")) if acc is not None else chip(f"{fa(s['topics'])} مبحث", "muted"),
                           ft.PopupMenuButton(icon=ic("MORE_VERT"), icon_color=P["muted"], items=[ft.PopupMenuItem(text="حذف درس", icon=ic("DELETE", "outlined"),
                               on_click=lambda e, i=s["id"]: confirm("حذف درس", "درس با همهٔ مبحث‌ها و ثبت‌هایش حذف شود؟", lambda: (store.run("DELETE FROM subjects WHERE id=?", (i,)), render())))])], spacing=8)
            prog = [pbar(s["mastered"] / s["topics"], "green", 6, off=72, key=f"sub{s['id']}"), txt(f"{fa(s['mastered'])} از {fa(s['topics'])} مبحث مسلط", 11, color="muted")] if s["topics"] else []
            out.append(card(ft.Column([head, *prog, *(tiles or [txt("هنوز مبحثی ندارد", 12, color="muted")])], spacing=6), margin=ft.margin.only(bottom=10)))
        if not subs: out.append(empty(ic("SCHOOL"), "اول یک درس بساز، بعد مبحث‌هایش را اضافه کن"))
        logs = store.all("SELECT q.*,s.name subject,t.name topic FROM quiz_logs q JOIN topics t ON t.id=q.topic_id JOIN subjects s ON s.id=t.subject_id ORDER BY q.date DESC,q.id DESC LIMIT 15")
        if logs:
            out.append(section("آخرین ثبت‌ها", None, ic("HISTORY")))
            for i, r in enumerate(logs):
                pct = r["correct"] / r["total"]
                out.append(card(ft.Row([ring(pct, 44, 5, "green" if pct >= .8 else "gold", key=f"log{r['id']}", center=txt(fa(round(pct * 100)), 11, ft.FontWeight.W_800)),
                    ft.Column([txt(f"{r['subject']} — {r['topic']}", 13, ft.FontWeight.W_600), txt(f"{KINDS.get(r['kind'], r['kind'])} • {J.fmt(r['date'])}", 11, color="muted")], spacing=2, expand=True),
                    txt(f"{fa(r['correct'])}/{fa(r['total'])}", 14, ft.FontWeight.W_800, "gold")], spacing=12), pad=12, margin=ft.margin.only(bottom=6), radius=20))
        return out + [spacer()]

    # ================= تنظیمات =================
    def page_settings():
        def theme(e): store.setpref("theme", "dark" if e.control.value else "light"); apply_theme(); build_chrome(); render()
        def set_pref(key, label, opts):
            cur = str(store.pref(key)); s = seg(cur, [(o, fa(o)) for o in opts])
            dialog(label, [s], lambda: (store.setpref(key, list(s.selected)[0]), render()), icon="TUNE")
        def do_restore(text):
            try: store.restore_text(text)
            except Exception as ex: log_error("بازیابی", ex); snack(f"بازیابی انجام نشد: {ex}", False); return
            snack("بازیابی انجام شد"); apply_theme(); build_chrome(); render()
        def save_as(e):
            text, name = store.backup_text(), store.export_filename()
            def done(ev):
                path = getattr(ev, "path", None)
                if not path: return                                   # انصراف
                try:
                    if not os.path.exists(path) or os.path.getsize(path) == 0:
                        with open(path, "w", encoding="utf-8") as f: f.write(text)
                    snack("پشتیبان ذخیره شد")
                except OSError as ex: log_error("ذخیرهٔ پشتیبان", ex); snack("ذخیره در این مکان ممکن نشد؛ «کپی پشتیبان» را امتحان کن", False)
            fp.on_result = done
            try:
                try: fp.save_file(dialog_title="ذخیرهٔ پشتیبان", file_name=name, allowed_extensions=["json"], src_bytes=text.encode("utf-8"))
                except TypeError: fp.save_file(dialog_title="ذخیرهٔ پشتیبان", file_name=name, allowed_extensions=["json"])
            except Exception as ex: log_error("save_file", ex); snack("انتخاب مکان در این دستگاه ممکن نشد؛ «کپی پشتیبان» را امتحان کن", False)
        def pick_restore(e):
            def done(ev):
                files = getattr(ev, "files", None)
                if not files: return
                try:
                    with open(files[0].path, encoding="utf-8") as f: text = f.read()
                except Exception as ex: log_error("خواندن فایل پشتیبان", ex); snack("خواندن فایل ممکن نشد؛ از «بازیابی از متن» استفاده کن", False); return
                confirm("بازیابی", "اطلاعات فعلی با این پشتیبان جایگزین می‌شود (از وضعیت فعلی یک نسخهٔ امن گرفته می‌شود). ادامه می‌دهی؟", lambda: do_restore(text))
            fp.on_result = done
            try: fp.pick_files(dialog_title="انتخاب فایل پشتیبان", allowed_extensions=["json"], allow_multiple=False)
            except Exception as ex: log_error("pick_files", ex); snack("انتخاب فایل در این دستگاه ممکن نشد؛ از «بازیابی از متن» استفاده کن", False)
        def auto_list(e):
            items = store.list_backups()[:8]
            if not items: snack("هنوز پشتیبان خودکاری ساخته نشده", False); return
            holder = {}; rows = []
            for pth, mt in items:
                nm = os.path.basename(pth); kind = "پیش از بازیابی" if nm.startswith("pre-restore") else "پیش از پاک‌سازی" if nm.startswith("pre-wipe") else "خودکار روزانه"
                when = datetime.fromtimestamp(mt)
                def pick(ev, pth=pth):
                    page.close(holder["d"])
                    def go():
                        try:
                            with open(pth, encoding="utf-8") as f: text = f.read()
                            do_restore(text)
                        except OSError as ex: log_error("خواندن پشتیبان خودکار", ex); snack("خواندن پشتیبان ممکن نشد", False)
                    confirm("بازیابی", "اطلاعات فعلی با این نسخه جایگزین می‌شود. ادامه می‌دهی؟", go)
                rows.append(card(ft.Row([ibadge(ic("HISTORY"), "blue", 34, radius=11), ft.Column([txt(kind, 13, ft.FontWeight.W_600), txt(f"{J.fmt(when.date())} • {fa(when.strftime('%H:%M'))}", 11, color="muted")], spacing=0, expand=True),
                                         ft.Icon(ic("RESTORE"), size=18, color=P["muted"])], spacing=10), pad=10, radius=18, shadow=False, on_click=pick))
            holder["d"] = dialog("پشتیبان‌های خودکار", [txt("برای بازگردانی روی یک نسخه بزن. هر روز یک نسخه خودکار ساخته می‌شود.", 12, color="muted"), *rows], lambda: True, "بستن", cancel=False, icon="HISTORY")
        def export(e):
            p = os.path.join(data_dir(), store.export_filename())
            try: store.backup(p)
            except Exception as ex: snack(str(ex), False); return
            try: page.set_clipboard(store.backup_text()); extra = "متن پشتیبان در کلیپ‌بورد هم کپی شد؛ می‌توانی در یادداشت‌های گوشی یا پیام‌رسان ذخیره‌اش کنی."
            except Exception: extra = ""
            dialog("پشتیبان ذخیره شد", [ft.Text(p, size=12, selectable=True, color=P["muted"]), txt(extra, 12, color="muted")], lambda: True, "باشه", cancel=False, icon="CLOUD_DONE")
        def restore_text(e):
            f = field("متن پشتیبان را اینجا بچسبان", multiline=True, min_lines=5, max_lines=8)
            def go():
                try: store.restore_text(f.value)
                except Exception as ex: snack(f"متن معتبر نیست: {ex}", False); return False
                snack("بازیابی انجام شد"); apply_theme(); build_chrome(); render()
            dialog("بازیابی از متن", [f], go, "بازیابی", icon="CONTENT_PASTE")
        def wipe(e):
            confirm("تأیید اول", "تمام اطلاعات برای همیشه پاک می‌شود. ادامه؟",
                    lambda: confirm("تأیید نهایی", "این کار قابل بازگشت نیست. مطمئنی؟", lambda: (store.clear_all(), snack("پاک شد؛ نسخهٔ امن در «پشتیبان‌های خودکار» است"), render())))
        def row(icon, t, sub, trailing, col="gold"):
            return card(ft.Row([ibadge(ic(icon), col, 40), ft.Column([txt(t, 14, ft.FontWeight.W_600), txt(sub, 11, color="muted")], spacing=2, expand=True), trailing], spacing=12), margin=ft.margin.only(bottom=8), radius=22)
        go_ = lambda f: ft.IconButton(ic("CHEVRON_LEFT"), icon_color=P["muted"], on_click=f)
        exam = store.pref("exam_date")
        logo = ft.Container(ft.Column([ibadge(ic("AUTO_AWESOME"), "gold", 52, filled=True, radius=18), txt("Get Better", 15, ft.FontWeight.W_800),
                            txt(f"نسخه {fa(VERSION)} • کاملاً آفلاین • هیچ اطلاعاتی از دستگاه خارج نمی‌شود", 11, color="muted", text_align=ft.TextAlign.CENTER)],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6), alignment=ft.alignment.center, padding=20)
        return [ft.Row([ft.IconButton(ic("ARROW_FORWARD"), on_click=lambda e: (S.update(tab=S["nav"]), render())), title("تنظیمات")]),
                section("برنامه‌ریزی", None, ic("EVENT_NOTE")),
                row("EVENT_REPEAT", "روتین‌ها و نماز", "کارهای همیشگی که هر روز خودکار اضافه می‌شوند", go_(lambda e: (S.update(tab=6), render()))),
                row("FLAG", "هدف من", store.pref("goal") or "هنوز تعیین نشده", go_(lambda e: set_goal())),
                row("EVENT_AVAILABLE", "تاریخ آزمون", J.fmt(exam) if exam else "هنوز تعیین نشده", go_(lambda e: set_exam())),
                row("TASK_ALT", "هدف روزانه", f"{fa(store.pref_int('daily_goal', 3))} مأموریت در روز", go_(lambda e: set_pref("daily_goal", "هدف روزانه (مأموریت)", [1, 2, 3, 4, 5, 6]))),
                row("TIMER", "طول تمرکز", f"{fa(store.pref_int('pomodoro', 25))} دقیقه تمرکز، {fa(store.pref_int('break', 5))} دقیقه استراحت",
                    go_(lambda e: (set_pref("pomodoro", "طول هر دور تمرکز (دقیقه)", [15, 25, 45, 50])))),
                row("COFFEE", "طول استراحت", f"{fa(store.pref_int('break', 5))} دقیقه", go_(lambda e: set_pref("break", "طول استراحت (دقیقه)", [5, 10, 15]))),
                section("ظاهر", None, ic("PALETTE")),
                row("DARK_MODE", "حالت تیره", "انتخاب تو روی همین دستگاه ذخیره می‌شود", ft.Switch(value=ui.is_dark(), active_color=P["gold"], on_change=theme), "violet"),
                section("داده‌ها", None, ic("STORAGE")),
                row("CLOUD_UPLOAD", "ذخیرهٔ پشتیبان", "انتخاب مکان دلخواه (حافظه، فایل‌ها، ابر)", go_(save_as), "blue"),
                row("CLOUD_DOWNLOAD", "بازیابی از فایل", "انتخاب فایل پشتیبان", go_(pick_restore), "blue"),
                row("HISTORY", "پشتیبان‌های خودکار", f"{fa(len(store.list_backups()))} نسخه • روزانه خودکار ساخته می‌شود", go_(auto_list), "blue"),
                row("CONTENT_COPY", "کپی پشتیبان", "فایل داخلی + متن در کلیپ‌بورد", go_(export), "blue"),
                row("CONTENT_PASTE", "بازیابی از متن", "متن کپی‌شدهٔ پشتیبان را بچسبان", go_(restore_text), "blue"),
                row("DELETE_FOREVER", "پاک‌سازی کامل", "با دو تأیید؛ پیش از آن نسخهٔ امن گرفته می‌شود", go_(wipe), "red"),
                section("برنامه", None, ic("INFO")),
                row("PRIVACY_TIP", "درباره، حریم خصوصی و راهنما", f"نسخه {fa(VERSION)}", go_(lambda e: (S.update(tab=7), render())), "green"),
                logo, spacer(20)]

    # ================= قاب اصلی =================
    body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)
    pages = [page_home, page_week, page_progress, page_notes, page_review]
    NAVC, FAB = [], {}
    SHOWN = {"k": None}

    def goto(i):
        S.update(tab=i, nav=i); render()

    def paint_nav():
        cur = S["nav"]
        for i, n in enumerate(NAVC):
            sel = i == cur
            n["box"].bgcolor = P["gold"] if sel else "#00000000"
            n["box"].padding = ft.padding.symmetric(horizontal=14 if sel else 11, vertical=10)
            n["icon"].name = ic(NAV[i][1]) if sel else ic(NAV[i][1], "outlined")
            n["icon"].color = P["on_accent"] if sel else P["muted"]
            n["lab"].width = NAV[i][2] if sel else 0
            n["lab"].opacity = 1 if sel else 0
            n["box"].scale = 1.0 if sel else .96

    def reveal(ctrls):
        """ورود پلکانی: هر بخش از پایین کمی بالا می‌آید و محو‌شدگی‌اش برطرف می‌شود."""
        jobs = []
        for i, c in enumerate(ctrls):
            c.opacity = 0; c.offset = ft.Offset(0, .08); c.animate_opacity = anim(420, EASE); c.animate_offset = anim(480, EASE)
            def show(c=c): c.opacity = 1; c.offset = ft.Offset(0, 0); c.update()
            jobs.append((.04 if i else 0, show))
        M.jobs = jobs + M.jobs          # اول ورود بخش‌ها، بعد پر شدن نوار و حلقه‌ها
        M.base = .04                                  # بخش‌های بالای صفحه همزمان با ورودشان شروع به پر شدن می‌کنند

    def render():
        M.reset(); update_width()
        try: body.controls = page_settings() if S["tab"] == 5 else page_routines() if S["tab"] == 6 else page_about() if S["tab"] == 7 else pages[S["tab"]]()
        except Exception as ex:
            traceback.print_exc(); body.controls = [empty(ic("ERROR"), f"مشکلی پیش آمد: {ex}")]
        key = (S["tab"], S["notes_tab"], S["day"] if S["tab"] == 0 else S["wk"] if S["tab"] == 1 else "")
        fresh = SHOWN["k"] != key
        M.animate = fresh
        if fresh:
            SHOWN["k"] = key; M.prev.clear(); reveal(body.controls[:10])
        paint_nav()
        if FAB:
            vis = S["tab"] in (0, 1, 3, 4, 6)
            FAB["c"].visible = vis
            if vis and fresh:
                FAB["c"].scale = .6
                def pop(): FAB["c"].scale = 1; FAB["c"].update()
                M.after(pop, .08)
        page.update(); M.flush()

    def on_fab(e):
        def week_add():
            ws = J.week_start(date.fromisoformat(S["wk"]))
            mission_form(day=(today() if ws <= today() <= ws + timedelta(days=6) else ws).isoformat())
        {0: mission_form, 1: week_add, 3: (lambda: note_form() if S["notes_tab"] == 0 else event_form()), 4: log_form, 6: routine_form}.get(S["tab"], mission_form)()

    # ---- دکمهٔ بازگشت اندروید: پشتهٔ دو view (نگهبان + اصلی) تا Back به on_view_pop برسد؛ با یک view، اندروید مستقیم خارج می‌شود
    VIEWS = {"guard": None, "main": None, "exit_armed": False}
    def mount(root):
        try:
            if VIEWS["main"] is None:
                VIEWS["guard"] = ft.View(route="/guard", controls=[], padding=0, spacing=0)
                VIEWS["main"] = ft.View(route="/", controls=[root], padding=0, spacing=0, bgcolor=P["bg"])
                page.views.clear(); page.views.append(VIEWS["guard"]); page.views.append(VIEWS["main"])
            else:
                VIEWS["main"].controls = [root]; VIEWS["main"].bgcolor = P["bg"]
            return
        except Exception as ex:
            VIEWS["main"] = None; log_error("پشتهٔ view", ex)
        page.controls.clear(); page.add(root)         # جایگزین: همان رفتار قبلی (Back مستقیم خارج می‌شود)

    def set_guard(on):
        """نگهبان را برمی‌دارد/برمی‌گرداند. بدون نگهبان، Back بعدی طبق رفتار پیش‌فرض اندروید از برنامه خارج می‌شود."""
        try:
            has = VIEWS["guard"] in page.views
            if on and not has: page.views.insert(0, VIEWS["guard"]); page.update()
            elif not on and has: page.views.remove(VIEWS["guard"]); page.update()
        except Exception as ex: log_error("نگهبان Back", ex)

    def go_back():
        """منطق Back: زیرصفحه → صفحهٔ پیشین • تب دیگر → امروز • امروز → دوبار Back برای خروج. خروجی: آیا برنامه خودش مصرف کرد."""
        t = S["tab"]
        if t == 7: S["tab"] = 5
        elif t == 5: S["tab"] = S["nav"]
        elif t == 6: S.update(tab=1, nav=1)
        elif t != 0: S.update(tab=0, nav=0)
        else: return False
        render(); return True

    def on_view_pop(e=None):
        if go_back(): VIEWS["exit_armed"] = False; return
        # در صفحهٔ امروز: بار اول فقط هشدار؛ نگهبان برداشته می‌شود تا Back دوم (طی ۳ ثانیه) خروج واقعی باشد
        snack("برای خروج، یک بار دیگر «بازگشت» را بزن"); set_guard(False); VIEWS["exit_armed"] = True
        def rearm():
            if VIEWS["exit_armed"]: VIEWS["exit_armed"] = False; set_guard(True)
        threading.Timer(3.0, rearm).start()
    try: page.on_view_pop = on_view_pop
    except Exception as ex: log_error("on_view_pop", ex)

    def build_chrome():
        NAVC.clear()
        dark = ui.is_dark()
        # پس‌زمینهٔ شفقی: گرادیان + دو هالهٔ نور
        aurora = ft.Container(left=0, right=0, top=0, bottom=0, gradient=ft.LinearGradient(begin=ft.alignment.top_center, end=ft.alignment.bottom_center, colors=[P["bg"], P["bg2"]]))
        halo1 = glow(380, "gold", .07 if dark else .12, right=-140, top=-120)
        halo2 = glow(420, "violet", .10 if dark else .10, left=-190, bottom=40)
        logo = ibadge(ic("AUTO_AWESOME"), "gold", 36, filled=True, radius=12); pulse(logo, 1.06)
        top = ft.Row([ft.Row([logo, ft.Column([txt("Get Better", 18, ft.FontWeight.W_800), txt("بهتر شو، هر روز", 10, color="muted")], spacing=0)], spacing=10, expand=True),
                      ft.Container(ft.IconButton(ic("SETTINGS", "outlined"), icon_color=P["muted"], tooltip="تنظیمات", on_click=lambda e: (S.update(tab=5), render())), border_radius=16,
                                   bgcolor=alpha(P["card"], .8), border=ft.border.all(1, alpha(P["line"], .08)))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        content = ft.Container(ft.Column([ft.Container(top, padding=ft.padding.only(top=6)), body], spacing=4, expand=True), padding=ft.padding.symmetric(horizontal=18), left=0, right=0, top=0, bottom=0)

        # نوار پایین شناور: فقط تب فعال برچسب دارد؛ عرض و رنگ با انیمیشن عوض می‌شوند
        items = []
        for i, (label, icon, w) in enumerate(NAV):
            icn = ft.Icon(ic(icon, "outlined"), size=23, color=P["muted"])
            lab = ft.Container(txt(label, 12, ft.FontWeight.W_800, P["on_accent"], no_wrap=True), width=0, opacity=0, animate=anim(320, EASE), animate_opacity=anim(260), clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
            box = ft.Container(ft.Row([icn, lab], spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER), border_radius=22, animate=anim(320, EASE), animate_scale=anim(300, BACK),
                               ink=True, on_click=lambda e, i=i: goto(i), data=("nav", i), tooltip=NAV[i][0], padding=ft.padding.symmetric(horizontal=11, vertical=10))
            NAVC.append({"box": box, "icon": icn, "lab": lab}); items.append(box)
        nav = ft.Container(ft.Row(items, alignment=ft.MainAxisAlignment.SPACE_AROUND), left=14, right=14, bottom=12, height=66, padding=ft.padding.symmetric(horizontal=8, vertical=8), border_radius=30,
                           bgcolor=alpha(P["card"], .94), border=ft.border.all(1, alpha(P["line"], .10)),
                           shadow=ft.BoxShadow(blur_radius=30, spread_radius=-6, color=alpha("#000000", .55 if dark else .18), offset=ft.Offset(0, 12)))

        fab = ft.Container(ft.Row([ft.Icon(ic("ADD"), size=24, color=P["on_accent"]), txt("افزودن", 14, ft.FontWeight.W_800, P["on_accent"])], spacing=6, tight=True),
                           padding=ft.padding.symmetric(horizontal=18, vertical=14), border_radius=22, left=20, bottom=92, ink=True, on_click=on_fab, data="fab",
                           gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[P["gold"], P["amber"]]),
                           shadow=ft.BoxShadow(blur_radius=24, spread_radius=-2, color=alpha(P["gold"], .55), offset=ft.Offset(0, 8)), animate_scale=anim(380, BACK), scale=1)
        FAB["c"] = fab
        page.bgcolor = P["bg"]
        mount(ft.Stack([aurora, halo1, halo2, ft.SafeArea(ft.Stack([content, nav, fab], expand=True), expand=True)], expand=True))
        paint_nav()

    fp = ft.FilePicker()
    try: page.overlay.append(fp)
    except Exception as ex: log_error("FilePicker", ex)

    # ================= معرفی اولیه =================
    def onboarding():
        """سه گام: خوش‌آمدگویی • هدف و تاریخ آزمون • هدف روزانه. هر لحظه می‌شود رد کرد."""
        st = {"i": 0}
        goal = field("هدفت چیست؟ (مثلاً قبولی در مدرسه نمونه)", store.pref("goal"))
        has_exam = bool(store.pref("exam_date"))
        use_exam = ft.Switch(label="تاریخ آزمون دارم", value=has_exam, active_color=P["gold"])
        dfield, get_exam, _ = jdate_field("تاریخ آزمون", store.pref("exam_date") or (today() + timedelta(days=90)).isoformat())
        dfield.visible = has_exam
        def exam_toggle(e): dfield.visible = bool(use_exam.value); dfield.update()
        use_exam.on_change = exam_toggle
        dgoal = seg(store.pref_int("daily_goal", 3), [(n, fa(n)) for n in (1, 2, 3, 4, 5)])
        def bullet(icon, col, t): return ft.Row([ibadge(ic(icon), col, 34, radius=11), txt(t, 13, expand=True)], spacing=10)
        s1 = ft.Column([ft.Row([ibadge(ic("AUTO_AWESOME"), "gold", 64, filled=True, radius=22)], alignment=ft.MainAxisAlignment.CENTER),
                        txt("به Get Better خوش آمدی", 20, ft.FontWeight.W_800, text_align=ft.TextAlign.CENTER),
                        txt("همراه روزانهٔ تو برای آمادگی آزمون", 12, color="muted", text_align=ft.TextAlign.CENTER),
                        bullet("CHECKLIST", "gold", "کارها، ریزه‌کارها و برنامهٔ هفتگی جلالی"),
                        bullet("AUTO_STORIES", "blue", "مرور فاصله‌دار تا چیزی از یادت نرود"),
                        bullet("LOCAL_FIRE_DEPARTMENT", "red", "امتیاز، سطح و استریک برای انگیزه"),
                        bullet("LOCK", "green", "همه‌چیز آفلاین و فقط روی گوشی خودت می‌ماند")], spacing=12, tight=True)
        s2 = ft.Column([txt("هدف و آزمونت را بگو تا شمارش معکوس و مسیر پیشرفتت ساخته شود. بعداً در تنظیمات قابل تغییر است.", 12, color="muted"), goal, use_exam, dfield], spacing=12, tight=True, visible=False)
        s3 = ft.Column([txt("هر روز چند کار را هدف می‌گیری؟", 14, ft.FontWeight.W_700), dgoal,
                        txt("پیشنهاد: با عدد کوچک شروع کن و هر هفته کمی بالاتر ببر؛ پیوستگی از شدت مهم‌تر است.", 12, color="muted")], spacing=12, tight=True, visible=False)
        steps = [s1, s2, s3]; holder = {}
        nxt = ft.FilledButton("بعدی", style=ft.ButtonStyle(bgcolor=P["gold"], color=P["on_accent"], shape=ft.RoundedRectangleBorder(radius=14)))
        back = ft.TextButton("قبلی", visible=False, style=ft.ButtonStyle(color=P["muted"]))
        skip = ft.TextButton("رد کردن", style=ft.ButtonStyle(color=P["muted"]))
        def paint():
            for i, c in enumerate(steps): c.visible = i == st["i"]
            back.visible = st["i"] > 0; nxt.text = "شروع" if st["i"] == len(steps) - 1 else "بعدی"
            try: holder["d"].update()
            except Exception: pass
        def finish(save):
            if save:
                store.setpref("goal", goal.value.strip()[:120]); store.setpref("exam_date", get_exam() if use_exam.value else "")
                store.setpref("daily_goal", list(dgoal.selected)[0])
            store.setpref("onboarded", "1"); page.close(holder["d"]); render()
        def go_next(e):
            if st["i"] >= len(steps) - 1: finish(True)
            else: st["i"] += 1; paint()
        def go_back(e): st["i"] = max(0, st["i"] - 1); paint()
        nxt.on_click, back.on_click, skip.on_click = go_next, go_back, lambda e: finish(False)
        holder["d"] = ft.AlertDialog(modal=True, bgcolor=P["card"], shape=ft.RoundedRectangleBorder(radius=28), inset_padding=ft.padding.symmetric(horizontal=16, vertical=24),
                                     content=ft.Container(ft.Column(steps, tight=True, scroll=ft.ScrollMode.AUTO), width=340), actions=[skip, back, nxt])
        page.open(holder["d"])

    # ================= درباره، حریم خصوصی و راهنما =================
    def page_about():
        def point(icon, col, t, sub=None):
            return card(ft.Row([ibadge(ic(icon), col, 38, radius=13), ft.Column([txt(t, 13, ft.FontWeight.W_700)] + ([txt(sub, 11, color="muted")] if sub else []), spacing=2, expand=True)], spacing=12),
                        pad=12, radius=20, shadow=False, margin=ft.margin.only(bottom=6))
        def copy_log(e):
            log = read_error_log()
            if not log: snack("گزارش خطایی ثبت نشده؛ همه‌چیز سالم است"); return
            try: page.set_clipboard(log); snack("گزارش خطا کپی شد؛ برای پشتیبانی بفرست")
            except Exception: snack("کپی انجام نشد", False)
        def clear_log(e): clear_error_log(); snack("گزارش خطا پاک شد"); render()
        logo = card(ft.Column([ibadge(ic("AUTO_AWESOME"), "gold", 64, filled=True, radius=22), txt(meta.APP_NAME, 20, ft.FontWeight.W_800),
                               txt(meta.TAGLINE, 12, color="muted"),
                               chip(f"نسخه {fa(VERSION)} • ساخت {fa(meta.BUILD_NUMBER)}", "gold", ic("VERIFIED"))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    grad=True, pad=20, radius=28)
        out = [ft.Row([ft.IconButton(ic("ARROW_FORWARD"), tooltip="بازگشت", on_click=lambda e: (S.update(tab=5), render())), title("درباره و حریم خصوصی")]), logo,
               section("حریم خصوصی", None, ic("PRIVACY_TIP")),
               point("PHONELINK_LOCK", "green", "همه‌چیز فقط روی گوشی تو", "کارها، یادداشت‌ها و آمار در حافظهٔ همین دستگاه ذخیره می‌شوند."),
               point("PERSON_OFF", "blue", "بدون حساب کاربری", "ثبت‌نام، ورود یا شمارهٔ تلفن لازم نیست."),
               point("WIFI_OFF", "violet", "کاملاً آفلاین", "برنامه هیچ داده‌ای نمی‌فرستد و هیچ ردیاب، تبلیغ یا تحلیل‌گری ندارد."),
               point("BACKUP", "gold", "پشتیبان دست خودت است", "پشتیبان را خودت می‌سازی و خودت نگه می‌داری. با حذف برنامه، داده‌ها هم پاک می‌شوند؛ پیش از آن پشتیبان بگیر."),
               section("راهنمای سریع", None, ic("LIGHTBULB")),
               point("BOLT", "gold", "امتیاز و سطح", "هر کار انجام‌شده XP می‌دهد؛ کارهای طولانی‌تر و مهم‌تر امتیاز بیشتری دارند."),
               point("AUTO_STORIES", "blue", "مرور فاصله‌دار", "اگر مرور را ≥۸۰٪ درست بزنی یک جعبه جلو می‌روی؛ وگرنه فردا دوباره مرور می‌شود."),
               point("CENTER_FOCUS_STRONG", "green", "حالت تمرکز", "تایمر با ساعت واقعی می‌شمارد؛ خاموش‌شدن صفحه یا رفتن به برنامهٔ دیگر مشکلی ایجاد نمی‌کند. فقط اگر سیستم خود برنامه را ببندد، دور نیمه‌کاره ذخیره نمی‌شود."),
               section("اطلاعات فنی", None, ic("INFO")),
               card(ft.Column([txt(f"ساختار دیتابیس: نسخهٔ {fa(store.schema_version())}", 12, color="muted"), txt(f"نسخهٔ پشتیبان: {fa(2)}", 12, color="muted"),
                               ft.Row([chip("کپی گزارش خطا", "blue", ic("BUG_REPORT"), on_click=copy_log), chip("پاک کردن گزارش", "muted", ic("DELETE", "outlined"), on_click=clear_log)], spacing=8, wrap=True)], spacing=8), pad=14, radius=20, shadow=False),
               section("سپاس‌ها", None, ic("FAVORITE")),
               txt("ساخته‌شده با Flet (Apache-2.0)، فونت وزیرمتن (OFL) و آیکون‌های Material (Apache-2.0).", 11, color="muted")]
        if meta.SUPPORT_EMAIL: out.append(point("MAIL", "gold", "پشتیبانی", meta.SUPPORT_EMAIL))
        out.append(btn("مرور دوبارهٔ معرفی برنامه", lambda e: onboarding(), ic("PLAY_CIRCLE"), False))
        return out + [spacer()]

    apply_theme(); build_chrome(); render()
    try: store.maybe_daily_backup()                 # بعد از اولین نمایش صفحه، تا شروع برنامه معطل پشتیبان‌گیری نماند
    except Exception as ex: log_error("پشتیبان خودکار", ex)
    if store.recovery: snack("دیتابیس آسیب‌دیده بود و از آخرین پشتیبان بازیابی شد" if store.recovery == "restored" else "دیتابیس آسیب‌دیده بود؛ برنامه از نو شروع شد (فایل قبلی نگه داشته شد)", store.recovery == "restored")
    if store.pref("onboarded") != "1":
        if store.is_fresh(): onboarding()
        else: store.setpref("onboarded", "1")        # کاربر قدیمی که از نسخهٔ قبل ارتقا داده است

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
