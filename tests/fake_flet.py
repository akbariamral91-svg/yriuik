# -*- coding: utf-8 -*-
"""شبیه‌ساز سبک Flet برای تست دودی رابط (بدون نیاز به نصب flet).
فقط ساختار درخت کنترل‌ها و منطق رویدادها را می‌سنجد، نه رندر واقعی یا سازگاری دقیق API."""
import sys, types

class Ctl:
    def __init__(self, *a, **kw):
        self._args = a; self.__dict__.update(kw)
        if type(self).__name__ == "Option" and a: self.key = a[0]; self.text = a[1] if len(a) > 1 else a[0]
        self.updates = 0
    def update(self): self.updates += 1
    def children(self):
        for k, v in list(self.__dict__.items()):
            if k.startswith("_"): continue
            if isinstance(v, Ctl): yield v
            elif isinstance(v, (list, tuple)):
                for x in v:
                    if isinstance(x, Ctl): yield x
        for a in self._args:
            if isinstance(a, Ctl): yield a
            elif isinstance(a, (list, tuple)):
                for x in a:
                    if isinstance(x, Ctl): yield x

class NS:
    def __getattr__(self, n): return n
class FnNS:
    def __getattr__(self, n): return lambda *a, **k: (n, a, tuple(sorted(k.items())))

_cache = {}
def _cls(n):
    if n not in _cache: _cache[n] = type(n, (Ctl,), {})
    return _cache[n]

class Colors:
    @staticmethod
    def with_opacity(a, c): return f"{c}@{a}"
    def __getattr__(self, n): return n

class Page(Ctl):
    def __init__(self):
        super().__init__(); self.window = Ctl(); self.controls = []; self.views = []; self.dialogs = []; self.snacks = []; self.clip = None; self.overlay = []
    def add(self, *c): self.controls += c
    def open(self, c):
        (self.snacks if type(c).__name__ == "SnackBar" else self.dialogs).append(c)
    def close(self, c):
        if c in self.dialogs: self.dialogs.remove(c)
    def update(self, *controls): self.updates += 1; self.batch = getattr(self, "batch", 0) + (1 if controls else 0)   # مثل Flet واقعی: update(*controls) یک پیام دسته‌ای است
    def set_clipboard(self, t): self.clip = t

_ENUMS = {"Icons", "FontWeight", "ThemeMode", "KeyboardType", "ScrollMode", "MainAxisAlignment", "CrossAxisAlignment", "TextAlign",
          "TextOverflow", "TextDecoration", "SnackBarBehavior", "AnimationCurve", "ClipBehavior", "NavigationBarLabelBehavior", "StrokeCap"}
mod = types.ModuleType("flet")
def _getattr(n):
    if n == "Page": return Page
    if n == "Colors": return Colors()
    if n in _ENUMS: return NS()
    if n in ("alignment", "padding", "margin", "border"): return FnNS()
    if n == "dropdown": return types.SimpleNamespace(Option=_cls("Option"))
    if n == "app": return lambda *a, **k: None
    if n[0].isupper(): return _cls(n)
    raise AttributeError(n)
mod.__getattr__ = _getattr
def install(): sys.modules["flet"] = mod

# ---- ابزار کاوش درخت ----
def walk(c):
    yield c
    for ch in c.children(): yield from walk(ch)
def find(root, cls=None, pred=lambda c: True):
    return [c for c in walk(root) if (cls is None or type(c).__name__ == cls) and pred(c)]
def text_of(c): return str(c._args[0]) if type(c).__name__ == "Text" and c._args else ""
def all_text(root): return " | ".join(t for t in (text_of(c) for c in walk(root)) if t)
def roots(page): return list(page.controls) + list(page.dialogs)
