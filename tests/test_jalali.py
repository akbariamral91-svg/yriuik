# -*- coding: utf-8 -*-
import os, sys, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jalali as j

class T(unittest.TestCase):
    def test_anchors(self):
        for g, s in {date(2026,10,19):(1405,7,27), date(2026,3,21):(1405,1,1), date(2025,3,21):(1404,1,1),
                     date(2025,3,20):(1403,12,30), date(2000,1,1):(1378,10,11), date(2026,9,22):(1405,6,31)}.items():
            self.assertEqual(j.to_jalali(g), s)
    def test_roundtrip_and_continuity(self):
        d, prev = date(2001, 3, 1), None
        while d < date(2045, 1, 1):
            cur = j.to_jalali(d); self.assertEqual(j.from_jalali(*cur), d)
            if prev: self.assertTrue(cur[2] == prev[2] + 1 or cur[2] == 1)
            prev = cur; d += timedelta(1)
    def test_leap_and_lengths(self):
        self.assertEqual([y for y in range(1399, 1411) if j.is_leap(y)], [1399, 1403, 1408])
        self.assertEqual((j.month_length(1403, 12), j.month_length(1404, 12), j.month_length(1404, 7), j.month_length(1404, 1)), (30, 29, 30, 31))
    def test_invalid(self):
        with self.assertRaises(ValueError): j.from_jalali(1404, 12, 30)
        self.assertIsNone(j.parse("بد")); self.assertIsNone(j.parse("1405/13/1"))
    def test_format_parse(self):
        d = date(2026, 10, 19)
        self.assertEqual(j.fmt(d), "۲۷ مهر ۱۴۰۵"); self.assertEqual(j.fmt(d, "full"), "دوشنبه ۲۷ مهر ۱۴۰۵"); self.assertEqual(j.fmt(d, "num"), "۱۴۰۵/۰۷/۲۷")
        self.assertEqual(j.parse("۱۴۰۵/۷/۲۷"), d); self.assertEqual(j.parse("1405-07-27"), d)
    def test_week_start(self):
        self.assertEqual(j.week_start(date(2026,10,19)), date(2026,10,17)); self.assertEqual(j.week_start(date(2026,10,17)), date(2026,10,17))
        self.assertEqual(j.week_start(date(2026,10,23)), date(2026,10,17))

if __name__ == "__main__": unittest.main()
