# Independent QA Verification Report — RSF-36

**Task:** RSF-36 (`[M8] Portable packaging, CI and reproducible release artifacts`)  
**Task ID:** `zhk7olqfex25j8tewzoragi0`  
**Milestone:** M8 — Release Readiness  
**Reviewer:** forge-qa-reviewer (Independent Read-Only QA Session)  
**Date:** 2026-10-31  
**Verdict:** **QA_PASS**

---

## 1. Executive Summary

An independent, clean-room audit and verification of task RSF-36 was conducted. The task scope encompasses portable packaging, standard-library core isolation, CI configuration across Python 3.12–3.14, release reproducibility under `SOURCE_DATE_EPOCH`, license/provenance documentation, and strict exclusion of proprietary game assets and private test fixtures from public distribution artifacts.

All four acceptance criteria were independently verified and evaluated against the codebase, automated test suites, isolated distribution environments, and package archives.

**Primary Release Artifact Hashes:**
- **Wheel:** `dist/ro_sprite_forge-0.1.0-py3-none-any.whl`  
  SHA-256: `6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a` (Size: 258,976 bytes)
- **Sdist:** `dist/ro_sprite_forge-0.1.0.tar.gz`  
  SHA-256: `10a52be6aa122ecb2a6919847e245de67f0823f0e8f9571ca60dfeb739506618` (Size: 393,324 bytes)

Independent release reconstruction verified that the built wheel is bit-for-bit identical across multiple builds and rebuilds directly from the sdist (`6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a`).

---

## 2. Acceptance Criteria Verification

### Criterion 1: Clean supported Python 3.12+ installations run CLI/UI workflows; CI verifies supported versions and optional adapter isolation.
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `pyproject.toml` declares `requires-python = ">=3.12,<3.15"`, classifiers for Python 3.12, 3.13, 3.14, and `dependencies = []` (core is stdlib-only).
  - Wheel installed into an isolated virtual environment (`tests/check_distribution.py`) outside the source tree. Invocation of `ro-sprite-forge --help` executed cleanly from a separate working directory with no repository checkout.
  - Core binary ACT/SPR serialization, roundtrip preservation, inventory parsing, and finite requirements planning execute with stdlib only (verified with `PIL` and `jsonschema` completely uninstalled).
  - Package data (17 JSON schemas under `schemas/` and workbench assets `index.html`, `workbench.js`, `workbench.css`, `video.js` under `static/`) resolve cleanly via `importlib.resources`.
  - GitHub Actions CI workflow (`.github/workflows/ci.yml`) defines a matrix across `["3.12", "3.13", "3.14"]`.
  - Python 3.14.4 verified locally (`DISTRIBUTION_CHECK_PASS`). Python 3.12 and 3.13 are recorded as `NOT_RUN` locally due to host interpreter availability and are automated in CI.

### Criterion 2: Release rebuilds record stable tool/dependency/policy provenance and reproducible artifact hashes; no private paths, credentials, art or GRFs enter public packages.
- **Verdict:** **PASS**
- **Independent Evidence:**
  - Repeated wheel builds with `SOURCE_DATE_EPOCH="1704067200"` and different hash seeds produce byte-identical SHA-256 hashes (`6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a`).
  - Sdist extracted and rebuilt into a wheel produced the exact same SHA-256 hash (`6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a`).
  - Member audit of wheel (74 members) and sdist (132 members) verified zero `.act`, `.spr`, or `.grf` proprietary binaries, zero `private_fixture_hooks`, and zero credentials, keys (`.key`, `.pem`), or `.env` files.
  - `MANIFEST.in` explicitly prunes `tests/private_fixture_hooks`, `tools/rust-oracle/target`, and enforces `global-exclude *.act *.spr *.grf`.

### Criterion 3: Source modules/dependencies have explicit license/provenance review and notices; unresolved source ownership prevents publication.
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `NOTICE.md` exists at repository root, is included in `MANIFEST.in`, and is packaged in sdist root and wheel `dist-info/licenses/NOTICE.md`.
  - Provenance details documented:
    1. MIT License and copyright (c) 2026 Ronniel Allan Castañito.
    2. LWR codec extraction: `ro_reference.py` snapshot SHA-256 `55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46` under MIT.
    3. Independent Rust oracle: vendored from Korangar (commit `3f3d88a583203f09d079712f43343c1041258ffd`) under MIT, excluded from production wheels.
    4. Gravity Co., Ltd. intellectual property separation: zero proprietary game assets, client binaries, or GRF archives distributed.
    5. Third-party dependencies: Pillow (HPND), jsonschema (MIT), setuptools/wheel/build (MIT/Apache-2.0/PSF), FFmpeg (LGPL/GPL system tool).
    6. Policy: Unresolved source ownership strictly prevents publication.
  - Both `LICENSE` and `NOTICE.md` are verified present in sdist and wheel archives.

### Criterion 4: Public CI and demos use synthetic redistributable assets; private fixture hooks remain optional and clearly NOT_RUN when absent.
- **Verdict:** **PASS**
- **Independent Evidence:**
  - Public test suite (647 tests) executes strictly on clean-room synthetic fixtures.
  - Private fixture hooks (`tests/private_fixture_hooks/`) are pruned from sdist and wheel distributions.
  - In isolated virtual environment distribution check (`tests/check_distribution.py`), all 647 public tests ran, 631 passed, 16 skipped (optional development tooling like local Rust oracle and FFmpeg gracefully degrade), yielding `DISTRIBUTION_CHECK_PASS`.
  - Private fixture hooks suite executed independently: 51 tests passed, 1 test skipped (`NOT_RUN`: native Korangar playback without GPU/display environment).

---

## 3. Independent Test Execution Matrix

| Test Suite / Inspection | Command | Exit Code | Result | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Manifest Check** | SHA-256 comparison of implementation & evidence manifests | `0` | **PASS** | 100% hash and size match across all 6 code files and 12 evidence files |
| **Packaging & Distribution** | `.venv/bin/python -m unittest tests/test_packaging_and_distribution.py -v` | `0` | **PASS** | 11 tests passed in 7.1s |
| **Full Public Discovery** | `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | `0` | **PASS** | 647 tests passed in 62.8s |
| **Private Fixture Hooks** | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'` | `0` | **PASS** | 52 tests (51 passed, 1 skipped/NOT_RUN for GPU native playback) |
| **Schema Checkers** | `for s in scripts/check_*schema*.py; do python3 "$s" \|\| exit 1; done` | `0` | **PASS** | 13/13 schema validation scripts passed |
| **Distribution Check** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | **PASS** | `DISTRIBUTION_CHECK_PASS` (647 run: 631 pass, 16 skip) |
| **Release Manifest Generator** | `.venv/bin/python scripts/generate_release_manifest.py` | `0` | **PASS** | `RELEASE_MANIFEST_GENERATED` |
| **Release Reconstruction** | Clean `python -m build` under `SOURCE_DATE_EPOCH=1704067200` | `0` | **PASS** | Wheel hash `6bc8a6e1f612...` matched bit-exact; sdist rebuild wheel matched bit-exact |

---

## 4. Observations & Notes

1. **Sdist-to-Wheel Hash Bit-Exact Match:**  
   In `docs/verification/rsf-36/REPORT.md` (line 35), the implementer noted an intermediate wheel hash `755f1d8855eb649f2c60af2cb68ca406ebee77445cb21766eb65cb930d4c1976`. Independent reconstruction and `distribution.log` (line 978) confirm that rebuilding a wheel from the released sdist actually produces `6bc8a6e1f6129265517d7548eb480985dc6e8f69d5ada8e9651867876e274d4a` — which is bit-exact identical to the wheel built directly from the source repository. This represents a stronger reproducibility outcome than the intermediate string in the report text.

2. **Clean Room and Zero Prohibited Assets:**  
   Both archive audits and filesystem scans confirm no proprietary assets (`.act`, `.spr`, `.grf`), credentials, private fixture hooks, or intermediate build files leaked into distributions.

---

## 5. Final QA Verdict

**Verdict:** `QA_PASS`

All technical contracts, reproducibility standards, licensing notices, and packaging criteria for task RSF-36 are satisfied.
