# -*- coding: utf-8 -*-
"""تقویم جلالی (شمسی) بدون وابستگی خارجی.

الگوریتم از jalaali-js (چرخهٔ ۳۳ ساله) گرفته شده و با تاریخ‌های مرجع تست شده است.
تاریخ‌ها در دیتابیس همیشه میلادی ISO (YYYY-MM-DD) ذخیره می‌شوند و فقط هنگام نمایش جلالی می‌شوند.
"""
import math
from datetime import date, timedelta

_BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178]

MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
# پایتون: دوشنبه=۰ … یکشنبه=۶
WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
WEEKDAY_SHORT = ["د", "س", "چ", "پ", "ج", "ش", "ی"]

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def fa(value):
    """اعداد را فارسی می‌کند."""
    return str(value).translate(_FA)

def en(value):
    """ارقام فارسی/عربی را به لاتین برمی‌گرداند (برای پارس ورودی کاربر)."""
    return str(value).translate(_EN)

def _div(a, b): return int(a / b)
def _mod(a, b): return int(math.fmod(a, b))

def _jal_cal(jy):
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    if jy < jp or jy >= _BREAKS[-1]:
        raise ValueError("سال جلالی خارج از بازه پشتیبانی‌شده: %s" % jy)
    jump = 0
    for jm in _BREAKS[1:]:
        jump = jm - jp
        if jy < jm: break
        leap_j += _div(jump, 33) * 8 + _div(jump % 33, 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(n % 33 + 3, 4)
    if jump % 33 == 4 and jump - n == 4: leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6: n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1: leap = 4
    return leap, gy, march

def is_leap(jy): return _jal_cal(jy)[0] == 0

def month_length(jy, jm):
    if jm <= 6: return 31
    if jm <= 11: return 30
    return 30 if is_leap(jy) else 29

def to_jalali(d):
    """date میلادی → (سال، ماه، روز) جلالی."""
    jy = d.year - 621
    leap, gy, march = _jal_cal(jy)
    k = (d - date(gy, 3, march)).days
    if k >= 0:
        if k <= 185: return jy, 1 + k // 31, k % 31 + 1
        k -= 186
    else:
        jy -= 1
        leap, gy, march = _jal_cal(jy)
        k = (d - date(gy, 3, march)).days
        if k <= 185: return jy, 1 + k // 31, k % 31 + 1
        k -= 186
    return jy, 7 + k // 30, k % 30 + 1

def from_jalali(jy, jm, jd):
    """(سال، ماه، روز) جلالی → date میلادی."""
    if not (1 <= jm <= 12) or not (1 <= jd <= month_length(jy, jm)):
        raise ValueError("تاریخ جلالی نامعتبر")
    _, gy, march = _jal_cal(jy)
    return date(gy, 3, march) + timedelta(days=(jm - 1) * 31 - (jm // 7) * (jm - 7) + jd - 1)

def as_date(v):
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])

def fmt(v, style="long"):
    """نمایش جلالی با ارقام فارسی. style: long='۲۷ مهر ۱۴۰۵'، short='۰۷/۲۷'، full='دوشنبه ۲۷ مهر ۱۴۰۵'، num='۱۴۰۵/۰۷/۲۷'."""
    d = as_date(v); jy, jm, jd = to_jalali(d)
    if style == "short": return fa("%02d/%02d" % (jm, jd))
    if style == "num": return fa("%04d/%02d/%02d" % (jy, jm, jd))
    if style == "day": return fa(jd)
    if style == "month": return MONTHS[jm - 1]
    s = "%s %s %s" % (fa(jd), MONTHS[jm - 1], fa(jy))
    return "%s %s" % (WEEKDAYS[d.weekday()], s) if style == "full" else s

def parse(s):
    """'۱۴۰۵/۷/۲۷' یا '1405-07-27' → date میلادی؛ در صورت خطا None."""
    try:
        parts = [int(p) for p in en(s).replace("-", "/").split("/") if p.strip()]
        if len(parts) != 3: return None
        return from_jalali(*parts)
    except Exception:
        return None

def week_start(d):
    """شنبهٔ هفتهٔ شامل d."""
    return d - timedelta(days=(d.weekday() + 2) % 7)

def days_until(v, today=None):
    return (as_date(v) - (today or date.today())).days
