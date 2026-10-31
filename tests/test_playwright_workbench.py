"""Real Playwright browser interaction test suite for Operator Workbench (RSF-39)."""

import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, reference
from ro_sprite_forge.core.project import create_project, load_project, save_project
from ro_sprite_forge.service.server import create_server, make_standard_actor_doc

CHROME_PATH = "/usr/bin/google-chrome"
SCREENSHOTS_DIR = Path("docs/verification/rsf-39/screenshots")


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "Playwright is not installed in the current environment")
class PlaywrightWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="rsf-playwright-")
        cls.root = Path(cls.temp_dir.name).resolve()

        # Create a synthetic project with declared topology
        create_project(cls.root, "playwright-project", "Playwright Test Project", "player", "male_novice")
        proj_data = load_project(cls.root, "playwright-project")

        profile = frozen_runtime_profile("player")
        actor_doc = make_standard_actor_doc("playwright-project", profile, parts=["body"])
        actor = load_actor(actor_doc)

        views = []
        for v in range(8):
            views.append({
                "view": v,
                "frame_count": 4,
                "topology": {"kind": "explicit", "layers": ["body", "shadow"]},
            })

        proj_data["target"] = {
            "schema": "rsf.target/v2",
            "id": "playwright-project-target",
            "revision": 1,
            "previous_sha256": None,
            "actor": reference(actor),
            "runtime_profile": reference(profile),
            "scope": "scoped",
            "actions": [
                {
                    "action": "Walk",
                    "requirement": "required",
                    "views": views,
                }
            ],
            "layers": [
                {"index": 0, "name": "shadow", "role": "shadow"},
                {"index": 1, "name": "body", "role": "main"},
            ],
        }
        save_project(cls.root, proj_data, expected_revision=proj_data["revision"])

        # Start server on dynamic loopback port
        cls.server = create_server(cls.root, host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = cls.server.url
        time.sleep(0.3)

        # Launch Playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
        except Exception:
            pass
        try:
            cls.pw.stop()
        except Exception:
            pass
        try:
            cls.server.shutdown()
        except Exception:
            pass
        cls.temp_dir.cleanup()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 800})
        self.page.goto(self.url, wait_until="networkidle")

    def tearDown(self):
        self.page.close()

    def test_01_responsive_viewports_and_screenshots(self):
        """Verify responsive layouts across supported desktop viewports (1920x1080, 1280x800, 1024x768)."""
        viewports = [
            (1920, 1080, "viewport_1920x1080.png"),
            (1280, 800, "viewport_1280x800.png"),
            (1024, 768, "viewport_1024x768.png"),
        ]
        for w, h, fname in viewports:
            self.page.set_viewport_size({"width": w, "height": h})
            self.page.wait_for_timeout(100)
            # Ensure header and brand are visible
            brand = self.page.locator(".brand-title")
            self.assertTrue(brand.is_visible())
            # Ensure workspace does not horizontally scroll window
            scroll_width = self.page.evaluate("() => document.documentElement.scrollWidth")
            client_width = self.page.evaluate("() => document.documentElement.clientWidth")
            self.assertEqual(scroll_width, client_width, f"Horizontal overflow at {w}x{h}")

            screenshot_path = SCREENSHOTS_DIR / fname
            self.page.screenshot(path=str(screenshot_path))
            self.assertTrue(screenshot_path.exists())
            self.assertGreater(screenshot_path.stat().st_size, 10000)

    def test_02_integer_zoom_controls_and_keyboard_shortcuts(self):
        """Verify integer nearest-neighbor zoom dropdown, step keys (+/-), and 1x reset key (0)."""
        zoom_select = self.page.locator("#preview-zoom")
        self.assertTrue(zoom_select.is_visible())
        self.assertEqual(zoom_select.input_value(), "1")

        # Focus non-input element
        self.page.locator("body").click()

        # Press '+' or '=' to zoom in
        self.page.keyboard.press("=")
        self.assertEqual(zoom_select.input_value(), "2")

        self.page.keyboard.press("=")
        self.assertEqual(zoom_select.input_value(), "3")

        self.page.keyboard.press("=")
        self.assertEqual(zoom_select.input_value(), "4")

        self.page.keyboard.press("=")
        self.assertEqual(zoom_select.input_value(), "8")

        # Press '-' to zoom out
        self.page.keyboard.press("-")
        self.assertEqual(zoom_select.input_value(), "4")

        # Press '0' to reset to 1x
        self.page.keyboard.press("0")
        self.assertEqual(zoom_select.input_value(), "1")

        # Dropdown selection directly
        zoom_select.select_option("4")
        self.assertEqual(zoom_select.input_value(), "4")

    def test_03_transparency_background_modes_and_b_key_cycle(self):
        """Verify 5 background modes and cycling with 'B' key."""
        bg_select = self.page.locator("#preview-bg")
        viewport = self.page.locator("#preview-viewport")
        self.assertTrue(bg_select.is_visible())
        self.assertEqual(bg_select.input_value(), "checker-dark")
        self.assertIn("bg-checker-dark", viewport.get_attribute("class") or "")

        self.page.locator("body").click()

        # Press 'b' to cycle
        self.page.keyboard.press("b")
        self.assertEqual(bg_select.input_value(), "checker-light")
        self.assertIn("bg-checker-light", viewport.get_attribute("class") or "")

        self.page.keyboard.press("b")
        self.assertEqual(bg_select.input_value(), "solid-dark")
        self.assertIn("bg-solid-dark", viewport.get_attribute("class") or "")

        self.page.keyboard.press("b")
        self.assertEqual(bg_select.input_value(), "solid-white")
        self.assertIn("bg-solid-white", viewport.get_attribute("class") or "")

        self.page.keyboard.press("b")
        self.assertEqual(bg_select.input_value(), "transparent")
        self.assertIn("bg-transparent", viewport.get_attribute("class") or "")

        # Cycle back to checker-dark
        self.page.keyboard.press("b")
        self.assertEqual(bg_select.input_value(), "checker-dark")
        self.assertIn("bg-checker-dark", viewport.get_attribute("class") or "")

    def test_04_timeline_frame_stepping_and_playback_shortcuts(self):
        """Verify ArrowLeft, ArrowRight, and Space trigger stepping and play/pause buttons."""
        self.page.locator("body").click()

        # We can spy on button clicks by setting data attributes in the page
        self.page.evaluate("""() => {
            window._clicks = {prev: 0, next: 0, play: 0, pause: 0};
            document.getElementById('previous-frame').addEventListener('click', () => window._clicks.prev++);
            document.getElementById('next-frame').addEventListener('click', () => window._clicks.next++);
            document.getElementById('play').addEventListener('click', () => window._clicks.play++);
            document.getElementById('pause').addEventListener('click', () => window._clicks.pause++);
        }""")

        self.page.keyboard.press("ArrowRight")
        clicks = self.page.evaluate("() => window._clicks")
        self.assertEqual(clicks["next"], 1)

        self.page.keyboard.press("ArrowLeft")
        clicks = self.page.evaluate("() => window._clicks")
        self.assertEqual(clicks["prev"], 1)

        self.page.keyboard.press("Space")
        clicks = self.page.evaluate("() => window._clicks")
        self.assertEqual(clicks["play"], 1)

    def test_05_keyboard_safety_in_inputs(self):
        """Verify typing spaces, +, -, 0, B in an input does NOT trigger shortcuts."""
        search_box = self.page.locator("#tree-search")
        search_box.focus()

        zoom_before = self.page.locator("#preview-zoom").input_value()
        bg_before = self.page.locator("#preview-bg").input_value()

        # Type keys that would normally trigger shortcuts
        self.page.keyboard.type("walk + - 0 b test ")

        # Zoom and background should remain unchanged
        zoom_after = self.page.locator("#preview-zoom").input_value()
        bg_after = self.page.locator("#preview-bg").input_value()
        self.assertEqual(zoom_before, zoom_after)
        self.assertEqual(bg_before, bg_after)
        self.assertEqual(search_box.input_value(), "walk + - 0 b test ")

    def test_06_review_dialog_shortcuts(self):
        """Verify review dialog keys: A (approve), R (reject), Escape (cancel)."""
        self.page.evaluate("""() => {
            window._reviewClicks = {approve: 0, reject: 0, cancel: 0};
            document.getElementById('approve-review').addEventListener('click', () => window._reviewClicks.approve++);
            document.getElementById('reject-review').addEventListener('click', () => window._reviewClicks.reject++);
            document.getElementById('cancel-review').addEventListener('click', () => window._reviewClicks.cancel++);
            document.getElementById('review-dialog').showModal();
        }""")

        dialog = self.page.locator("#review-dialog")
        self.assertTrue(dialog.is_visible())

        # Press 'a'
        self.page.keyboard.press("a")
        clicks = self.page.evaluate("() => window._reviewClicks")
        self.assertEqual(clicks["approve"], 1)

        # Press 'r'
        self.page.keyboard.press("r")
        clicks = self.page.evaluate("() => window._reviewClicks")
        self.assertEqual(clicks["reject"], 1)

        # Press 'Escape'
        self.page.keyboard.press("Escape")
        clicks = self.page.evaluate("() => window._reviewClicks")
        self.assertEqual(clicks["cancel"], 1)

    def test_07_non_color_diagnostic_badges(self):
        """Verify status filter buttons and badges have ASCII/textual indicators."""
        filter_bar = self.page.locator("#filter-bar")
        self.assertTrue(filter_bar.is_visible())

        # Check filter buttons contain explicit textual markers
        text_content = filter_bar.inner_text()
        self.assertIn("[!] UNDER", text_content)
        self.assertIn("[-] UNASSIGNED", text_content)
        self.assertIn("[x] INVALID", text_content)
        self.assertIn("[?] REVIEW", text_content)
        self.assertIn("[ø] UNSUPP", text_content)
        self.assertIn("[~] REUSED", text_content)
        self.assertIn("[✓] READY", text_content)


if __name__ == "__main__":
    unittest.main()
