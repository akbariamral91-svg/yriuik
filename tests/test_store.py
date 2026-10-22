# -*- coding: utf-8 -*-
import glob, os, sys, json, sqlite3, tempfile, threading, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from store import Store, level_for_xp, xp_threshold, xp_for_mission, BOX_DAYS, PRAYERS, WEEK_ORDER
import jalali
import store as store_mod

T = date.today()
def D(n=0): return (T + timedelta(days=n)).isoformat()

class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.s = Store(os.path.join(self.dir.name, "t.db"))
    def tearDown(self): self.s.db.close(); self.dir.cleanup()
    def topic(self, name="الف"):
        sid = self.s.run("INSERT OR IGNORE INTO subjects(name) VALUES('ریاضی')")
        sid = self.s.one("SELECT id FROM subjects WHERE name='ریاضی'")["id"]
        return self.s.run("INSERT INTO topics(subject_id,name) VALUES(?,?)", (sid, name))

class TestMissions(Base):
    def test_xp_and_levels(self):
        self.assertEqual(xp_for_mission(30, 1), 21); self.assertEqual(xp_for_mission(1000, 2), 100)
        self.assertEqual(level_for_xp(0), 1); self.assertEqual(level_for_xp(100), 2); self.assertEqual(level_for_xp(xp_threshold(5)), 5)
    def test_no_double_xp(self):
        m = self.s.save_mission("الف", "", 30, 1, D())
        self.assertTrue(self.s.toggle_mission(m)); x = self.s.xp()
        self.assertFalse(self.s.toggle_mission(m)); self.assertTrue(self.s.toggle_mission(m))
        self.assertEqual(self.s.xp(), x)
    def test_repeat_spawns_once(self):
        m = self.s.save_mission("ورزش", "", 20, 0, D(), repeat="daily")
        self.s.toggle_mission(m); self.s.toggle_mission(m); self.s.toggle_mission(m)
        self.assertEqual(self.s.one("SELECT COUNT(*) n FROM missions WHERE title='ورزش'")["n"], 2)
        w = self.s.save_mission("هفتگی", "", 20, 0, D(), repeat="weekly"); self.s.toggle_mission(w)
        self.assertEqual(self.s.one("SELECT date FROM missions WHERE title='هفتگی' AND id!=?", (w,))["date"], D(7))
    def test_overdue_and_move(self):
        self.s.save_mission("قدیمی", "", 20, 0, D(-3)); self.s.save_mission("امروز", "", 20, 0, D())
        self.assertEqual(len(self.s.overdue()), 1); self.s.move_overdue_to_today()
        self.assertEqual(len(self.s.overdue()), 0); self.assertEqual(len(self.s.today_missions()), 2)
    def test_day_load(self):
        a = self.s.save_mission("a", "", 20, 0, D()); self.s.save_mission("b", "", 20, 0, D()); self.s.toggle_mission(a)
        self.assertEqual(self.s.day_load(T, 3)[D()], (2, 1)); self.assertEqual(self.s.day_load(T, 3)[D(2)], (0, 0))
    def test_toggle_missing(self): self.assertFalse(self.s.toggle_mission(999))

class TestStreaks(Base):
    def log_day(self, n):
        m = self.s.save_mission("x", "", 10, 0, D(n)); self.s.toggle_mission(m)
        self.s.run("UPDATE missions SET completed_at=? WHERE id=?", (f"{D(n)}T10:00:00", m))
    def test_current_and_best(self):
        for n in (-1, -2, -3, -10, -11): self.log_day(n)
        self.assertEqual(self.s.streaks(), (3, 3))      # امروز فعالیت ندارد؛ از دیروز می‌شمارد
        self.log_day(0); self.assertEqual(self.s.streaks()[0], 4)
    def test_broken_streak(self):
        self.log_day(-5); self.assertEqual(self.s.streaks(), (0, 1))
    def test_empty(self): self.assertEqual(self.s.streaks(), (0, 0))
    def test_focus_counts_as_activity(self):
        self.s.add_focus(None, 600); self.assertEqual(self.s.streaks()[0], 1)

class TestReview(Base):
    def test_leitner_progression(self):
        t = self.topic(); get = lambda: self.s.one("SELECT * FROM topics WHERE id=?", (t,))
        self.assertEqual(BOX_DAYS, [1, 3, 7, 30, 90])
        self.s.add_log(t, "practice", 10, 9, None, D())            # اولین ثبت → ۱ روز
        self.assertEqual((get()["status"], get()["box"], get()["next_review"]), (1, 0, D(1)))
        for box, days in ((1, 3), (2, 7), (3, 30), (4, 90), (4, 90)):  # هر بار درست → جعبهٔ بعد؛ سقف ۳ ماه
            self.s.add_log(t, "review", 10, 9, None, D()); self.assertEqual((get()["box"], get()["next_review"]), (box, D(days)))
        self.s.add_log(t, "review", 10, 7, None, D())              # بلد نبود → برگشت به جعبهٔ اول
        self.assertEqual((get()["box"], get()["next_review"]), (0, D(1)))
    def test_first_poor_log_box_zero(self):
        t = self.topic(); self.s.add_log(t, "practice", 10, 2, None, D())
        self.assertEqual(self.s.one("SELECT box FROM topics WHERE id=?", (t,))["box"], 0)
    def test_mastery_and_demotion(self):
        t = self.topic()
        self.s.add_log(t, "exam", 10, 9, None, D(-2)); self.s.add_log(t, "exam", 10, 8, None, D(-1))
        self.assertEqual(self.s.one("SELECT status FROM topics WHERE id=?", (t,))["status"], 3)
        self.s.add_log(t, "exam", 10, 3, None, D()); self.assertEqual(self.s.one("SELECT status FROM topics WHERE id=?", (t,))["status"], 2)
    def test_same_day_no_mastery(self):
        t = self.topic(); self.s.add_log(t, "exam", 10, 9, None, D()); self.s.add_log(t, "exam", 10, 9, None, D())
        self.assertNotEqual(self.s.one("SELECT status FROM topics WHERE id=?", (t,))["status"], 3)
    def test_due_and_plan(self):
        t = self.topic("ضعیف"); self.s.add_log(t, "practice", 10, 3, None, D(-5))   # next = D(-4)
        due = self.s.due_topics(); self.assertEqual([x["id"] for x in due], [t])
        plan = self.s.suggest_plan(); self.assertEqual(len(plan), 1); self.assertEqual(plan[0]["priority"], 2)
        self.s.apply_plan(plan); self.assertEqual(self.s.suggest_plan(), [])           # تکراری پیشنهاد نمی‌شود
        self.assertEqual(self.s.today_missions()[0]["topic_id"], t)
    def test_unstarted_not_due(self):
        self.topic(); self.assertEqual(self.s.due_topics(), [])
    def test_subject_summary(self):
        t = self.topic(); self.s.add_log(t, "practice", 10, 5, None, D())
        r = self.s.subject_summary()[0]; self.assertEqual((r["topics"], r["mastered"], r["acc"]), (1, 0, .5))
    def test_cascade_delete(self):
        t = self.topic(); self.s.add_log(t, "practice", 10, 5, None, D())
        self.s.run("DELETE FROM subjects"); self.assertEqual(self.s.one("SELECT COUNT(*) n FROM quiz_logs")["n"], 0)

class TestAchievementsStats(Base):
    def test_unlock_once(self):
        m = self.s.save_mission("a", "", 30, 1, D()); self.s.toggle_mission(m)
        new = {a[0] for a in self.s.check_achievements()}; self.assertIn("first_step", new)
        self.assertEqual(self.s.check_achievements(), [])
    def test_focus_achievement(self):
        self.s.add_focus(None, 5 * 3600); self.assertIn("focus_5h", {a[0] for a in self.s.check_achievements()})
    def test_week_series_and_heatmap(self):
        m = self.s.save_mission("a", "", 30, 1, D()); self.s.toggle_mission(m); self.s.add_focus(m, 1800)
        w = self.s.week_series(); self.assertEqual(len(w), 7); self.assertEqual(w[-1]["done"], 1); self.assertEqual(w[-1]["minutes"], 30)
        grid, counts = self.s.heatmap(); self.assertEqual((len(grid), len(grid[0])), (5, 7)); self.assertGreaterEqual(counts[D()], 1)
        self.assertEqual(grid[0][0].weekday(), 5)   # شنبه
    def test_focus_updates_mission(self):
        m = self.s.save_mission("a", "", 30, 1, D()); self.s.add_focus(m, 100); self.s.add_focus(m, 0)
        self.assertEqual(self.s.one("SELECT spent_seconds s FROM missions WHERE id=?", (m,))["s"], 100)

class TestNotesPrefs(Base):
    def test_tags_and_search(self):
        n = self.s.save_note("فیزیک", "قانون نیوتن", ["مهم", " مهم ", "امتحان"]); self.s.save_note("ریاضی", "مشتق")
        self.assertEqual(self.s.note_tag_names(n), ["امتحان", "مهم"])
        self.assertEqual(len(self.s.search_notes("نیوتن")), 1); self.assertEqual(len(self.s.search_notes("", "مهم")), 1)
        self.s.set_note_tags(n, []); self.assertEqual(self.s.all_tags(), [])   # برچسب یتیم پاک می‌شود
    def test_prefs_defaults(self):
        self.assertEqual(self.s.pref_int("pomodoro"), 25); self.s.setpref("pomodoro", "50"); self.assertEqual(self.s.pref_int("pomodoro"), 50)
        self.assertEqual(self.s.pref("nothing"), "")

class TestBackup(Base):
    def populate(self):
        t = self.topic(); self.s.add_log(t, "exam", 10, 9, None, D()); m = self.s.save_mission("a", "ریاضی", 30, 1, D(), topic_id=t)
        self.s.toggle_mission(m); self.s.save_note("n", "b", ["x"]); self.s.setpref("goal", "هدف"); self.s.add_focus(m, 60)
    def test_roundtrip(self):
        self.populate(); text = self.s.backup_text(); before = self.s.stats()
        self.s.clear_all(); self.assertEqual(self.s.stats()["missions"], 0)
        self.s.restore_text(text); self.assertEqual(self.s.stats(), before); self.assertEqual(self.s.pref("goal"), "هدف")
        self.assertEqual(self.s.note_tag_names(1), ["x"])
    def test_file_roundtrip(self):
        self.populate(); p = os.path.join(self.dir.name, "b.json"); self.s.backup(p); self.s.clear_all(); self.s.restore(p)
        self.assertEqual(self.s.stats()["done"], 1)
    def test_invalid_restore_is_atomic(self):
        self.populate()
        for bad in ("not json", "[]", '{"data": {"x": 1}}'):
            with self.assertRaises(Exception): self.s.restore_text(bad)
        bad = json.dumps({"data": {"missions": [], "topics": [{"id": 1, "subject_id": 999, "name": "x"}]}})
        with self.assertRaises(sqlite3.IntegrityError): self.s.restore_text(bad)
        self.assertEqual(self.s.stats()["done"], 1)          # هیچ چیز از دست نرفته
    def test_old_backup_and_unknown_columns(self):
        old = {"app": "Get Better", "version": 1, "data": {"missions": [{"id": 1, "title": "قدیمی", "date": D(), "xp": 10, "future_col": 5}]}}
        self.s.restore_text(json.dumps(old)); self.assertEqual(self.s.today_missions()[0]["title"], "قدیمی")
    def test_clear_keeps_theme(self):
        self.s.setpref("theme", "light"); self.populate(); self.s.clear_all(); self.assertEqual(self.s.pref("theme"), "light")

class TestRoutinesWeekly(Base):
    def rows(self, d, **kw): return self.s.missions_on(d)
    def test_prayers_seeded_once(self):
        self.assertEqual([r["key"] for r in self.s.routines()], [k for k, _, _ in PRAYERS])
        self.s.delete_routine(self.s.routines()[0]["id"]); path = self.s.path; self.s.db.close()
        self.s = Store(path); self.assertEqual(len(self.s.routines()), 4)          # حذف‌شده برنگشت
    def test_daily_generation_idempotent_and_reset(self):
        self.s.ensure_day(T); self.s.ensure_day(T); self.assertEqual(len(self.rows(T)), 5)
        for r in self.rows(T)[:2]: self.s.toggle_mission(r["id"])
        self.s.ensure_day(D(1)); tom = self.rows(D(1))
        self.assertEqual((len(tom), sum(r["done"] for r in tom)), (5, 0))               # فردا دوباره از صفر
        self.assertEqual(sum(r["done"] for r in self.rows(T)), 2)                       # امروز دست‌نخورده
    def test_prayer_xp_small_and_not_in_stats(self):
        self.s.ensure_day(T); r = self.rows(T)[0]; self.s.toggle_mission(r["id"])
        self.assertEqual(self.s.xp(), 5); st = self.s.stats()
        self.assertEqual((st["done"], st["missions"], st["streak"]), (0, 0, 0))         # روتین آمار مطالعه را شلوغ نمی‌کند
        self.assertEqual(self.s.overdue(), []); self.assertEqual(self.s.day_load(T, 1)[D()], (0, 0))
    def test_past_days_not_generated(self):
        self.s.ensure_day(D(-1)); self.assertEqual(self.rows(D(-1)), [])
    def test_custom_routine_days_and_sync(self):
        rid = self.s.save_routine("کلاس ریاضی", "task", 90, "16:00", [T.weekday()])
        self.s.ensure_range(T, 7); inst = [r for r in self.s.week_plan(T) if any(x["title"] == "کلاس ریاضی" for x in x_rows(r))]
        self.assertEqual(len(inst), 1)                                                   # فقط یک روز از هفته
        self.s.save_routine("کلاس فیزیک", "task", 60, "17:30", [T.weekday()], rid)
        m = [r for r in self.rows(T) if r["routine_id"] == rid][0]; self.assertEqual((m["title"], m["time"], m["minutes"]), ("کلاس فیزیک", "17:30", 60))
        self.s.set_routine_active(rid, False); self.assertEqual([r for r in self.rows(T) if r["routine_id"] == rid], [])
        self.s.set_routine_active(rid, True); self.s.ensure_day(T); self.assertEqual(len([r for r in self.rows(T) if r["routine_id"] == rid]), 1)
    def test_delete_keeps_history(self):
        self.s.ensure_day(T); r = self.rows(T)[0]; self.s.toggle_mission(r["id"]); self.s.delete_routine(r["routine_id"])
        self.assertEqual(len(self.rows(T)), 5); self.assertEqual(len(self.s.routines()), 4)
        self.assertTrue(self.s.one("SELECT done FROM missions WHERE id=?", (r["id"],))["done"])   # تاریخچهٔ انجام‌شده می‌ماند
    def test_task_vs_chore(self):
        t = self.s.save_mission("کلاس", "", 90, 1, D(), kind="task", time="16:00"); c = self.s.save_mission("آب دادن گل", "", 45, 2, D(), kind="chore", time="09:00")
        a, b = [self.s.one("SELECT * FROM missions WHERE id=?", (i,)) for i in (t, c)]
        self.assertEqual((a["kind"], a["time"], a["minutes"]), ("task", "16:00", 90)); self.assertEqual((b["kind"], b["time"], b["minutes"], b["xp"]), ("chore", "", 0, 5))
        self.s.save_mission("بی‌ساعت", "", 0, 0, D())                                    # مدت و ساعت اختیاری است
        order = [r["title"] for r in self.rows(D())]; self.assertEqual(order[0], "کلاس")  # دارای ساعت اول
    def test_week_plan_and_copy(self):
        from jalali import week_start
        ws = week_start(T); self.s.save_mission("الف", "", 30, 1, ws + timedelta(days=2), kind="task", time="10:00"); self.s.save_mission("ب", "", 0, 1, ws, kind="chore")
        plan = self.s.week_plan(ws); self.assertEqual((len(plan), plan[0]["date"], plan[0]["total"], plan[2]["total"]), (7, ws, 1, 1))
        self.assertEqual(self.s.copy_week(ws, ws + timedelta(days=7)), 2); self.assertEqual(self.s.copy_week(ws, ws + timedelta(days=7)), 0)   # تکراری کپی نمی‌شود
        self.assertEqual(self.s.one("SELECT time FROM missions WHERE title='الف' AND date=?", ((ws + timedelta(days=9)).isoformat(),))["time"], "10:00")
    def test_clear_reseeds_and_backup_has_routines(self):
        self.s.save_routine("ورزش", "chore", 0, "", WEEK_ORDER); text = self.s.backup_text(); self.s.clear_all()
        self.assertEqual(len(self.s.routines()), 5); self.s.restore_text(text); self.assertEqual(len(self.s.routines()), 6)

def x_rows(day): return day["tasks"] + day["routine"]

class TestMigration(unittest.TestCase):
    def test_old_db_upgrades(self):
        d = tempfile.TemporaryDirectory(); p = os.path.join(d.name, "old.db"); c = sqlite3.connect(p)
        c.executescript("""CREATE TABLE missions(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,subject TEXT DEFAULT '',description TEXT DEFAULT '',minutes INTEGER DEFAULT 30,priority INTEGER DEFAULT 1,done INTEGER DEFAULT 0,xp INTEGER DEFAULT 10,date TEXT NOT NULL,note TEXT DEFAULT '',spent_seconds INTEGER DEFAULT 0,completed_at TEXT,icon TEXT);
        CREATE TABLE subjects(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE);
        CREATE TABLE topics(id INTEGER PRIMARY KEY AUTOINCREMENT,subject_id INTEGER NOT NULL,chapter TEXT DEFAULT '',name TEXT NOT NULL,notes TEXT DEFAULT '',mistakes TEXT DEFAULT '',status INTEGER DEFAULT 0,next_review TEXT);
        INSERT INTO missions(title,date) VALUES('قدیمی','2025-01-01');""")
        c.commit(); c.close()
        s = Store(p); self.assertIn("repeat", s._columns("missions")); self.assertIn("box", s._columns("topics"))
        self.assertEqual(s.one("SELECT title FROM missions")["title"], "قدیمی"); s.db.close(); d.cleanup()

class TestRobustness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.path = os.path.join(self.dir.name, "t.db"); os.environ["FLET_APP_STORAGE_DATA"] = self.dir.name
    def tearDown(self): self.dir.cleanup()
    def test_schema_version_stamped(self):
        s = Store(self.path); self.assertEqual(s.schema_version(), store_mod.SCHEMA_VERSION); s.close()
    def test_corrupt_db_without_backup_starts_fresh(self):
        with open(self.path, "wb") as f: f.write(b"this is not a sqlite database at all" * 50)
        s = Store(self.path); self.assertEqual(s.recovery, "fresh"); self.assertEqual(s.xp(), 0)
        self.assertTrue(glob.glob(self.path + ".corrupt-*")); s.save_mission("بعد از خرابی", "", 10, 1, D()); s.close()   # فایل خراب برای بررسی نگه داشته می‌شود
    def test_corrupt_db_restores_from_latest_backup(self):
        s = Store(self.path); s.save_mission("مهم", "", 30, 1, D()); s.auto_backup("auto"); s.close()
        with open(self.path, "wb") as f: f.write(b"garbage" * 500)
        for ext in ("-wal", "-shm"):
            if os.path.exists(self.path + ext): os.remove(self.path + ext)
        s = Store(self.path); self.assertEqual(s.recovery, "restored"); self.assertEqual(s.one("SELECT title FROM missions WHERE routine_id IS NULL")["title"], "مهم"); s.close()
    def test_auto_backup_prunes_and_daily_once(self):
        s = Store(self.path); s.save_mission("الف", "", 30, 1, D())
        for _ in range(7): s.auto_backup("auto", keep=3)
        self.assertEqual(len(glob.glob(os.path.join(s.backups_dir(), "auto-*.json"))), 3)
        s2 = Store(os.path.join(self.dir.name, "other.db")); self.assertFalse(s2.maybe_daily_backup())      # بدون داده، پشتیبانی ساخته نمی‌شود
        self.assertTrue(s.maybe_daily_backup()); self.assertFalse(s.maybe_daily_backup()); s.close(); s2.close()
    def test_restore_snapshots_current_state_first(self):
        s = Store(self.path); s.save_mission("قدیمی", "", 30, 1, D()); text = s.backup_text()
        s.save_mission("جدید", "", 30, 1, D()); s.restore_text(text)
        self.assertEqual(s.one("SELECT COUNT(*) n FROM missions WHERE routine_id IS NULL")["n"], 1)
        snap = glob.glob(os.path.join(s.backups_dir(), "pre-restore-*.json")); self.assertEqual(len(snap), 1)
        s.restore(snap[0], snapshot=False); self.assertEqual(s.one("SELECT COUNT(*) n FROM missions WHERE routine_id IS NULL")["n"], 2); s.close()   # اشتباه قابل جبران است
    def test_clear_all_snapshots_and_keeps_onboarded(self):
        s = Store(self.path); s.save_mission("الف", "", 30, 1, D()); s.setpref("onboarded", "1"); s.clear_all()
        self.assertTrue(glob.glob(os.path.join(s.backups_dir(), "pre-wipe-*.json"))); self.assertEqual(s.pref("onboarded"), "1"); s.close()
    def test_invalid_restores_change_nothing(self):
        s = Store(self.path); s.save_mission("الف", "", 30, 1, D())
        for bad in ("نه JSON", "[1,2]", '{"data": {"missions": "x"}}', '{"data": {"missions": [1]}}', '{"version": 99, "data": {"missions": []}}', "{}"):
            with self.assertRaises(ValueError): s.restore_text(bad)
        self.assertEqual(s.one("SELECT COUNT(*) n FROM missions WHERE routine_id IS NULL")["n"], 1); s.close()
    def test_backup_write_is_atomic_and_dated_name(self):
        s = Store(self.path); out = os.path.join(self.dir.name, "x.json"); s.backup(out)
        self.assertTrue(os.path.exists(out)); self.assertFalse(os.path.exists(out + ".tmp")); self.assertRegex(s.export_filename(), r"^get_better_backup_\d{4}-\d{2}-\d{2}\.json$"); s.close()
    def test_usable_from_another_thread(self):          # Flet رویدادها را در رشته‌های دیگر اجرا می‌کند
        s = Store(self.path); box = {}
        def work():
            try: s.save_mission("رشته", "", 10, 1, D()); box["n"] = s.one("SELECT COUNT(*) n FROM missions WHERE routine_id IS NULL")["n"]
            except Exception as ex: box["err"] = ex
        t = threading.Thread(target=work); t.start(); t.join(); self.assertNotIn("err", box); self.assertEqual(box["n"], 1); s.close()
    def test_is_fresh(self):
        s = Store(self.path); self.assertTrue(s.is_fresh()); s.setpref("goal", "هدف"); self.assertFalse(s.is_fresh())
        s.setpref("goal", ""); s.save_mission("الف", "", 10, 1, D()); self.assertFalse(s.is_fresh()); s.close()
    def test_error_log_roundtrip_and_rotation(self):
        store_mod.clear_error_log(); self.assertEqual(store_mod.read_error_log(), "")
        try: raise ValueError("بوم")
        except ValueError as ex: store_mod.log_error("آزمایش", ex)
        log = store_mod.read_error_log(); self.assertIn("آزمایش", log); self.assertIn("ValueError", log)
        with open(os.path.join(self.dir.name, "errors.log"), "a", encoding="utf-8") as f: f.write("x" * 210_000)
        store_mod.log_error("بعد از چرخش"); self.assertTrue(os.path.exists(os.path.join(self.dir.name, "errors.log.1"))); self.assertIn("بعد از چرخش", store_mod.read_error_log())
        store_mod.clear_error_log(); self.assertEqual(store_mod.read_error_log(), "")


if __name__ == "__main__": unittest.main()
