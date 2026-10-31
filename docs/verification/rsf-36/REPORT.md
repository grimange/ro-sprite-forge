# Verification Report — RSF-36: Portable Packaging, CI, and Reproducible Release Artifacts

## 1. Executive Summary

**Task:** RSF-36 — `[M8] Portable packaging, CI and reproducible release artifacts`  
**Internal Task ID:** `zhk7olqfex25j8tewzoragi0` (Number 36)  
**Milestone:** M8 — Release Readiness  
**Implementer:** AGY (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)  
**Status at Handoff:** In Review (`bnbwdupscc2quo8im9o6w3ol`)  
**Build Artifacts:**
- Wheel: `dist/ro_sprite_forge-0.1.0-py3-none-any.whl` (SHA-256: `6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a`)
- Sdist: `dist/ro_sprite_forge-0.1.0.tar.gz` (SHA-256: `10a52be6aa122ecb2a6919847e245de67f0823f0e8f9571ca60dfeb739506618`)
- Canonical Release Manifest: `docs/verification/rsf-36/release-manifest.json`

All four mandatory live acceptance criteria have been implemented, tested, and self-verified with zero failures.

---

## 2. Evaluation of Live Acceptance Criteria

### Criterion 1: Clean supported Python 3.12+ installations run CLI/UI workflows; CI verifies supported versions and optional adapter isolation
- **Status:** **PASS**
- **Evidence:**
  - `tests/test_packaging_and_distribution.py` (Test 5) installs the built wheel into a completely isolated temporary virtual environment outside the source tree.
  - The CLI entry point `ro-sprite-forge --help` executes cleanly from an external working directory with no source checkout dependency.
  - Stdlib-only core functionality (ACT/SPR binary reading/writing, roundtrip preservation, inventory parsing, and finite requirements planning) executes with zero external dependencies (`Pillow` and `jsonschema` absent).
  - Package resources (17 JSON schemas and static workbench assets `index.html`, `workbench.js`, `workbench.css`, `video.js`) resolve correctly via `importlib.resources`.
  - GitHub Actions CI workflow (`.github/workflows/ci.yml`) defines a matrix across all declared supported Python versions (`["3.12", "3.13", "3.14"]`).
  - Locally, Python 3.14.4 is verified (`DISTRIBUTION_CHECK_PASS`). Python 3.12 and 3.13 are recorded as `NOT_RUN` locally due to interpreter availability and are automated via CI.

### Criterion 2: Release rebuilds record stable tool/dependency/policy provenance and reproducible artifact hashes; no private paths, credentials, art or GRFs enter public packages
- **Status:** **PASS**
- **Evidence:**
  - Repeated release builds using `SOURCE_DATE_EPOCH="1704067200"` across different output directories and process hash seeds produce bit-exact identical wheels (`_file_sha256(whl1) == _file_sha256(whl2)`).
  - Rebuilding wheels from independently extracted sdists produces bit-exact identical wheel hashes matching the primary release wheel (`6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a`).
  - Comprehensive member audits of both wheel and sdist verify zero prohibited extensions (`.act`, `.spr`, `.grf`), zero `private_fixture_hooks`, and zero credentials, keys (`.key`, `.pem`), or environment files.
  - `MANIFEST.in` explicitly prunes `tests/private_fixture_hooks`, `tools/rust-oracle/target`, and adds `global-exclude *.act *.spr *.grf`.

### Criterion 3: Source modules/dependencies have explicit license/provenance review and notices; unresolved source ownership prevents publication
- **Status:** **PASS**
- **Evidence:**
  - Created root `NOTICE.md` documenting:
    1. Core package copyright and MIT License.
    2. Living-World-Ragnarok (LWR) codec provenance: adapted from `ro_reference.py` (`SHA-256: 55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46`), authored by Ronniel Allan Castañito under MIT.
    3. Independent Rust oracle provenance: vendored from Korangar (pinned commit `3f3d88a583203f09d079712f43343c1041258ffd`), copyright 2023 Lucas Pütz under MIT. Oracle is excluded from release wheels.
    4. Gravity Co., Ltd. intellectual property separation: RO Sprite Forge distributes zero proprietary game assets, client binaries, or GRFs.
    5. Third-party dependencies: Pillow (HPND), jsonschema (MIT), setuptools/wheel/build (MIT/Apache-2.0/PSF), FFmpeg (LGPL/GPL system tool).
    6. Policy: Unresolved source ownership strictly prevents publication.
  - Both `LICENSE` and `NOTICE.md` are packaged into sdist root and wheel `dist-info/licenses/`.

### Criterion 4: Public CI and demos use synthetic redistributable assets; private fixture hooks remain optional and clearly NOT_RUN when absent
- **Status:** **PASS**
- **Evidence:**
  - All 647 public tests and public distribution checks run strictly on synthetic clean-room fixtures.
  - Private fixture hooks (`tests/private_fixture_hooks/`) are pruned from sdist and wheel distributions (`MANIFEST.in`).
  - Distribution verification script (`tests/check_distribution.py`) confirms that public distributions run cleanly without private fixtures.
  - In CI and distribution checks, missing native GPU runs and missing optional tools (Rust oracle, FFmpeg) are explicitly classified as skipped/NOT_RUN rather than failing or reporting false PASS.

---

## 3. Test Execution Matrix

| Test Suite / Gate | Command | Exit Code | Result | Evidence File |
| :--- | :--- | :---: | :---: | :--- |
| **Focused Packaging Suite** | `.venv/bin/python -m unittest tests/test_packaging_and_distribution.py -v` | `0` | 11 PASS | `focused.log` |
| **Full Public Test Discovery** | `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` | `0` | 647 PASS | `public.log` |
| **Private Fixture Hooks** | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v` | `0` | 51 PASS, 1 SKIP | `private.log` |
| **Schema Checkers (13 scripts)** | `for s in scripts/check_*schema*.py; do python3 "$s"; done` | `0` | 13 PASS | `schemas.log` |
| **Distribution Check (isolated venv)** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | 647 run, 631 PASS, 16 SKIP | `distribution.log` |
| **Release Manifest Generation** | `.venv/bin/python scripts/generate_release_manifest.py` | `0` | Manifest Generated | `release-manifest.json` |

---

## 4. Deliverables and Changed Paths

1. `NOTICE.md` (New): Third-party notices, license documentation, and source ownership policies.
2. `MANIFEST.in` (Modified): Added `LICENSE`, `NOTICE.md`, schema packaging, prune rust target, and `global-exclude *.act *.spr *.grf`.
3. `.github/workflows/ci.yml` (New): Full GitHub Actions workflow with matrix across Python 3.12, 3.13, 3.14, distribution rebuild, reproducibility comparison, and artifact exclusion.
4. `tests/test_packaging_and_distribution.py` (New): 11 comprehensive tests covering metadata, licensing, exclusion, reproducibility, clean installation, sdist rebuild, CI validity, and negative tests.
5. `tests/check_distribution.py` (Modified): Added `NOTICE.md` audit in sdist and wheel, and passed `RSF_REPO_ROOT` to isolated venvs.
6. `scripts/generate_release_manifest.py` (New): Generates durable canonical release manifest tying git commit, hashes, audits, and python matrix.
7. `docs/verification/rsf-36/` (New): Complete evidence packet (`PLAN.md`, `REPORT.md`, `environment.json`, `commands.json`, `kaneo-start.json`, `release-manifest.json`, and all execution logs).
