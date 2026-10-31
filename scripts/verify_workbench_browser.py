"""Verify workbench UI in a headless browser and capture screenshot evidence."""

import os
import subprocess
import tempfile
import time
from pathlib import Path

from ro_sprite_forge.core.project import create_project


def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        create_project(
            proj_dir,
            "novice-walk-browser",
            "Male Novice Browser Test",
            "player",
            "male_novice",
        )

        port = 8899
        env = os.environ.copy()
        proc = subprocess.Popen(
            [
                ".venv/bin/python",
                "-m",
                "ro_sprite_forge",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--projects-dir",
                str(proj_dir),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(1.2)
            url = f"http://127.0.0.1:{port}"
            out_png = Path("docs/verification/rsf-38/workbench-browser.png")
            out_png.parent.mkdir(parents=True, exist_ok=True)

            res = subprocess.run(
                [
                    "google-chrome",
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--window-size=1280,800",
                    f"--screenshot={out_png}",
                    url,
                ],
                capture_output=True,
                text=True,
            )
            print(f"Chrome exit code: {res.returncode}")
            if out_png.exists():
                print(f"Screenshot captured: {out_png} ({out_png.stat().st_size} bytes)")

            res_dom = subprocess.run(
                [
                    "google-chrome",
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
            )
            dom_text = res_dom.stdout
            assert 'id="preview-zoom"' in dom_text, "Missing preview-zoom in DOM"
            assert 'id="preview-bg"' in dom_text, "Missing preview-bg in DOM"
            assert 'id="preview-viewport"' in dom_text, "Missing preview-viewport in DOM"
            assert "Checkerboard (Dark)" in dom_text, "Missing Checkerboard option in DOM"
            assert "[A] Approve displayed scope" in dom_text, "Missing keyboard approve shortcut in DOM"
            print("DOM assertions passed successfully!")
        finally:
            proc.terminate()
            proc.wait(timeout=3)


if __name__ == "__main__":
    main()
