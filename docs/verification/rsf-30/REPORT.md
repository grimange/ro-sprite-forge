# RSF-30 Implementation and Verification Evidence Report

**Task:** RSF-30 — [M6] Video-derived Walk assignment through the existing compiler  
**Task ID:** `kd4gq1ex5zq2k32rn38yso35`  
**Worker:** AGY (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)  
**Status:** Implementation Complete -> Moving to QA Review  
**Milestone:** M6  

---

## 1. Executive Summary

RSF-30 establishes the end-to-end integration proving that video-derived candidate frames route through the established Sprite Forge asset compilation pipeline without requiring a second compiler, custom animation timing, or automatic artistic approval.

The workflow operates strictly through existing, accepted subsystems:
1. **Video Inspection & Extraction:** Synthetic VFR video (`51f0173b...`) is inspected with exact rational time base `1/1000`. Operator-selected PTS values `[300, 0, 120]` resolve to presentation ordinals `[4, 0, 2]`.
2. **Immutable Staging:** Extracted PNG candidates are validated and staged as content-addressed image blobs (`blob-1c5c...`, `blob-dde9...`, `blob-3e00...`) into the project catalog.
3. **Formal Walk Requirements:** Target declares an explicit Walk scope with inherited layer topology.
4. **Explicit Assignment:** Candidate PNGs map to exact action/view/frame/layer requirement IDs via the RSF-9 assignment ledger.
5. **Compositor Preview:** Preview renders the actual candidate pixels.
6. **Timing Authority Separation:** Source video PTS (`300`, `0`, `120`) remains metadata provenance; ACT playback timing follows declared runtime authority (`movement_speed=100` vs `250`). Reverse independence is verified.
7. **Human Review Boundary:** No automatic approval occurs. Isolated synthetic operator review is recorded. Modifying assignments triggers scoped review invalidation.
8. **Deterministic M5 Compilation:** The existing compiler produces a bounded `PARTIAL_DIAGNOSTIC` ACT/SPR pair.
9. **Independent Rust Verification:** The independent Rust oracle (`rsf-rust-oracle`) verifies exact golden pixel insertion for the 3 targeted Walk occurrences, exact preservation of 51 unaffected occurrences and 6 hidden clips, and zero mismatches.
10. **Reproducibility:** Clean repeated CLI compilations with varied prefixes and `PYTHONHASHSEED` yield bit-for-bit identical binaries.

---

## 2. Video Source & Staging Evidence

- **Synthetic VFR Video SHA-256:** `51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d`
- **Source Presentation PTS Sequence:** `[0, 40, 120, 160, 300]` (time base `1/1000`)
- **Operator Selection:** Nonchronological PTS `[300, 0, 120]`
- **Resolved Presentation Ordinals:** `[4, 0, 2]`
- **Candidate PNG Hashes:**
  - Candidate 0 (ord 4, PTS 300): `1c5c3e4c120ee8a2861bf12636a1b96344f578171f7543869ea4a8b437883382`
  - Candidate 1 (ord 0, PTS 0): `dde9003e6bd1bca8db19eaeb40b24733bbbf4dac8a934f0314cbc4b96f780ef9`
  - Candidate 2 (ord 2, PTS 120): `3e00777e379eecd20d3385f45bcd00b3d85d525d45c50318cbc0634f3f6f8989`
- **Blob Staging:** Staged into content-addressed blob store as `blob-<sha256>` with `availability='AVAILABLE'`, `validation='VALID'`. Idempotent staging preserves project revision and prevents duplicate sequences.

---

## 3. Timing Authority Separation

- **Video Authority:** Preserves exact source PTS (`300`, `0`, `120`), rational time base (`1/1000`), and presentation ordinals (`4`, `0`, `2`).
- **ACT/Runtime Authority:** Runtime playback timing is governed by ACT action delays and movement speed context.
- **Independence Verified:**
  - Changing `movement_speed` from 100 to 250 alters frame playback duration in the compositor according to the Korangar movement speed formula.
  - Video PTS, candidate hashes, time base, and extraction provenance in `video_imports` remain completely unchanged.
  - Reordering video extraction candidates (`[300, 120, 0]`) does not modify ACT frame delays or timing definitions.

---

## 4. Compilation & Independent Rust Verification

- **Compilation Mode:** Bounded replacement (`bounded_replacement`), policy `explicit_rgba`.
- **Classification:** `PARTIAL_DIAGNOSTIC` (`production_authorized=false`, `PARTIAL_DIAGNOSTIC.txt` generated).
- **Independent Rust Oracle:** Direct binary execution of `tools/rust-oracle/target/debug/rsf-rust-oracle`:
  - Targeted occurrences: 3 (Walk view 0 frames 0, 1, 2) -> resolved to exact 16x16 candidate PNG pixels.
  - Unaffected occurrences: 51 -> byte-exact match with original 4x4 image pixels.
  - Hidden clips: 6 -> preserved with raw clip ordinals and attributes.
  - Mismatches: 0.
  - Whole ACT equality: delays, bounds, anchors, and metadata outside targeted references are identical.
- **Deterministic Repeated Compilation:** Two independent CLI compilations in separate directories with varied `PYTHONHASHSEED` and output prefixes produced bit-for-bit identical ACT, SPR, and build manifest bytes.

---

## 5. Test Suite Execution & Exit Codes

All test commands executed with exit code 0:

| Test Suite | Command | Result | Evidence Log |
|---|---|---|---|
| Focused Video Walk Integration | `.venv/bin/python -m unittest discover -s tests -p test_video_walk_compilation.py -v` | 10 PASS | `focused.log` |
| Full Public Test Suite | `.venv/bin/python -m unittest discover -s tests -v` | 514 PASS | `public.log` |
| Private Fixture Suite | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 40 PASS, 1 legacy skip | `private.log` |
| All Schema Validators | 11 `scripts/check_*schema*.py` scripts | 11 PASS | `schemas.log` |
| Installed Distribution | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | 514 PASS, 12 optional skips | `distribution.log` |

---

## 6. Milestone & Native Boundaries

- **Production Readiness:** Scoped diagnostic Walk coverage does not satisfy full actor completeness (`export_ready=false`, `completeness='INCOMPLETE'`). Production export mode fails closed if attempted.
- **Native GPU Status:** Retains previous M5 native proof scope. The new video-derived compiled output is truthfully recorded as `UNVERIFIED` for native playback.
