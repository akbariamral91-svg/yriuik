# -*- coding: utf-8 -*-
"""دانلود فونت وزیرمتن (Regular / Medium / Bold) داخل assets/fonts با چند آینه (mirror) و اعتبارسنجی فایل TTF.
اگر همهٔ آینه‌ها ناموفق بودند با کد خروج ۱ تمام می‌شود تا ساخت انتشار بی‌صدا بدون فونت ادامه پیدا نکند."""
import os, sys, time, urllib.request

MIRRORS = (
    "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/",
    "https://github.com/rastikerdar/vazirmatn/raw/v33.003/fonts/ttf/",
    "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/",
    "https://cdn.jsdelivr.net/npm/vazirmatn@latest/fonts/ttf/",
)
NAMES = ("Vazirmatn-Regular.ttf", "Vazirmatn-Medium.ttf", "Vazirmatn-Bold.ttf")
DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
MIN_SIZE = 50_000
MAGIC = (b"\x00\x01\x00\x00", b"true", b"OTTO")      # امضای فایل‌های TTF/OTF

def valid(path):
    try:
        if os.path.getsize(path) < MIN_SIZE: return False
        with open(path, "rb") as f: return f.read(4) in MAGIC
    except OSError: return False

def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (get-better-build)"})
    with urllib.request.urlopen(req, timeout=60) as r: data = r.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f: f.write(data)
    os.replace(tmp, dest)

def fetch(name):
    dest = os.path.join(DEST_DIR, name)
    if valid(dest): print("از قبل هست:", dest); return True
    for rnd in range(1, 4):
        for base in MIRRORS:
            try:
                download(base + name, dest)
                if valid(dest): print("ذخیره شد:", dest, "←", base); return True
                raise OSError("فایل دانلودشده معتبر نیست")
            except Exception as ex:
                print(f"ناموفق ({name}) از {base}: {ex}", file=sys.stderr)
        time.sleep(3 * rnd)
    return False

if __name__ == "__main__":
    os.makedirs(DEST_DIR, exist_ok=True)
    ok = all([fetch(n) for n in NAMES])
    sys.exit(0 if ok else 1)
