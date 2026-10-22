# -*- coding: utf-8 -*-
"""هم‌خوانی‌های انتشار: نسخه، آیکون، مستندات، CI. اگر هنگام بالا بردن نسخه چیزی را فراموش کنی، این‌جا قرمز می‌شود."""
import os, re, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import meta

def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f: return f.read()

class TestRelease(unittest.TestCase):
    def test_version_consistent(self):
        self.assertRegex(meta.VERSION, r"^\d+\.\d+\.\d+$"); self.assertIsInstance(meta.BUILD_NUMBER, int); self.assertGreaterEqual(meta.BUILD_NUMBER, 1)
        self.assertIn(f'version = "{meta.VERSION}"', read("pyproject.toml"))
        self.assertIn(f"## {meta.VERSION}", read("CHANGELOG.md"))
        self.assertIn(f"--build-number {meta.BUILD_NUMBER}", read("RELEASE.md"))
    def test_app_id_matches_org(self):
        self.assertTrue(meta.APP_ID.startswith(re.search(r'org = "([^"]+)"', read("pyproject.toml")).group(1)))
    def test_assets_exist_and_sized(self):
        from PIL import Image
        for rel, size in (("assets/icon.png", (1024, 1024)), ("store/icon_512.png", (512, 512)), ("store/feature_graphic.png", (1024, 500))):
            with Image.open(os.path.join(ROOT, rel)) as im: self.assertEqual(im.size, size, rel)
        for rel in ("assets/splash.png", "assets/splash_dark.png", "assets/favicon.png"): self.assertTrue(os.path.getsize(os.path.join(ROOT, rel)) > 500, rel)
    def test_icon_has_no_transparency(self):          # گوگل‌پلی آیکون با شفافیت را رد می‌کند
        from PIL import Image
        with Image.open(os.path.join(ROOT, "assets", "icon.png")) as im: self.assertNotIn("A", im.mode)
    def test_docs_present(self):
        for f in ("README.md", "PRIVACY.md", "CHANGELOG.md", "RELEASE.md", "STORE_LISTING.md"): self.assertTrue(len(read(f)) > 300, f)
        self.assertIn("هیچ داده‌ای", read("PRIVACY.md")); self.assertIn("Privacy Policy", read("PRIVACY.md"))
    def test_store_listing_limits(self):
        sl = read("STORE_LISTING.md"); short = re.search(r"\*\*توضیح کوتاه[^\n]*\n(.+)", sl).group(1).strip()
        self.assertLessEqual(len(short), 80); name = re.search(r"\*\*نام[^\n]*:\*\* (.+)", sl).group(1).strip(); self.assertLessEqual(len(name), 30)
    def test_ci_workflow(self):
        ci = read(".github", "workflows", "build.yml")
        for k in ("unittest discover", "flet build apk", "flet build aab", "get_font.py", "upload-artifact"): self.assertIn(k, ci)
    def test_ci_robustness(self):
        ci = read(".github", "workflows", "build.yml")
        for k in ("requirements-dev.txt", "contents: write", "timeout-minutes", "flet[all]==0.28.3", "if-no-files-found: error"): self.assertIn(k, ci)
        self.assertIn("pillow", read("requirements-dev.txt").lower())      # تست‌ها به Pillow نیاز دارند
        self.assertIn("flet==0.28.3", read("requirements.txt")); self.assertIn("flet==0.28.3", read("pyproject.toml"))
    def test_font_script_has_mirrors(self):
        self.assertGreaterEqual(read("tools", "get_font.py").count("https://"), 3)
    def test_assets_fonts_dir_not_empty_file(self):
        self.assertTrue(os.path.getsize(os.path.join(ROOT, "assets", "fonts", "README.txt")) > 20)   # آپلود وب گیت‌هاب فایل خالی را نادیده می‌گیرد
    def test_secrets_not_committable(self):
        gi = read(".gitignore"); self.assertIn("*.jks", gi); self.assertIn("*.keystore", gi)
    def test_no_network_calls_in_app(self):           # ادعای «کاملاً آفلاین» در حریم خصوصی باید درست بماند
        for f in ("main.py", "store.py", "ui.py", "jalali.py", "meta.py"):
            src = read(f)
            for bad in ("urllib", "requests", "http.client", "socket", "httpx", "aiohttp"): self.assertNotIn("import " + bad, src, f"{f} imports {bad}")

if __name__ == "__main__": unittest.main()
