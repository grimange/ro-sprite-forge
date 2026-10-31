# RSF-31 Implementation and Verification Evidence Report

**Task:** RSF-31 — [M6] VFR, candidate-frame diagnostics and repeatability verification  
**Task ID:** `r9wtccay03qkpx6i4jco8971`  
**Worker:** AGY (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)  
**Status:** Implementation Complete -> Moving to QA Review  
**Milestone:** M6  

---

## 1. Executive Summary

RSF-31 consolidates comprehensive verification, candidate-frame diagnostics, and repeatability evidence across the entire optional video-ingestion pipeline established in M6 (RSF-28, RSF-29, RSF-30).

A dedicated, comprehensive test suite of 25 focused verification scenarios was implemented in `tests/test_vfr_diagnostics.py` covering:
1. **CFR Exact Presentation Identity:** Validated sequential PTS `[0, 40, 80, 120, 160]`, rational time base `1/1000`, `REGULAR_PTS_OBSERVED` timing flag, display ordinals `[0, 1, 2, 3, 4]`, and exact decoded RGBA pixels against synthetic patterns.
2. **VFR Presentation Identity & Irregular Intervals:** Validated irregular PTS `[0, 40, 120, 160, 300]`, intervals `[40, 80, 40, 140]`, `IRREGULAR_PTS` timing classification, without nominal-FPS approximation.
3. **Nonchronological Selection:** Requested PTS `[300, 0, 120]` resolved to ordinals `[4, 0, 2]`; extracted PNG candidates strictly preserved declared operator selection order.
4. **Presentation vs Decode Ordering:** B-frame container verified distinguishing decode order from presentation order while preserving presentation PTS.
5. **Duplicate PTS Diagnostics:** Synthetic fixture with duplicate PTS 40 rejected on exact PTS request with typed diagnostic `VIDEO_SELECTION_NOT_EXACT: pts=40; matches=2`; explicit ordinal selection `[1, 2]` succeeded unambiguously.
6. **Missing & Invalid PTS:** Absent PTS (e.g. 80 in VFR fixture) and `None` timestamps rejected fail-closed with `VIDEO_SELECTION_NOT_EXACT: pts=80; matches=0` without nearest-frame substitution or invented timestamps.
7. **Selection & Dimension Limits:** Values exceeding JavaScript safe integer bound ($2^{53}-1$), empty lists, quota violations (>64 candidates), duplicate requested values, and invalid modes rejected before starting any subprocess.
8. **Rational Time-Base & Large Precision:** Fractions (`1/1000`, `1/90000`, `1001/30000`) preserved as exact integer numerator/denominator pairs; large metadata values preserved as strings in wire records via `browser_safe()`.
9. **Known-Pixel Correctness:** Decoded candidate PNG pixels unpacked with Pillow and verified against independent synthetic RGB pixel buffers with 0 mismatch.
10. **Repeatability & Provenance:** Repeated clean extractions in different temporary directories produced bit-for-bit identical PNG bytes and canonical manifest SHA-256 hashes under the pinned toolchain.
11. **Idempotent Staging & Failure Preservation:** Re-staging identical media did not duplicate sequence imports or bump project revision; failed mutations left project manifest and revision unincremented.
12. **Separation of Authorities:** Video presentation timestamps remained metadata provenance; ACT playback delays and movement speed context remained independent runtime authorities.
13. **Coverage Reconciliation:** Fully reconciled RSF-30 scoped Walk arithmetic: $12\text{ required layers} = 3\text{ assigned} + 9\text{ unassigned}$, resolving the review question.
14. **End-to-End Regression:** Video-derived Walk slice compiled through accepted M5 compiler and verified with independent Rust oracle (`result='AGREEMENT'`).

---

## 2. Media Baseline & Frame Identity Evidence

### CFR Baseline
- **Source Video SHA-256:** `429db0f589999b17906d33923055740445d4f10738d2f0eb363c46e16668705a` (synthetic FFV1 CFR)
- **Time Base:** `1/1000` (rational: `numerator=1`, `denominator=1000`)
- **Observed Presentation PTS:** `[0, 40, 80, 120, 160]`
- **Presentation Ordinals:** `[0, 1, 2, 3, 4]`
- **Timing Classification:** `REGULAR_PTS_OBSERVED`
- **Candidate Decoded Pixels:** Extracted frames match known synthetic mathematical RGB patterns with zero bit discrepancies.

### VFR Baseline
- **Source Video SHA-256:** `51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d` (synthetic FFV1 VFR)
- **Time Base:** `1/1000`
- **Observed Presentation PTS:** `[0, 40, 120, 160, 300]`
- **Presentation Intervals:** `[40, 80, 40, 140]`
- **Timing Classification:** `IRREGULAR_PTS`
- **Operator Selection:** Nonchronological `[300, 0, 120]` -> resolved ordinals `[4, 0, 2]`
- **Extracted PNG SHA-256:**
  - Candidate 0 (ordinal 4, PTS 300): `1c5c3e4c120ee8a2861bf12636a1b96344f578171f7543869ea4a8b437883382`
  - Candidate 1 (ordinal 0, PTS 0): `dde9003e6bd1bca8db19eaeb40b24733bbbf4dac8a934f0314cbc4b96f780ef9`
  - Candidate 2 (ordinal 2, PTS 120): `3e00777e379eecd20d3385f45bcd00b3d85d525d45c50318cbc0634f3f6f8989`

---

## 3. Duplicate and Missing PTS Diagnostics

### Duplicate PTS
- **Synthetic Duplicate Fixture:** `duplicate_pts.mkv`, PTS sequence `[0, 40, 40, 120, 160]`.
- **Exact PTS Selection `[40]`:** Raises `ForgeError(INVALID_INPUT, 'VIDEO_SELECTION_NOT_EXACT: pts=40; matches=2')`.
- **Policy:** Ambiguous PTS requests fail closed; silent nearest or first-duplicate selection is prohibited.
- **Disambiguation:** Ordinal selection `[1, 2]` remains unambiguous and succeeds, extracting distinct candidate PNGs.

### Missing & Invalid PTS
- **Absent PTS (e.g. PTS 80 in VFR fixture):** Raises `ForgeError(INVALID_INPUT, 'VIDEO_SELECTION_NOT_EXACT: pts=80; matches=0')`.
- **Out of Range (e.g. PTS 9999):** Raises `VIDEO_SELECTION_NOT_EXACT`.
- **Missing PTS Metadata (`pts=None`):** Fails closed without inventing timestamps or substituting adjacent frames.

---

## 4. Coverage Reconciliation (RSF-30 Arithmetic)

The RSF-30 review raised a question regarding coverage accounting: why 3 occurrences were assigned and 12 unassigned in declared scope vs missing directions and frames.

Verification in `test_24_rsf30_coverage_reconciliation` conclusively establishes the exact arithmetic:
1. **Target Structure:** Monster Walk profile contains 8 action view slots (slots 8 to 15, corresponding to views 0 to 7).
2. **View 0 Layer Occurrences:** View 0 contains 4 frames:
   - Frame 0: 1 layer (Layer 0) -> 1 occurrence
   - Frame 1: 1 layer (Layer 0) -> 1 occurrence
   - Frame 2: 2 layers (Layer 0, Layer 1) -> 2 occurrences
   - Frame 3: 1 layer (Layer 0) -> 1 occurrence
   *Subtotal View 0:* 5 layer occurrences across 4 frames.
3. **Views 1 to 7 Layer Occurrences:** Each of views 1 through 7 has 1 frame with 1 layer:
   *Subtotal Views 1..7:* $7 \times 1 \times 1 = 7$ layer occurrences across 7 frames.
4. **Total Required Counts:**
   - Required slots: 8
   - Required frames: $4 + 7 = 11$
   - Required layers: $5 + 7 = 12$
5. **Assignment Breakdown (after assigning 3 candidates to View 0 frames 0, 1, 2 layer 0):**
   - **Direct Assignments:** 3 occurrences (View 0, Frame 0 Layer 0; View 0 Frame 1 Layer 0; View 0 Frame 2 Layer 0)
   - **Unassigned Occurrences:** 9 occurrences:
     - View 0, Frame 2, Layer 1 (second layer in composite frame) -> 1 occurrence
     - View 0, Frame 3, Layer 0 (fourth frame in direction) -> 1 occurrence
     - Views 1 through 7, Frame 0, Layer 0 (7 missing walk directions) -> 7 occurrences
     *Subtotal Unassigned:* $1 + 1 + 7 = 9$ occurrences.
6. **Reconciliation Equation:**
   $$\text{required\_layers}\ (12) = \text{direct}\ (3) + \text{unassigned}\ (9)$$
   $$\text{required\_layers}\ (12) = \text{review\_artwork}\ (3) + \text{supply\_artwork}\ (9)$$
   All nonoverlapping categories sum to 12. Full actor completeness remains truthfully reported as `completeness='INCOMPLETE'`, `assignment_coverage='PARTIAL'`, `export_ready=False`.

---

## 5. Toolchain Repeatability & Provenance

- **Pinned Environment:** Ubuntu Linux, kernel 7.0.0-42, Python 3.14.4, FFmpeg 8.0.1-3ubuntu2, FFprobe 8.0.1-3ubuntu2, Pillow 12.1.1.
- **Repeatability Runs:** Multiple clean invocations across independent temporary directories with varied `tempfile` roots and process seeds produced:
  - Exact identical candidate PNG payloads (SHA-256 identical).
  - Exact identical RGBA pixel digests.
  - Bit-for-bit identical canonical candidate manifest JSON bytes (`canonical_bytes`).
  - Bit-for-bit identical candidate collection SHA-256 hashes.
- **Toolchain Provenance in Manifest:** Includes FFmpeg/FFprobe version strings, executable SHA-256 hashes, version report hashes, and bitexact extraction arguments (`-cpuflags 0`, `-filter_threads 1`, `-threads:v 1`, `-bitexact`, `-fps_mode passthrough`).

---

## 6. Test Suite Execution & Exit Codes

All test commands executed with exit code 0:

| Test Suite | Command | Result | Evidence Log |
|---|---|---|---|
| Focused VFR Diagnostics Suite | `PYTHONPATH=tests:src .venv/bin/python -m unittest discover -s tests -p test_vfr_diagnostics.py -v` | 25 PASS | `focused.log` |
| Full Public Test Suite | `PYTHONPATH=tests:src .venv/bin/python -m unittest discover -s tests -v` | 539 PASS | `public.log` |
| Private Fixture Suite | `PYTHONPATH=tests:src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 40 PASS, 1 legacy skip | `private.log` |
| All Schema Validators | 11 `scripts/check_*schema*.py` scripts | 11 PASS | `schemas.log` |
| Installed Distribution | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | 539 PASS, 12 optional skips | `distribution.log` |

---

## 7. Milestone Gate Evaluation: M6 Closure

With RSF-31 verified and passing all acceptance criteria:
- **RSF-28 (M6-01):** Accepted (FFprobe/FFmpeg candidate-frame import)
- **RSF-29 (M6-02):** Accepted (Operator frame selection & timing separation)
- **RSF-30 (M6-03):** Accepted (Video-derived Walk compilation through existing compiler)
- **RSF-31 (M6-04):** Verified & Complete (VFR diagnostics, candidate identity & repeatability)

**Authoritative M6 Gate Verdict:** **`M6_PASS`**  
The entire M6 milestone scope is complete, verified, and ready for closure.
