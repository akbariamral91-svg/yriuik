# -*- coding: utf-8 -*-
"""ticker دسته‌ای انیمیشن: مقدار نهایی می‌رسد، پیام‌ها دسته‌ای‌اند و رندر جدید اجرای قبلی را باطل می‌کند."""
import os, sys, time, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_flet as F
F.install()
import ui

class FakePage:
    def __init__(self): self.calls = []
    def update(self, *c): self.calls.append(c)

class Box:
    def __init__(self): self.value = 0; self.n = 0
    def update(self): self.n += 1

class TestMotion(unittest.TestCase):
    def setUp(self): self.m = ui.Motion(); self.m.page = FakePage()
    def test_tween_reaches_final_and_batches(self):
        a, b = Box(), Box()
        def mk(box): return lambda v: setattr(box, "value", v)
        self.m.tween(mk(a), 0, 10, .2, ctrl=a); self.m.tween(mk(b), 0, 50, .2, ctrl=b)
        self.m.flush(); time.sleep(.7)
        self.assertEqual((a.value, b.value), (10, 50))
        self.assertTrue(self.m.page.calls and all(len(c) >= 1 for c in self.m.page.calls))
        self.assertTrue(any(len(c) == 2 for c in self.m.page.calls))        # هر دو کنترل در یک پیام
        self.assertEqual((a.n, b.n), (0, 0))                                   # بدون update تک‌تک
        self.assertLess(len(self.m.page.calls), 40)
    def test_set_at_runs_once_with_delay(self):
        x = Box(); hits = []
        self.m.set_at(x, lambda: hits.append(time.monotonic()), .15); t0 = time.monotonic()
        self.m.flush(); time.sleep(.5)
        self.assertEqual(len(hits), 1); self.assertGreaterEqual(hits[0] - t0, .15)
    def test_new_render_cancels_old(self):
        a = Box(); self.m.tween(lambda v: setattr(a, "value", v), 0, 10, .6, ctrl=a); self.m.flush(); time.sleep(.15)
        self.m.reset(); self.m.flush(); time.sleep(.8)                          # رندر تازه
        self.assertLess(a.value, 10)
    def test_ambient_updates_in_one_batch(self):
        a, b = Box(), Box()
        for c in (a, b): self.m.ambient(lambda tick, c=c: c)
        self.m.flush(); time.sleep(.3)
        self.assertTrue(any(len(c) == 2 for c in self.m.page.calls))
    def test_fallback_when_batch_fails(self):
        class Bad(FakePage):
            def update(self, *c): raise TypeError("no batch")
        self.m.page = Bad(); a = Box()
        self.m.tween(lambda v: setattr(a, "value", v), 0, 5, .1, ctrl=a); self.m.flush(); time.sleep(.5)
        self.assertEqual(a.value, 5); self.assertGreater(a.n, 0)

if __name__ == "__main__": unittest.main()
