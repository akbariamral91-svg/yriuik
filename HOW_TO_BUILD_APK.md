# ساخت APK با GitHub (کاملاً خودکار)

1. در GitHub یک مخزن (Repository) جدید بساز.
2. **zip را اول Extract کن** و *محتویات* پوشهٔ `getbetter` را (نه خود پوشه را) آپلود کن تا `pyproject.toml` و پوشهٔ `.github` در ریشهٔ مخزن باشند.
   - پوشه‌های پنهان (`.github`, `.gitignore`) را فراموش نکن: در ویندوز «Hidden items» و در مک `Cmd+Shift+.` را روشن کن، سپس همهٔ پوشه‌ها را با drag & drop در صفحهٔ *Add file ← Upload files* بینداز.
   - بعد از آپلود بررسی کن مسیر `.github/workflows/build.yml` در مخزن دیده شود.
3. به تب **Actions** برو. اگر پرسید، Workflows را فعال (Enable) کن. ساخت خودکار شروع می‌شود (حدود ۱۵ تا ۳۵ دقیقه برای اولین بار).
4. بعد از سبز شدن: بخش **Releases** (ستون سمت راست صفحهٔ اصلی مخزن) ← فایل `GetBetter-3.4.2.apk` را مستقیم دانلود و روی گوشی نصب کن. (در Actions ← Artifacts هم یک نسخهٔ zip هست.)

اگر قرمز شد: روی مرحلهٔ قرمز کلیک کن و متن خطا را برایم بفرست.

## اگر پوشهٔ `.github` آپلود نشد یا دیده نمی‌شود
در مخزن: *Add file ← Create new file* ← در کادر نام دقیقاً بنویس `.github/workflows/build.yml` ← محتوای فایل `WORKFLOW_build.yml.txt` را کامل Paste کن ← Commit.
