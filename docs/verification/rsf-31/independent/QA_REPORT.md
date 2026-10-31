# Independent QA Review Report — RSF-31

**Task:** RSF-31 — [M6] VFR, candidate-frame diagnostics and repeatability verification  
**Task ID:** `r9wtccay03qkpx6i4jco8971`  
**Milestone:** M6  
**Implementation Review:** [`tests/test_vfr_diagnostics.py`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py) (SHA-256: `0cc8b6ed7de5a968b535470e181dd408b499576884c9c9d92136bd5c5f223c7a`)  
**Evidence Packet:** [`docs/verification/rsf-31/`](file:///home/ra/Documents/ro-sprite-forge/docs/verification/rsf-31/)  
**Reviewer Mode:** Independent read-only verification  
**Overall Verdict:** **`QA_PASS`**

---

## 1. Acceptance Criteria Verification Matrix

| Acceptance Criterion | Result | Evidence / Repro |
|---|---|---|
| **1. VFR fixtures preserve correct PTS and display order without silently assuming constant fps.** | **PASS** | [`test_01_cfr_exact_frame_identity`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L108-L133), [`test_02_vfr_exact_frame_identity`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L137-L150), [`test_04_presentation_order_and_b_frames`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L177-L198), [`test_09_rational_time_base_preservation`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L299-L313):<br>• CFR sequential PTS `[0, 40, 80, 120, 160]`, ordinals `[0, 1, 2, 3, 4]`, rational time base `1/1000`, `REGULAR_PTS_OBSERVED`.<br>• VFR irregular intervals `[40, 80, 40, 140]`, PTS `[0, 40, 120, 160, 300]`, `IRREGULAR_PTS` flag, zero nominal-FPS approximation.<br>• B-frame container decouples presentation order from decode order; presentation PTS preserved.<br>• Time bases parsed as integer numerator/denominator pairs without float rounding. |
| **2. Skipped, dropped or duplicated candidates are visible with source/frame identities; selected output and ACT timing remain explicit.** | **PASS** | [`test_03_nonchronological_pts_selection`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L154-L173), [`test_05_duplicate_pts_diagnostics`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L202-L223), [`test_06_missing_pts_diagnostics`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L227-L245), [`test_07_invalid_ordinal_rejection`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L249-L265), [`test_08_out_of_range_selection_rejection`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L269-L295), [`test_12_selection_output_count_consistency`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L352-L360), [`test_14_candidate_order_identity`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L392-L407), [`test_22_no_auto_assignment_or_approval`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L537-L556), [`test_23_video_act_timing_separation`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L560-L580):<br>• Ambiguous PTS request (PTS 40 in `duplicate_pts.mkv`) fails closed with `VIDEO_SELECTION_NOT_EXACT: pts=40; matches=2`. Ordinal selection `[1, 2]` succeeds unambiguously.<br>• Absent PTS (e.g. PTS 80 in VFR fixture) fails closed with `VIDEO_SELECTION_NOT_EXACT: pts=80; matches=0` (no nearest-frame fallback).<br>• Out-of-range ordinals, negative ordinals, non-integer inputs, empty lists, candidate limit (>64) and duplicate selection values fail closed.<br>• Nonchronological selection `[300, 0, 120]` maps to `[4, 0, 2]` and preserves request order.<br>• Staging video candidates does not create automatic assignments or visual approvals.<br>• Video presentation timestamps remain metadata provenance while ACT action delays (`delays[8] == 6.0`) remain independent runtime authorities. |
| **3. Repeated imports/selections/builds under pinned settings preserve frame hashes, timestamps and deterministic artifact hashes.** | **PASS** | [`test_10_large_metadata_integer_precision`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L317-L334), [`test_11_known_pixel_candidate_verification`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L338-L348), [`test_13_idempotent_reimport`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L364-L388), [`test_15_exact_source_sha256_verification`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L411-L425), [`test_16_repeated_clean_ffmpeg_execution`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L429-L446), [`test_17_canonical_manifest_byte_identity`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L450-L469), [`test_18_toolchain_provenance`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L473-L484), [`test_19_failed_extraction_cleanup`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L488-L494), [`test_20_failed_publication_preservation`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L498-L512):<br>• Multiple clean extractions yield bit-exact candidate PNGs, pixel digests, and canonical manifest JSON SHA-256.<br>• Re-staging identical video and selection is idempotent (no duplicate imports, revision unincremented).<br>• Decoded candidate pixels match known synthetic RGB patterns with 0 discrepancies.<br>• Large metadata integers (>2^53-1) preserved as strings in wire records via `browser_safe()`.<br>• Source SHA-256 mismatch rejects upfront before executing external tools.<br>• Failed mutations leave project manifest intact; failed extractions clean up temporary directories. |
| **4. Verification reports missing tooling, unsupported codecs and native NOT_RUN separately; selective LWR hashing/PTS/landmark reuse records provenance rather than importing unrelated modules.** | **PASS** | [`test_21_optional_dependency_absence`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L516-L534), [`test_24_rsf30_coverage_reconciliation`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L584-L675), [`test_25_existing_video_walk_compilation_regression`](file:///home/ra/Documents/ro-sprite-forge/tests/test_vfr_diagnostics.py#L679-L754):<br>• Absence of FFmpeg/FFprobe detected cleanly: `capabilities()` returns `available=False`, media calls raise `VIDEO_TOOL_UNAVAILABLE`, pure core remains functional.<br>• Full toolchain provenance recorded in candidate manifest (paths, versions, executable SHA-256).<br>• RSF-30 coverage arithmetic fully reconciled ($12\text{ required} = 3\text{ direct} + 9\text{ unassigned}$; $12 = 3\text{ review\_artwork} + 9\text{ supply\_artwork}$).<br>• Full video Walk compilation verified against independent Rust oracle binary (`result='AGREEMENT'`).<br>• Private fixture suite native verification skip reported accurately (`test_native_rsf6_structural_parity`: skipped 'Native RSF-6 run evidence not present in /tmp/rsf6-native-run-final-1'). |

---

## 2. Independent Test Execution Results

All commands executed cleanly with exit status 0:

1. **Focused VFR Diagnostics Suite (25 tests):**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests:src .venv/bin/python -m unittest discover -s tests -p test_vfr_diagnostics.py -v
   ```
   **Output:** `Ran 25 tests in 6.594s` — **`OK`** (exit 0)

2. **Full Public Test Suite (539 tests):**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests:src .venv/bin/python -m unittest discover -s tests -v
   ```
   **Output:** `Ran 539 tests in 47.463s` — **`OK`** (exit 0)

3. **Private Fixture Suite (41 tests):**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests:src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v
   ```
   **Output:** `Ran 41 tests in 22.528s` — **`OK (skipped=1)`** (exit 0; 40 PASS, 1 legacy native skip)

4. **Schema Check Scripts (11 scripts):**
   ```bash
   export PYTHONDONTWRITEBYTECODE=1 && for s in scripts/check_*schema*.py; do .venv/bin/python "$s" || exit 1; done
   ```
   **Output:** All 11 scripts passed (`ANIMATION_SCHEMA_PASS`, `COMPARISON_SCHEMA_PASS`, `COMPILATION_SCHEMA_PASS`, `JSON_SCHEMA_PASS`, `COVERAGE_SCHEMA_PASS`, `EXTRACTION_SCHEMA_PASS`, `INGESTION_SCHEMA_PASS`, `LEDGER_SCHEMA_PASS`, `REVIEW_SCHEMA_PASS`, `TRANSFORMATION_SCHEMA_PASS`, `VIDEO_SCHEMA_PASS`) — **`OK`** (exit 0)

5. **Installed Distribution Verification (isolated venv wheel install):**
   ```bash
   export PYTHONDONTWRITEBYTECODE=1 && .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14
   ```
   **Output:** `Ran 539 tests in 43.364s` — **`OK (skipped=12)`**, `DISTRIBUTION_CHECK_PASS` (exit 0)

---

## 3. RSF-30 Coverage Accounting Reconciliation

The question raised during RSF-30 review regarding why 3 occurrences were assigned and 12 unassigned is completely explained and validated in `test_24_rsf30_coverage_reconciliation`:
- **Monster Walk Action Profile:** 8 action view slots (slots 8 to 15, corresponding to views 0 through 7).
- **View 0 occurrences:** 4 frames total:
  - Frame 0: 1 layer (Layer 0) = Occurrence 1
  - Frame 1: 1 layer (Layer 0) = Occurrence 2
  - Frame 2: 2 layers (Layer 0, Layer 1) = Occurrences 3 and 4
  - Frame 3: 1 layer (Layer 0) = Occurrence 5
  - *Subtotal View 0:* 5 layer occurrences across 4 frames.
- **Views 1 to 7 occurrences:** 7 views $\times$ 1 frame $\times$ 1 layer = 7 occurrences across 7 frames.
- **Total Required:** 8 slots, 11 frames, 12 layer occurrences.
- **After assigning 3 video candidates to View 0 (frames 0, 1, 2, layer 0):**
  - **Direct Assignments:** 3 occurrences.
  - **Unassigned Occurrences:** 9 occurrences (View 0 Frame 2 Layer 1; View 0 Frame 3 Layer 0; 7 directional frames for Views 1..7).
  - **Reconciliation Equations:**
    $$\text{required\_layers}\ (12) = \text{direct}\ (3) + \text{unassigned}\ (9)$$
    $$\text{required\_layers}\ (12) = \text{review\_artwork}\ (3) + \text{supply\_artwork}\ (9)$$
  - Full actor status correctly reflects `completeness='INCOMPLETE'`, `assignment_coverage='PARTIAL'`, `export_ready=False`.

---

## 4. Final Verdict and Gate Assessment

- **RSF-31 Verdict:** **`QA_PASS`**
- **Milestone Gate M6 Status:** With RSF-28, RSF-29, RSF-30 accepted and RSF-31 verified passing all 4 acceptance criteria with independent test execution, the M6 milestone requirements are satisfied:
  - **Authoritative Gate:** **`M6_PASS`**
