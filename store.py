# -*- coding: utf-8 -*-
"""لایه داده و منطق Get Better (بدون وابستگی به UI).

ویژگی‌ها: XP و سطح، استریک، مرور فاصله‌دار (لایتنر)، تسلط مبحث، دستاوردها،
تایمر تمرکز، مأموریت‌های تکرارشونده، برنامهٔ هوشمند، آمار هفتگی و پشتیبان‌گیری.
"""
import sqlite3, json, os, glob, traceback
from datetime import date, datetime, timedelta
from jalali import fa  # noqa: F401  (برای سازگاری: from store import fa)

TABLES = ['routines', 'missions', 'xp_ledger', 'subjects', 'topics', 'quiz_logs', 'achievements',
          'notes', 'tags', 'note_tags', 'day_events', 'focus_sessions', 'settings']
BACKUP_VERSION = 2
SCHEMA_VERSION = 4                       # شمارهٔ نسخهٔ ساختار دیتابیس (PRAGMA user_version)
BOX_DAYS = [1, 3, 7, 30, 90]              # جعبه‌های لایتنر: ۱ روز، ۳ روز، ۱ هفته، ۱ ماه، ۳ ماه بعد
REPEATS = {"": "بدون تکرار", "daily": "هر روز", "weekly": "هر هفته"}
DEFAULTS = {"onboarded": "0", "last_auto_backup": "", "theme": "dark", "goal": "", "exam_date": "", "daily_goal": "3", "pomodoro": "25", "break": "5"}

LEVEL_TITLES = ["نوآموز", "کنجکاو", "کوشا", "پیگیر", "مصمم", "حرفه‌ای", "استاد", "نخبه", "افسانه"]

# نمازهای پنجگانه؛ خودکار به‌عنوان روتین روزانه ساخته می‌شوند (کلید، عنوان، نام کوتاه)
PRAYERS = [("prayer_fajr", "نماز صبح", "صبح"), ("prayer_dhuhr", "نماز ظهر", "ظهر"), ("prayer_asr", "نماز عصر", "عصر"),
           ("prayer_maghrib", "نماز مغرب", "مغرب"), ("prayer_isha", "نماز عشا", "عشا")]
KINDS_TASK = {"task": "کار", "chore": "ریزه‌کار"}      # کار: ساعت/مدت دارد • ریزه‌کار: کار کوچک بدون ساعت معین
CHORE_XP = 5
WEEK_ORDER = [5, 6, 0, 1, 2, 3, 4]                   # شنبه … جمعه (weekday پایتون)
ALL_DAYS = ",".join(map(str, WEEK_ORDER))

def data_dir():
    # روی اندروید پوشه برنامه فقط‌خواندنی است؛ Flet مسیر داده را در این متغیر می‌دهد
    d = os.getenv("FLET_APP_STORAGE_DATA") or os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d

def log_error(where, exc=None):
    """خطا را در errors.log کنار دیتابیس می‌نویسد (چرخشی، حداکثر حدود ۲۰۰ کیلوبایت). هرگز خطا نمی‌دهد."""
    try:
        p = os.path.join(data_dir(), "errors.log")
        if os.path.exists(p) and os.path.getsize(p) > 200_000: os.replace(p, p + ".1")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {where}\n")
            if exc is not None: f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) + "\n")
    except Exception: pass

def read_error_log(limit=6000):
    try:
        with open(os.path.join(data_dir(), "errors.log"), encoding="utf-8") as f: return f.read()[-limit:]
    except OSError: return ""

def clear_error_log():
    try: os.remove(os.path.join(data_dir(), "errors.log"))
    except OSError: pass

def xp_for_mission(minutes, priority):
    return max(10, min(100, 10 + int(minutes) // 5 + int(priority) * 5))
def xp_for(kind, minutes, priority):
    return CHORE_XP if kind == "chore" else xp_for_mission(minutes or 0, priority)
def xp_threshold(level): return 50 * (level - 1) * level
def level_for_xp(xp):
    level = 1
    while xp >= xp_threshold(level + 1): level += 1
    return level
def level_title(level): return LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)]

# --- دستاوردها: (شناسه، عنوان، توضیح، ایموجی، شرط روی stats)
ACHIEVEMENTS = [
    ("first_step", "اولین قدم", "اولین مأموریت را کامل کن", "🌱", lambda s: s["done"] >= 1),
    ("ten_missions", "ده‌تایی", "۱۰ مأموریت کامل کن", "🔟", lambda s: s["done"] >= 10),
    ("fifty_missions", "ماشین مأموریت", "۵۰ مأموریت کامل کن", "⚙️", lambda s: s["done"] >= 50),
    ("streak_3", "سه روز پیاپی", "۳ روز پشت‌سرهم فعالیت کن", "🔥", lambda s: s["best_streak"] >= 3),
    ("streak_7", "هفتهٔ آهنین", "۷ روز پشت‌سرهم فعالیت کن", "⚡", lambda s: s["best_streak"] >= 7),
    ("streak_30", "ماه بی‌وقفه", "۳۰ روز پشت‌سرهم فعالیت کن", "👑", lambda s: s["best_streak"] >= 30),
    ("level_5", "سطح ۵", "به سطح ۵ برس", "🚀", lambda s: s["level"] >= 5),
    ("mastered_1", "مسلط شدی", "یک مبحث را به تسلط برسان", "🎓", lambda s: s["mastered"] >= 1),
    ("exam_1", "اولین آزمون", "یک آزمون ≥۱۰ سؤالی ثبت کن", "📝", lambda s: s["exams"] >= 1),
    ("perfect", "نمرهٔ کامل", "در آزمونی (≥۱۰ سؤال) ۱۰۰٪ بگیر", "💯", lambda s: s["perfect"] >= 1),
    ("focus_5h", "تمرکز عمیق", "۵ ساعت تمرکز ثبت کن", "🎯", lambda s: s["focus_seconds"] >= 5 * 3600),
    ("xp_1000", "هزار امتیازی", "۱۰۰۰ XP جمع کن", "💎", lambda s: s["xp"] >= 1000),
]

def _iso(d): return d if isinstance(d, str) else d.isoformat()


class Store:
    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "get_better.db")
        self.recovery = None                       # None | "restored" | "fresh" — اگر دیتابیس خراب بود و بازسازی شد
        self.db = self._open()
        self.init_db()
        if self.recovery == "fresh": self._recover_from_backup()

    def _open(self):
        """اتصال امن: اگر فایل خراب بود کنارش می‌گذارد (برای بررسی) و دیتابیس تازه می‌سازد.
        check_same_thread=False چون Flet رویدادها را در رشته‌های مختلف اجرا می‌کند."""
        def connect():
            db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
            db.row_factory = sqlite3.Row
            return db
        try:
            db = connect()
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok": raise sqlite3.DatabaseError("quick_check failed")
        except sqlite3.DatabaseError as ex:
            try: db.close()
            except Exception: pass
            log_error("دیتابیس خراب بود و کنار گذاشته شد", ex)
            try: os.replace(self.path, f"{self.path}.corrupt-{datetime.now():%Y%m%d-%H%M%S}")
            except OSError:
                try: os.remove(self.path)
                except OSError: pass
            db = connect(); self.recovery = "fresh"
        db.execute("PRAGMA foreign_keys=ON")
        try: db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError: pass
        return db

    def _recover_from_backup(self):
        for p, _ in self.list_backups():
            try: self.restore(p, snapshot=False); self.recovery = "restored"; return
            except Exception as ex: log_error(f"بازیابی از {os.path.basename(p)} ناموفق بود", ex)

    def close(self):
        try: self.db.close()
        except Exception: pass

    def schema_version(self): return self.db.execute("PRAGMA user_version").fetchone()[0]

    # ---------- ساخت و مهاجرت دیتابیس ----------
    def init_db(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS missions(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,subject TEXT DEFAULT '',description TEXT DEFAULT '',minutes INTEGER DEFAULT 30,priority INTEGER DEFAULT 1,done INTEGER DEFAULT 0,xp INTEGER DEFAULT 10,date TEXT NOT NULL,note TEXT DEFAULT '',spent_seconds INTEGER DEFAULT 0,completed_at TEXT,icon TEXT);
        CREATE TABLE IF NOT EXISTS xp_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id INTEGER NOT NULL UNIQUE,xp INTEGER NOT NULL,at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY AUTOINCREMENT,subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,chapter TEXT DEFAULT '',name TEXT NOT NULL,notes TEXT DEFAULT '',mistakes TEXT DEFAULT '',status INTEGER DEFAULT 0,next_review TEXT);
        CREATE TABLE IF NOT EXISTS quiz_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,kind TEXT NOT NULL,total INTEGER NOT NULL,correct INTEGER NOT NULL,seconds INTEGER,date TEXT NOT NULL,note TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS achievements(id TEXT PRIMARY KEY,unlocked_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT DEFAULT '',body TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,pinned INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS tags(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,color TEXT DEFAULT '#E8B84A');
        CREATE TABLE IF NOT EXISTS note_tags(note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(note_id,tag_id));
        CREATE TABLE IF NOT EXISTS day_events(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,body TEXT DEFAULT '',date TEXT NOT NULL,time TEXT DEFAULT '00:00',icon TEXT);
        CREATE TABLE IF NOT EXISTS routines(id INTEGER PRIMARY KEY AUTOINCREMENT,key TEXT DEFAULT '',title TEXT NOT NULL,kind TEXT DEFAULT 'chore',minutes INTEGER DEFAULT 0,time TEXT DEFAULT '',days TEXT DEFAULT '',xp INTEGER DEFAULT 5,active INTEGER DEFAULT 1,sort INTEGER DEFAULT 0,created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS focus_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id INTEGER,seconds INTEGER NOT NULL,at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        # ستون‌های نسخهٔ ۲ (روی دیتابیس‌های قدیمی هم امن است)
        self._ensure_column("missions", "repeat", "TEXT DEFAULT ''")
        self._ensure_column("missions", "topic_id", "INTEGER")
        self._ensure_column("missions", "kind", "TEXT DEFAULT 'task'")
        self._ensure_column("missions", "time", "TEXT DEFAULT ''")
        self._ensure_column("missions", "routine_id", "INTEGER")
        self._ensure_column("topics", "box", "INTEGER DEFAULT 0")
        self.db.executescript("""
        CREATE INDEX IF NOT EXISTS ix_missions_date ON missions(date);
        CREATE INDEX IF NOT EXISTS ix_logs_topic ON quiz_logs(topic_id,date);
        CREATE INDEX IF NOT EXISTS ix_topics_review ON topics(next_review);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_missions_routine_day ON missions(routine_id,date) WHERE routine_id IS NOT NULL;
        """)
        for ddl in ("CREATE INDEX IF NOT EXISTS ix_missions_cdate ON missions(date(completed_at))",   # آمار روزانه بدون پویش کل جدول
                    "CREATE INDEX IF NOT EXISTS ix_xp_date ON xp_ledger(date(at))",
                    "CREATE INDEX IF NOT EXISTS ix_focus_date ON focus_sessions(date(at))",
                    "CREATE INDEX IF NOT EXISTS ix_quiz_date ON quiz_logs(date)"):
            try: self.db.execute(ddl)
            except sqlite3.DatabaseError as ex: log_error("ساخت ایندکس", ex)
        self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.db.commit()
        self.seed_prayers()

    def _columns(self, table):
        return [r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")]
    def _ensure_column(self, table, col, ddl):
        if col not in self._columns(table):
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

    # ---------- پایه ----------
    def all(self, sql, args=()): return self.db.execute(sql, args).fetchall()
    def one(self, sql, args=()): return self.db.execute(sql, args).fetchone()
    def run(self, sql, args=()):
        cur = self.db.execute(sql, args); self.db.commit(); return cur.lastrowid
    def pref(self, key, default=None):
        r = self.one("SELECT value FROM settings WHERE key=?", (key,))
        if r: return r["value"]
        return DEFAULTS.get(key, "") if default is None else default
    def pref_int(self, key, default=0):
        try: return int(self.pref(key))
        except (TypeError, ValueError): return default
    def setpref(self, key, value):
        self.run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    # ---------- XP و مأموریت ----------
    def xp(self): return self.one("SELECT COALESCE(SUM(xp),0) n FROM xp_ledger")["n"]
    def missions_on(self, day):
        """مأموریت‌های یک روز؛ rkey/rsort از روتین (نماز و...) می‌آید. ساخت روتین‌های روز با ensure_day است."""
        return self.all("""SELECT m.*, r.key rkey, COALESCE(r.sort,0) rsort FROM missions m LEFT JOIN routines r ON r.id=m.routine_id
                           WHERE m.date=? ORDER BY m.done, (m.time=''), m.time, m.priority DESC, m.id""", (_iso(day),))
    def today_missions(self): return self.missions_on(date.today())
    def overdue(self, today=None):
        return self.all("SELECT * FROM missions WHERE done=0 AND routine_id IS NULL AND date<? ORDER BY date,priority DESC", (_iso(today or date.today()),))
    def day_load(self, start, n=7):
        """برای هر روز: (تعداد کل، تعداد انجام‌شده) — برای نوار هفته."""
        start = date.fromisoformat(_iso(start)); out = {}
        rows = self.all("SELECT date,COUNT(*) t,SUM(done) d FROM missions WHERE routine_id IS NULL AND date BETWEEN ? AND ? GROUP BY date",
                        (start.isoformat(), (start + timedelta(days=n - 1)).isoformat()))
        by = {r["date"]: (r["t"], r["d"] or 0) for r in rows}
        for i in range(n):
            k = (start + timedelta(days=i)).isoformat(); out[k] = by.get(k, (0, 0))
        return out

    def save_mission(self, title, subject, minutes, priority, day, mid=None, repeat="", topic_id=None, kind="task", time=""):
        """kind: task (کار؛ ساعت و مدت اختیاری) یا chore (ریزه‌کار؛ بدون ساعت و مدت)."""
        if kind == "chore": minutes, time = 0, ""
        xp = xp_for(kind, minutes, priority); day = _iso(day)
        if mid:
            self.run("UPDATE missions SET title=?,subject=?,minutes=?,priority=?,xp=?,date=?,repeat=?,kind=?,time=? WHERE id=?",
                     (title, subject, minutes, priority, xp, day, repeat, kind, time, mid)); return mid
        return self.run("INSERT INTO missions(title,subject,minutes,priority,xp,date,repeat,topic_id,kind,time) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (title, subject, minutes, priority, xp, day, repeat, topic_id, kind, time))

    def toggle_mission(self, mid):
        """True اگر تازه تکمیل شد. دفتر XP یکتاست، پس بازگردانی و تکمیل دوباره امتیاز تکراری نمی‌دهد.
        مأموریت تکرارشونده هنگام تکمیل، نمونهٔ بعدی را می‌سازد (بدون تکرار ساختن)."""
        r = self.one("SELECT * FROM missions WHERE id=?", (mid,))
        if not r: return False
        now = datetime.now().isoformat(timespec='seconds')
        if not r['done']:
            with self.db:
                self.db.execute("UPDATE missions SET done=1,completed_at=? WHERE id=?", (now, mid))
                self.db.execute("INSERT OR IGNORE INTO xp_ledger(mission_id,xp,at) VALUES(?,?,?)", (mid, r['xp'], now))
            if r['repeat']: self._spawn_next(r)
            return True
        self.run("UPDATE missions SET done=0,completed_at=NULL WHERE id=?", (mid,)); return False

    def _spawn_next(self, r):
        step = {"daily": 1, "weekly": 7}.get(r['repeat'])
        if not step: return
        nxt = (date.fromisoformat(r['date']) + timedelta(days=step)).isoformat()
        if not self.one("SELECT 1 FROM missions WHERE title=? AND date=? AND repeat=?", (r['title'], nxt, r['repeat'])):
            self.run("INSERT INTO missions(title,subject,minutes,priority,xp,date,repeat,topic_id,kind,time) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (r['title'], r['subject'], r['minutes'], r['priority'], r['xp'], nxt, r['repeat'], r['topic_id'], r['kind'], r['time']))

    def move_tomorrow(self, mid):
        self.run("UPDATE missions SET date=? WHERE id=?", ((date.today() + timedelta(days=1)).isoformat(), mid))
    def move_overdue_to_today(self):
        self.run("UPDATE missions SET date=? WHERE done=0 AND date<?", (date.today().isoformat(),) * 2)
    def delete_mission(self, mid): self.run("DELETE FROM missions WHERE id=?", (mid,))

    # ---------- روتین‌ها (کارهای همیشگی؛ هر روز خودکار ساخته و صبح روز بعد ریست می‌شوند) ----------
    def seed_prayers(self):
        """نمازهای پنجگانه یک‌بار به‌صورت روتین روزانه اضافه می‌شوند؛ اگر کاربر حذفشان کرد، دوباره برنمی‌گردند."""
        if self.pref("prayers_seeded") == "1": return
        today = date.today().isoformat()
        for i, (key, name, _) in enumerate(PRAYERS):
            if not self.one("SELECT 1 FROM routines WHERE key=?", (key,)):
                self.db.execute("INSERT INTO routines(key,title,kind,minutes,time,days,xp,active,sort,created) VALUES(?,?,?,?,?,?,?,1,?,?)",
                                (key, name, "chore", 0, "", ALL_DAYS, CHORE_XP, i, today))
        self.db.commit(); self.setpref("prayers_seeded", "1")

    def routines(self):
        return self.all("SELECT * FROM routines ORDER BY sort,id")
    @staticmethod
    def routine_days(r):
        return {int(x) for x in (r["days"] or ALL_DAYS).split(",") if x.strip().isdigit()}
    def save_routine(self, title, kind, minutes, time, days, rid=None):
        days = sorted({int(d) for d in days}) or WEEK_ORDER
        if kind == "chore": minutes, time = 0, ""
        xp, ds = xp_for(kind, minutes, 1), ",".join(map(str, days))
        if rid:
            self.run("UPDATE routines SET title=?,kind=?,minutes=?,time=?,days=?,xp=? WHERE id=?", (title, kind, minutes, time, ds, xp, rid))
        else:
            n = self.one("SELECT COALESCE(MAX(sort),-1)+1 n FROM routines")["n"]
            rid = self.run("INSERT INTO routines(key,title,kind,minutes,time,days,xp,active,sort,created) VALUES('',?,?,?,?,?,?,1,?,?)",
                           (title, kind, minutes, time, ds, xp, n, date.today().isoformat()))
        self._sync_routine(rid); return rid
    def set_routine_active(self, rid, active):
        self.run("UPDATE routines SET active=? WHERE id=?", (1 if active else 0, rid)); self._sync_routine(rid)
    def delete_routine(self, rid):
        """روتین و نمونه‌های انجام‌نشدهٔ امروز و آینده‌اش حذف می‌شوند؛ تاریخچهٔ انجام‌شده‌ها می‌ماند."""
        self.db.execute("DELETE FROM missions WHERE routine_id=? AND done=0 AND date>=?", (rid, date.today().isoformat()))
        self.db.execute("DELETE FROM routines WHERE id=?", (rid,)); self.db.commit()
    def _sync_routine(self, rid):
        """تغییر روتین روی نمونه‌های انجام‌نشدهٔ امروز و آینده اعمال می‌شود."""
        r = self.one("SELECT * FROM routines WHERE id=?", (rid,))
        if not r: return
        days = self.routine_days(r)
        for m in self.all("SELECT id,date FROM missions WHERE routine_id=? AND done=0 AND date>=?", (rid, date.today().isoformat())):
            if not r["active"] or date.fromisoformat(m["date"]).weekday() not in days:
                self.db.execute("DELETE FROM missions WHERE id=?", (m["id"],))
            else:
                self.db.execute("UPDATE missions SET title=?,minutes=?,time=?,kind=?,xp=? WHERE id=?", (r["title"], r["minutes"], r["time"], r["kind"], r["xp"], m["id"]))
        self.db.commit()
    def ensure_day(self, day):
        """نمونهٔ روتین‌های فعالِ آن روز را می‌سازد (فقط از امروز به بعد؛ روز گذشته هرگز دستکاری نمی‌شود)."""
        d = date.fromisoformat(_iso(day))
        if d < date.today(): return
        for r in self.all("SELECT * FROM routines WHERE active=1 AND created<=?", (d.isoformat(),)):
            if d.weekday() not in self.routine_days(r): continue
            self.db.execute("INSERT OR IGNORE INTO missions(title,subject,minutes,priority,xp,date,kind,time,routine_id) VALUES(?,?,?,?,?,?,?,?,?)",
                            (r["title"], "", r["minutes"], 1, r["xp"], d.isoformat(), r["kind"], r["time"], r["id"]))
        self.db.commit()
    def ensure_range(self, start, n=7):
        start = date.fromisoformat(_iso(start))
        for i in range(n): self.ensure_day(start + timedelta(days=i))

    # ---------- برنامهٔ هفتگی ----------
    def week_plan(self, start):
        """۷ روز از start: کارهای عادی، خلاصهٔ روتین و نمازها."""
        start = date.fromisoformat(_iso(start)); self.ensure_range(start, 7); out = []
        for i in range(7):
            d = start + timedelta(days=i); rows = self.missions_on(d)
            tasks = [r for r in rows if r["routine_id"] is None]; rt = [r for r in rows if r["routine_id"] is not None]
            pr = [r for r in rt if (r["rkey"] or "").startswith("prayer")]; other = [r for r in rt if r not in pr]
            out.append(dict(date=d, tasks=tasks, routine=other, prayers=pr,
                            done=sum(1 for r in tasks if r["done"]), total=len(tasks),
                            routine_done=sum(1 for r in other if r["done"]), prayer_done=sum(1 for r in pr if r["done"])))
        return out
    def copy_week(self, src_start, dst_start):
        """کارهای عادی (غیرروتین) یک هفته را به‌صورت انجام‌نشده به هفتهٔ دیگر کپی می‌کند؛ تعداد کپی‌شده را برمی‌گرداند."""
        src, dst = date.fromisoformat(_iso(src_start)), date.fromisoformat(_iso(dst_start)); n = 0
        for r in self.all("SELECT * FROM missions WHERE routine_id IS NULL AND date BETWEEN ? AND ? ORDER BY id", (src.isoformat(), (src + timedelta(days=6)).isoformat())):
            nd = (dst + (date.fromisoformat(r["date"]) - src)).isoformat()
            if self.one("SELECT 1 FROM missions WHERE title=? AND date=? AND kind=?", (r["title"], nd, r["kind"])): continue
            self.run("INSERT INTO missions(title,subject,minutes,priority,xp,date,topic_id,kind,time) VALUES(?,?,?,?,?,?,?,?,?)",
                     (r["title"], r["subject"], r["minutes"], r["priority"], r["xp"], nd, r["topic_id"], r["kind"], r["time"])); n += 1
        return n

    # ---------- تمرکز (پومودورو) ----------
    def add_focus(self, mission_id, seconds):
        seconds = int(seconds)
        if seconds <= 0: return
        with self.db:
            self.db.execute("INSERT INTO focus_sessions(mission_id,seconds,at) VALUES(?,?,?)",
                            (mission_id, seconds, datetime.now().isoformat(timespec='seconds')))
            if mission_id: self.db.execute("UPDATE missions SET spent_seconds=spent_seconds+? WHERE id=?", (seconds, mission_id))
    def focus_seconds(self, day=None):
        if day: return self.one("SELECT COALESCE(SUM(seconds),0) n FROM focus_sessions WHERE date(at)=?", (_iso(day),))["n"]
        return self.one("SELECT COALESCE(SUM(seconds),0) n FROM focus_sessions")["n"]

    # ---------- مرور، تسلط و لایتنر ----------
    def add_log(self, topic_id, kind, total, correct, seconds, day, note=''):
        day = _iso(day)
        self.run("INSERT INTO quiz_logs(topic_id,kind,total,correct,seconds,date,note) VALUES(?,?,?,?,?,?,?)", (topic_id, kind, total, correct, seconds, day, note))
        t = self.one("SELECT status,box FROM topics WHERE id=?", (topic_id,))
        status, box = t['status'], (t['box'] or 0)
        acc = correct / total
        n_logs = self.one("SELECT COUNT(*) n FROM quiz_logs WHERE topic_id=?", (topic_id,))["n"]
        # لایتنر: اولین ثبت همیشه به جعبهٔ اول (۱ روز بعد)؛ بعد از آن بلد بودن (≥۸۰٪) → جعبهٔ بعدی،
        # در غیر این صورت برگشت به جعبهٔ اول
        if n_logs <= 1 or acc < .8: box = 0
        else: box = min(box + 1, len(BOX_DAYS) - 1)
        nxt = (date.fromisoformat(day) + timedelta(days=BOX_DAYS[box])).isoformat()
        logs = self.all("SELECT * FROM quiz_logs WHERE topic_id=? ORDER BY date,id", (topic_id,))
        if status == 0: status = 1
        if acc < .6 and status == 3: status = 2                    # افت عملکرد → نیازمند مرور
        if len(logs) >= 2:
            a, b = logs[-1], logs[-2]
            if a['date'] != b['date'] and a['total'] >= 10 and b['total'] >= 10 and a['correct'] / a['total'] >= .8 and b['correct'] / b['total'] >= .8:
                status = 3
        self.run("UPDATE topics SET status=?,box=?,next_review=? WHERE id=?", (status, box, nxt, topic_id))

    def set_topic_status(self, topic_id, status):
        self.run("UPDATE topics SET status=? WHERE id=?", (status, topic_id))

    def due_topics(self, today=None):
        """مباحثی که زمان مرورشان رسیده؛ ضعیف‌ترها اول."""
        return self.all("""
            SELECT t.*, s.name subject,
                   (SELECT 1.0*SUM(correct)/SUM(total) FROM quiz_logs q WHERE q.topic_id=t.id) acc
            FROM topics t JOIN subjects s ON s.id=t.subject_id
            WHERE t.status>0 AND (t.next_review IS NULL OR t.next_review<=?)
            ORDER BY COALESCE(acc,0), t.next_review""", (_iso(today or date.today()),))

    def subject_summary(self):
        return self.all("""
            SELECT s.id, s.name, COUNT(t.id) topics, COALESCE(SUM(t.status=3),0) mastered,
                   (SELECT 1.0*SUM(q.correct)/SUM(q.total) FROM quiz_logs q JOIN topics tt ON tt.id=q.topic_id WHERE tt.subject_id=s.id) acc
            FROM subjects s LEFT JOIN topics t ON t.subject_id=s.id GROUP BY s.id ORDER BY s.name""")

    def suggest_plan(self, day=None, limit=5):
        """برنامهٔ هوشمند: مرور مباحث موعدگذشته که هنوز برایشان مأموریتی نیست."""
        day = _iso(day or date.today()); out = []
        for t in self.due_topics(day):
            title = f"مرور: {t['name']}"
            if self.one("SELECT 1 FROM missions WHERE date=? AND (topic_id=? OR title=?)", (day, t['id'], title)): continue
            weak = t['acc'] is not None and t['acc'] < .6
            out.append(dict(title=title, subject=t['subject'], minutes=40 if weak else 25, priority=2 if weak else 1, topic_id=t['id']))
            if len(out) >= limit: break
        return out
    def apply_plan(self, items, day=None):
        for it in items:
            self.save_mission(it['title'], it['subject'], it['minutes'], it['priority'], day or date.today(), topic_id=it.get('topic_id'))
        return len(items)

    # ---------- استریک و آمار ----------
    def activity_days(self):
        rows = self.all("""SELECT date(completed_at) d FROM missions WHERE done=1 AND routine_id IS NULL AND completed_at IS NOT NULL
                           UNION SELECT date FROM quiz_logs UNION SELECT date(at) FROM focus_sessions""")
        return sorted({r[0] for r in rows if r[0]})

    def streaks(self, today=None, _days=None):
        """(استریک جاری، بهترین استریک). استریک جاری اگر امروز هنوز فعالیتی نیست، از دیروز حساب می‌شود."""
        today = today or date.today()
        days = {date.fromisoformat(d) for d in (self.activity_days() if _days is None else _days)}
        if not days: return 0, 0
        best = run = 0; prev = None
        for d in sorted(days):
            run = run + 1 if prev and (d - prev).days == 1 else 1
            best = max(best, run); prev = d
        cur, d = 0, today if today in days else today - timedelta(days=1)
        while d in days: cur += 1; d -= timedelta(days=1)
        return cur, best

    def stats(self):
        adays = self.activity_days()
        cur, best = self.streaks(_days=adays); xp = self.xp()
        m = self.one("SELECT COUNT(*) n, COALESCE(SUM(done),0) d FROM missions WHERE routine_id IS NULL")
        tp = self.one("SELECT COUNT(*) n, COALESCE(SUM(status=3),0) m FROM topics")
        q = self.one("""SELECT COALESCE(SUM(kind='exam' AND total>=10),0) exams,
                               COALESCE(SUM(kind='exam' AND total>=10 AND correct=total),0) perfect,
                               COALESCE(SUM(kind='review'),0) reviews,
                               COALESCE(SUM(kind='exam' AND total>=10 AND seconds IS NOT NULL),0) timed FROM quiz_logs""")
        return dict(
            xp=xp, level=level_for_xp(xp), streak=cur, best_streak=best,
            missions=m["n"], done=m["d"], topics=tp["n"], mastered=tp["m"],
            exams=q["exams"], perfect=q["perfect"], reviews=q["reviews"], timed=q["timed"],
            days=len(adays), focus_seconds=self.focus_seconds())

    def week_series(self, end=None, n=7):
        """آمار n روز منتهی به end: XP، تعداد مأموریت انجام‌شده و دقیقهٔ مطالعه (با چند پرس‌وجوی گروهی، نه ۴ پرس‌وجو برای هر روز)."""
        end = date.fromisoformat(_iso(end or date.today()))
        first, last = (end - timedelta(days=n - 1)).isoformat(), end.isoformat()
        xp = {r[0]: r[1] for r in self.all("SELECT date(at) d, SUM(xp) FROM xp_ledger WHERE date(at) BETWEEN ? AND ? GROUP BY d", (first, last))}
        done, sec = {}, {}
        for r in self.all("""SELECT date(completed_at) d, COUNT(*), SUM(CASE WHEN spent_seconds>0 THEN spent_seconds ELSE minutes*60 END)
                             FROM missions WHERE done=1 AND routine_id IS NULL AND date(completed_at) BETWEEN ? AND ? GROUP BY d""", (first, last)):
            done[r[0]] = r[1]; sec[r[0]] = r[2] or 0
        foc = {r[0]: r[1] for r in self.all("SELECT date(at) d, SUM(seconds) FROM focus_sessions WHERE date(at) BETWEEN ? AND ? GROUP BY d", (first, last))}
        out = []
        for i in range(n - 1, -1, -1):
            d = (end - timedelta(days=i)).isoformat()
            out.append(dict(date=d, xp=xp.get(d, 0), done=done.get(d, 0), minutes=max(sec.get(d, 0), foc.get(d, 0)) // 60))
        return out

    def heatmap(self, weeks=5, end=None):
        """شدت فعالیت هر روز برای weeks هفتهٔ منتهی به هفتهٔ شامل end (ستون‌ها شنبه‌تا‌جمعه)."""
        from jalali import week_start
        end = date.fromisoformat(_iso(end or date.today())); start = week_start(end) - timedelta(days=7 * (weeks - 1))
        counts = {}
        for r in self.all("""SELECT d, COUNT(*) n FROM (
                 SELECT date(completed_at) d FROM missions WHERE done=1 AND routine_id IS NULL AND completed_at IS NOT NULL
                 UNION ALL SELECT date FROM quiz_logs UNION ALL SELECT date(at) FROM focus_sessions) WHERE d>=? GROUP BY d""", (start.isoformat(),)):
            counts[r['d']] = r['n']
        return [[(start + timedelta(days=7 * w + i)) for i in range(7)] for w in range(weeks)], counts

    def roadmap(self):
        s = self.stats()
        return [("شروع مسیر", "از همین‌جا شروع می‌شود", 1, 1), ("ساخت عادت مطالعه", "فعالیت در ۵ روز مختلف", s['days'], 5),
                ("تسلط بر مباحث", "۳ مبحث با تسلط تأییدشده", s['mastered'], 3), ("تثبیت و مرور", "۵ مرور ثبت‌شده", s['reviews'], 5),
                ("آزمون‌های ترکیبی", "۳ آزمون با حداقل ۱۰ سؤال", s['exams'], 3), ("آزمون‌های زمان‌دار", "۳ آزمون زمان‌دار", s['timed'], 3),
                ("ارزیابی نهایی آمادگی", "۱۰ آزمون ثبت‌شده", s['exams'], 10)]

    # ---------- دستاوردها ----------
    def unlocked(self): return {r['id'] for r in self.all("SELECT id FROM achievements")}
    def check_achievements(self):
        """دستاوردهای تازه‌باز‌شده را ثبت می‌کند و فهرست (id,title,desc,emoji) برمی‌گرداند."""
        s, have, new = self.stats(), self.unlocked(), []
        now = datetime.now().isoformat(timespec='seconds')
        for aid, title, desc, emoji, cond in ACHIEVEMENTS:
            if aid not in have and cond(s):
                self.db.execute("INSERT OR IGNORE INTO achievements(id,unlocked_at) VALUES(?,?)", (aid, now))
                new.append((aid, title, desc, emoji))
        self.db.commit(); return new

    # ---------- یادداشت و برچسب ----------
    def all_tags(self): return self.all("SELECT t.*,(SELECT COUNT(*) FROM note_tags n WHERE n.tag_id=t.id) cnt FROM tags t ORDER BY name")
    def note_tag_names(self, note_id):
        return [r['name'] for r in self.all("SELECT t.name FROM tags t JOIN note_tags n ON n.tag_id=t.id WHERE n.note_id=? ORDER BY t.name", (note_id,))]
    def set_note_tags(self, note_id, names):
        names = list(dict.fromkeys(n.strip() for n in names if n.strip()))
        with self.db:
            self.db.execute("DELETE FROM note_tags WHERE note_id=?", (note_id,))
            for n in names:
                self.db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (n,))
                tid = self.db.execute("SELECT id FROM tags WHERE name=?", (n,)).fetchone()[0]
                self.db.execute("INSERT OR IGNORE INTO note_tags(note_id,tag_id) VALUES(?,?)", (note_id, tid))
            self.db.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM note_tags)")   # برچسب‌های یتیم
    def save_note(self, title, body, tags=(), nid=None):
        now = datetime.now().isoformat(timespec="seconds")
        if nid: self.run("UPDATE notes SET title=?,body=?,updated_at=? WHERE id=?", (title, body, now, nid))
        else: nid = self.run("INSERT INTO notes(title,body,created_at,updated_at) VALUES(?,?,?,?)", (title, body, now, now))
        self.set_note_tags(nid, tags); return nid
    def search_notes(self, q="", tag=None):
        like = f"%{q.strip()}%"
        sql = "SELECT * FROM notes n WHERE (title LIKE ? OR body LIKE ?)"; args = [like, like]
        if tag: sql += " AND EXISTS(SELECT 1 FROM note_tags nt JOIN tags t ON t.id=nt.tag_id WHERE nt.note_id=n.id AND t.name=?)"; args.append(tag)
        return self.all(sql + " ORDER BY pinned DESC,updated_at DESC", args)

    # ---------- پشتیبان ----------
    def backup_dict(self):
        return {"app": "Get Better", "version": BACKUP_VERSION, "exported_at": datetime.now().isoformat(timespec='seconds'),
                "data": {t: [dict(r) for r in self.all('SELECT * FROM ' + t)] for t in TABLES}}
    def backup(self, path):
        tmp = path + ".tmp"                      # اول فایل موقت، بعد جایگزینی؛ پشتیبان نیمه‌کاره هرگز باقی نمی‌ماند
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(self.backup_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    def backup_text(self): return json.dumps(self.backup_dict(), ensure_ascii=False)
    @staticmethod
    def export_filename(): return f"get_better_backup_{date.today().isoformat()}.json"

    # --- پشتیبان خودکار (پوشهٔ backups کنار دیتابیس)
    def backups_dir(self):
        d = os.path.join(os.path.dirname(os.path.abspath(self.path)), "backups"); os.makedirs(d, exist_ok=True); return d
    def has_data(self):
        return any(self.one(q)["n"] for q in ("SELECT COUNT(*) n FROM missions WHERE routine_id IS NULL", "SELECT COUNT(*) n FROM topics",
                                               "SELECT COUNT(*) n FROM notes", "SELECT COUNT(*) n FROM quiz_logs", "SELECT COUNT(*) n FROM day_events"))
    def auto_backup(self, tag="auto", keep=5):
        d = self.backups_dir(); stamp = datetime.now().strftime("%Y%m%d-%H%M%S"); p = os.path.join(d, f"{tag}-{stamp}.json"); n = 1
        while os.path.exists(p): p = os.path.join(d, f"{tag}-{stamp}-{n}.json"); n += 1
        self.backup(p)
        for old in sorted(glob.glob(os.path.join(d, f"{tag}-*.json")), reverse=True)[keep:]:
            try: os.remove(old)
            except OSError: pass
        return p
    def maybe_daily_backup(self):
        """روزی حداکثر یک پشتیبان خودکار (فقط اگر داده‌ای وجود دارد). True اگر ساخته شد."""
        today = date.today().isoformat()
        if self.pref("last_auto_backup") == today or not self.has_data(): return False
        self.auto_backup("auto", 5); self.setpref("last_auto_backup", today); return True
    def list_backups(self):
        """[(مسیر، زمان)] جدیدترین اول؛ فقط فایل‌های JSON پوشهٔ backups."""
        files = glob.glob(os.path.join(self.backups_dir(), "*.json"))
        return sorted(((f, os.path.getmtime(f)) for f in files), key=lambda x: x[1], reverse=True)

    def restore(self, path, snapshot=True):
        with open(path, encoding='utf-8') as f: self.restore_text(f.read(), snapshot)
    def restore_text(self, text, snapshot=True):
        """بازیابی اتمیک: اگر چیزی خراب بود، هیچ تغییری اعمال نمی‌شود. ستون‌های ناشناخته نادیده گرفته می‌شوند.
        پیش از جایگزینی، از وضعیت فعلی یک نسخهٔ «pre-restore» گرفته می‌شود تا اشتباه قابل جبران باشد."""
        try: obj = json.loads(text)
        except ValueError: raise ValueError("فایل پشتیبان معتبر نیست")
        if not isinstance(obj, dict): raise ValueError("فایل پشتیبان معتبر نیست")
        data = obj.get('data', obj)
        if not isinstance(data, dict) or not any(t in data for t in TABLES): raise ValueError("فایل پشتیبان معتبر نیست")
        if isinstance(obj.get("version"), int) and obj["version"] > BACKUP_VERSION: raise ValueError("این پشتیبان از نسخهٔ جدیدتر برنامه است؛ برنامه را به‌روز کن")
        if any(not isinstance(data.get(t, []), list) or any(not isinstance(r, dict) for r in data.get(t, [])) for t in TABLES): raise ValueError("فایل پشتیبان معتبر نیست")
        if snapshot and self.has_data():
            try: self.auto_backup("pre-restore", 3)
            except OSError as ex: log_error("ساخت نسخهٔ پیش از بازیابی ناموفق بود", ex)
        with self.db:
            for t in reversed(TABLES):  # اول جدول‌های وابسته پاک شوند
                if t in data: self.db.execute('DELETE FROM ' + t)
            for t in TABLES:
                cols_ok = set(self._columns(t))
                for row in data.get(t, []):
                    cols = [c for c in row if c in cols_ok]
                    if not cols: continue
                    self.db.execute(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", [row[c] for c in cols])
        self.seed_prayers()
    def clear_all(self, keep=("theme", "onboarded")):
        if self.has_data():
            try: self.auto_backup("pre-wipe", 2)
            except OSError as ex: log_error("ساخت نسخهٔ پیش از پاک‌سازی ناموفق بود", ex)
        keep_vals = {k: self.pref(k) for k in keep}
        with self.db:
            for t in reversed(TABLES): self.db.execute('DELETE FROM ' + t)
        for k, v in keep_vals.items(): self.setpref(k, v)
        self.seed_prayers()

    def is_fresh(self):
        """True اگر کاربر هنوز هیچ داده‌ای نساخته (برای نمایش معرفی اولیه)."""
        return not self.has_data() and not (self.pref("goal") or self.pref("exam_date"))
