# Verification Plan — RSF-36: Portable Packaging, CI, and Reproducible Release Artifacts

## Objective
Verify that RO Sprite Forge:
1. Conforms to portable packaging standards with a stdlib-only core and explicit optional dependencies.
2. Generates complete wheel and sdist packages without referencing original development paths or private assets.
3. Produces bit-exact reproducible wheel artifacts across repeated builds under `SOURCE_DATE_EPOCH`.
4. Excludes all private/proprietary resources (`.act`, `.spr`, `.grf`, `private_fixture_hooks`, keys/credentials).
5. Provides explicit third-party notices, license documentation, and source provenance (`NOTICE.md`, `LICENSE`, `LWR_CODEC_PROVENANCE.md`, `tools/rust-oracle/PROVENANCE.md`).
6. Configures a continuous integration matrix verifying supported Python versions (3.12, 3.13, 3.14).
7. Installs cleanly and operates in an isolated virtual environment outside the source tree.

## Verification Matrix
1. **Focused Packaging Suite (`tests/test_packaging_and_distribution.py`):**
   - Package metadata and entry points.
   - Licensing, notices, and source provenance.
   - Wheel and sdist member audits.
   - Bit-exact wheel reproducibility under `SOURCE_DATE_EPOCH`.
   - Clean isolated installation in separate venv and outside-workdir CLI smoke test.
   - Sdist-to-wheel rebuild integrity.
   - CI workflow configuration and matrix.
   - Optional adapter isolation and graceful degradation.
   - Negative tests: prohibited file detection, release tampering digest invalidation, missing schema handling.
2. **Public Regression Suite (`tests/test_*.py`):**
   - All 647 public tests across codecs, requirements, ledger, compositor, timeline, workbench, video, and packaging.
3. **Private Fixture Suite (`tests/private_fixture_hooks/`):**
   - Real lawful asset preservation and decoding checks against private reference assets.
4. **Schema Checker Suite (`scripts/check_*schema*.py`):**
   - All 13 schema checkers.
5. **Distribution Check (`tests/check_distribution.py`):**
   - Full distribution build, sdist verification, repeated wheel reproducibility, isolated venv installation, stdlib-only core smoke test, and test execution.
