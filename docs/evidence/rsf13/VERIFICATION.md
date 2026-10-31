# RSF-13 Verification Evidence Packet

## Task Identity
- **Task ID**: `sr7zifcthz9m09btrmjlaosv` (RSF-13)
- **Title**: `[M2] Reference comparison and exported preview diagnostics`
- **Milestone**: M2
- **Author**: Codex / Antigravity Implementation Session
- **Status**: Implemented, verified locally, ready for independent QA Review

---

## Deliverables & Component Architecture

1. **Packaged Draft 2020-12 Schemas** (`src/ro_sprite_forge/schemas/`):
   - `preview-comparison-v1.json` (`rsf.preview-comparison/v1`)
   - `contact-sheet-v1.json` (`rsf.contact-sheet/v1`)
   - `sequence-manifest-v1.json` (`rsf.sequence-manifest/v1`)
2. **Comparison & Overlay Core** (`src/ro_sprite_forge/core/comparison.py`):
   - `compare_frames(...)`: Unified frame comparison with mode selection, alignment policies, and objective difference metrics.
   - `apply_overlays(...)`: Visual diagnostic overlays (`origin`, `bounds`, `anchors`, `layers`) with strict overlay isolation.
   - `compute_difference(...)`: Objective pixel differences, alpha differences, max channel differences, and mean absolute channel differences.
   - `create_side_by_side(...)`: Reference vs candidate side-by-side composition.
   - `blend_onion_skin(...)`: Alpha-composited onion-skin frame blending.
3. **Contact Sheet & Sequence Export Core** (`src/ro_sprite_forge/core/contact_sheet.py`):
   - `generate_contact_sheet(...)`: $M \times N$ grid arrangement with integer nearest-neighbor scaling and optional ordinal labels.
   - `export_frame_sequence(...)`: Atomic frame export with temporary staging and canonical `sequence-manifest.json`.
4. **CLI Subcommands** (`src/ro_sprite_forge/cli.py`):
   - `compare`: Reference vs candidate comparison CLI.
   - `contact-sheet`: Grid filmstrip generation CLI.
   - `sequence`: Atomic frame sequence export CLI.
5. **Test & Validation Suites**:
   - `scripts/check_comparison_schema.py`: Offline schema validator (checked 3 schemas, 11 valid instances, 13 malformed negative cases).
   - `tests/test_comparison.py`: 16 comprehensive synthetic unit tests.
   - `tests/private_fixture_hooks/test_comparison_fixtures.py`: Audited Novice (Walk, body+head) and Orc Skeleton (Death, 22 frames, up to 12 layers) tests.

---

## Invariants & Gate Verification

- **Strict Overlay Isolation**: When `overlays` are empty or omitted, rendered output is bit-for-bit identical to raw preview rendering. When overlays are active, the canonical report's `ref["png_sha256"]` continues to record the pristine raw render hash.
- **Candidate Absence Handling**: When a candidate is not supplied, the workbench exports reference-only diagnostics (`comparison_status: "MISSING_CANDIDATE"`). No fallback art is fabricated.
- **Artistic Quality Authority**: Algorithms evaluate objective metrics only (`artistic_approval: "UNVERIFIED"`, `technical_difference_only: true`). Human operator retains exclusive aesthetic review.
- **Preview Parity State**: Reports declare `overall: "PARTIAL"`, `native_pixel_parity: "UNVERIFIED"`.

---

## Verification Results Summary

| Verification Gate | Command | Result | Details |
| :--- | :--- | :--- | :--- |
| Synthetic Unit Tests | `python -m unittest tests/test_comparison.py` | **PASS** | 16/16 tests passing (0.364s) |
| Full Public Test Suite | `python -m unittest discover -s tests -p 'test_*.py'` | **PASS** | 245/245 tests passing (3.228s) |
| Audited Private Fixtures | `python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'` | **PASS** | 32/32 tests passing (5.598s) |
| Offline Schema Validator | `python scripts/check_comparison_schema.py` | **PASS** | 3 schemas verified, 11 valid, 13 rejected |
| Package & Wheel Distribution | `python tests/check_distribution.py ...` | **PASS** | `DISTRIBUTION_CHECK_PASS` in isolated venv |
| Reproducible Examples | `python docs/evidence/rsf13/reproduce_examples.py` | **PASS** | 8 examples generated in `examples.json` |
