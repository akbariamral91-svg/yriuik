# -*- coding: utf-8 -*-
"""بررسی اطلاعاتی: همهٔ نام‌های ft.* و آیکون‌های استفاده‌شده باید در Flet نصب‌شده وجود داشته باشند.
تست‌های محلی از شبیه‌ساز استفاده می‌کنند؛ این اسکریپت در CI با Flet واقعی اجرا می‌شود. فقط هشدار می‌دهد، ساخت را متوقف نمی‌کند."""
import ast, os, re, sys
import flet as ft
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
missing = set()
for fn in ("main.py", "ui.py"):
    src = open(os.path.join(ROOT, fn), encoding="utf-8").read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Attribute):
            chain, cur = [], node
            while isinstance(cur, ast.Attribute): chain.append(cur.attr); cur = cur.value
            if isinstance(cur, ast.Name) and cur.id == "ft":
                obj = ft
                for a in reversed(chain):
                    if not hasattr(obj, a): missing.add("ft." + ".".join(reversed(chain))); break
                    obj = getattr(obj, a)
    for m in re.finditer(r'\bic\(\s*"([A-Z0-9_]+)"', src):
        if not hasattr(ft.Icons, m.group(1)) and not hasattr(ft.Icons, m.group(1) + "_ROUNDED"): missing.add("Icons." + m.group(1))
print("flet", getattr(ft, "__version__", "?"))
if missing:
    print("::warning::نام‌های ناموجود در Flet نصب‌شده:", ", ".join(sorted(missing))); print("MISSING:", sorted(missing))
else:
    print("همهٔ نام‌های Flet معتبرند ✅")
