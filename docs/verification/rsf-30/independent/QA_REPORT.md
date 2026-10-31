# RSF-30 independent QA

Verdict: **QA_PASS**. Reviewer: separate configured `forge_qa_reviewer` context.
The reviewer changed no source files, made no Kaneo writes, took no ownership and granted no real artwork approval.
The coordinator archived this returned verdict.

All four live checklist items passed:

1. Formal Walk target uses declared inherited layer topology (`kind='inherited'`, `slot=8..15`).
   Synthetic VFR video (`51f0173b...`) inspected with exact rational time base `1/1000` and explicit operator selection of nonchronological PTS `[300, 0, 120]`, mapping to presentation ordinals `[4, 0, 2]`. Staging creates immutable content-addressed blobs (`blob-<sha256>`). Operator review records approval on exact composition revision; changing assigned source invalidates affected approval to `STALE`.
2. Video-derived candidates route directly through the canonical RSF-9 ledger and existing M5 compiler without video-specific branching.
   Independent Rust oracle (`rsf-rust-oracle`) verifies:
   - 3 targeted Walk occurrences inserted with bit-exact 16x16 PNG candidate pixels.
   - 51 unaffected occurrences preserved bit-for-bit against original 4x4 image pixels.
   - 6 hidden clips preserved with raw attributes.
   - 0 mismatches.
   - Whole ACT metadata, anchors, delays, and bounds outside targeted references are identical.
   Clean repeated CLI builds produce deterministic bit-for-bit identical outputs.
3. Unassigned coverage truthfully reports `export_ready=False`, `completeness='INCOMPLETE'`, and `unassigned=12` layer occurrences. Only view 0 (frames 0, 1, 2) is assigned; views 1–7 remain missing. Compiled output produces `PARTIAL_DIAGNOSTIC.txt` with `export_label='PARTIAL_DIAGNOSTIC'` and `production_authorized=False`. Premature production export fails closed.
4. Video provenance preserves exact source PTS `[300, 0, 120]`, presentation ordinals `[4, 0, 2]`, and rational time base `1/1000` in `video_imports`. ACT runtime playback timing is governed by ACT action delays and movement speed (`movement_speed=100` vs `250`). Modifying movement speed leaves video PTS and extraction metadata intact. Reordering video extraction candidates does not mutate ACT frame delays. Native playback for this video-derived output is truthfully recorded as `UNVERIFIED`.

## Independently executed checks

| # | Check / Suite | Command | Result | Exit Code |
|---|---|---|---|---|
| 1 | Focused Video Walk Integration | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p test_video_walk_compilation.py -v` | 10 passed in 6.005s | `0` |
| 2 | Full Public Test Suite | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v` | 514 passed in 41.553s | `0` |
| 3 | Private Audited Fixture Suite | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 40 passed, 1 skipped (legacy RSF-6 native run evidence) in 22.600s | `0` |
| 4 | Schema Validators | `for s in scripts/check_*schema*.py; do PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$s" || exit 1; done` | 11 passed | `0` |
| 5 | Installed Distribution Check | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | 514 passed in isolated venv (12 skipped for environment tools) in 37.749s, `DISTRIBUTION_CHECK_PASS` | `0` |

Verdict: **QA_PASS**
