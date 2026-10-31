# RSF-23 Independent QA Review Report

**Task ID:** `vn81mars8cnptoeyxxi592po`  
**Ticket ID:** `RSF-23`  
**Title:** `[M5] Modified ACT/SPR writer and metadata-preserving replacements`  
**Milestone:** `M5: Deterministic Sprite Compilation and Native Verification`  
**Reviewer:** Independent Read-Only QA Reviewer (`forge-qa-reviewer`)  
**Verdict:** **QA_PASS** (Scope bounded strictly to M5 compilation core, serializers, CLI, workbench API, and structural/oracle verification; native runtime execution remains truthfully `UNVERIFIED` and deferred to RSF-24).

---

## 1. Review Scope & Files Inspected

- [docs/architecture/RSF23_COMPILER.md](file:///home/ra/Documents/ro-sprite-forge/docs/architecture/RSF23_COMPILER.md)
- [docs/evidence/rsf23/VERIFICATION.md](file:///home/ra/Documents/ro-sprite-forge/docs/evidence/rsf23/VERIFICATION.md)
- [docs/evidence/rsf23/implementation-manifest.json](file:///home/ra/Documents/ro-sprite-forge/docs/evidence/rsf23/implementation-manifest.json)
- [src/ro_sprite_forge/formats/spr.py](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/formats/spr.py)
- [src/ro_sprite_forge/core/compiler.py](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/core/compiler.py)
- [src/ro_sprite_forge/schemas/compilation-manifest-v1.json](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/schemas/compilation-manifest-v1.json)
- [src/ro_sprite_forge/schemas/project-v1.json](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/schemas/project-v1.json)
- [src/ro_sprite_forge/cli.py](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/cli.py)
- [src/ro_sprite_forge/service/workbench.py](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/service/workbench.py)
- [src/ro_sprite_forge/service/server.py](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/service/server.py)
- [src/ro_sprite_forge/static/workbench.js](file:///home/ra/Documents/ro-sprite-forge/src/ro_sprite_forge/static/workbench.js)
- [tests/test_compiler.py](file:///home/ra/Documents/ro-sprite-forge/tests/test_compiler.py)
- [tests/private_fixture_hooks/test_compiler_fixtures.py](file:///home/ra/Documents/ro-sprite-forge/tests/private_fixture_hooks/test_compiler_fixtures.py)
- [scripts/check_compilation_schema.py](file:///home/ra/Documents/ro-sprite-forge/scripts/check_compilation_schema.py)

---

## 2. Independent Test Execution & Verification

All commands executed with `PYTHONDONTWRITEBYTECODE=1`:

1. **Compiler Unit & Integration Test Suite:**
   - Command: `.venv/bin/python -m unittest tests/test_compiler.py -v`
   - Result: `Ran 13 tests in 1.043s` -> **OK (exit 0)**
   - Coverage: ACT & SPR no-op byte preservation, non-minimal RLE preservation, zero-runs > 255, in-place vs appended image replacement, copy-on-write reference isolation across shared image consumers, deduplication of identical replacements, multilayer ordering & hidden clip preservation, lossy indexed palette rejection, single execution of RSF-21 staged recipes, deterministic compilation & atomic directory publication, negative guards & source immutability, CLI `--plan-only` and `compile`, and HTTP workbench endpoints.

2. **Audited Private Fixtures & Independent Rust Oracle Tests:**
   - Command: `.venv/bin/python -m unittest tests/private_fixture_hooks/test_compiler_fixtures.py -v`
   - Result: `Ran 2 tests in 2.883s` -> **OK (exit 0)**
   - Coverage:
     - Male Novice body (104 slots, 456 frames) + head (15 sprites): Walk view 0 replacement affects exactly slot 8; 103 slots and 455 frames remain untouched; head resources preserved 100% byte-exact; verified by independent Rust oracle binary `tools/rust-oracle/target/debug/rsf-rust-oracle` with `AGREEMENT`.
     - Orc Skeleton (40 slots, 512 motions, 1,776 visible layers): 12-layer Death frame (Action 32, Frame 21) preserved with exact layer ordering, clip counts, and bounding box; verified by independent Rust oracle binary with `AGREEMENT`.

3. **Schema Conformance Scripts:**
   - Command: `.venv/bin/python scripts/check_compilation_schema.py`
   - Result: `COMPILATION_SCHEMA_PASS schemas=2 valid=3 invalid=6` -> **OK (exit 0)**
   - All 10 repository schema checkers verified: `ANIMATION`, `COMPARISON`, `COMPILATION`, `COVERAGE`, `EXTRACTION`, `INGESTION`, `LEDGER`, `REVIEW`, `TRANSFORMATION`, and Draft 2020-12 `JSON_SCHEMA_PASS`.

4. **Full Test Discovery & Regressions:**
   - Command: `.venv/bin/python -m unittest discover -s tests -v`
   - Result: `Ran 418 tests in 24.104s` -> **OK (exit 0)**
   - Private fixture hooks discovery: `Ran 38 tests in 15.178s` -> **OK (exit 0)**

5. **Wheel Distribution & Clean stdlib Core Isolation:**
   - Command: `.venv/bin/python tests/check_distribution.py --python "$PWD/.venv/bin/python" --wheelhouse /tmp/rsf4-wheelhouse`
   - Result: `Ran 418 tests in 23.317s` -> `DISTRIBUTION_CHECK_PASS` **(exit 0)**

6. **Implementation Manifest Hash Audit:**
   - Command: `python -c "..."` (verifying all 14 file sizes and SHA-256 digests in `docs/evidence/rsf23/implementation-manifest.json`)
   - Result: `ALL_MANIFEST_HASHES_MATCH` -> **OK (exit 0)**

---

## 3. Acceptance Criteria Evaluation

### Criterion 1: Compile validated images and ordered ACT layers without flattening, retaining supported raw metadata/opaque fields and rejecting unsupported lossless modifications.
- **Status:** **PASS**
- **Findings & Evidence:**
  - `src/ro_sprite_forge/formats/spr.py`: `write_spr()` preserves uncompressed/unmodified RLE streams byte-for-byte via `IndexedImage.raw_rle` without re-compressing or quantizing. `encode_rle()` correctly splits zero-runs greater than 255 into multiple chunks without byte overrun/underrun.
  - `src/ro_sprite_forge/formats/act.py` & `src/ro_sprite_forge/core/compiler.py`: Preserves all 10 opaque reserved header bytes, float32 action delays, global sound event triggers, and signed motion bounding boxes across serialization and decode-after-write verification (`compiler.py:1279-1287`).
  - Multilayer frames retain each clip as an independent layer; layers are never collapsed or flattened (`compiler.py:1218-1223, 1308-1320`).
  - Unsupported operations (lossy palette re-indexing under `indexed_exact`, unexecutable recipes, invalid coordinates, or underspecified layer topologies) are strictly rejected with typed `ForgeError` (`compiler.py:294, 905, 1031-1044`).

### Criterion 2: Bounded Novice action replacement preserves unrelated numeric ACT slots and head resources; classic retained art remains explicitly outside new-art completeness.
- **Status:** **PASS**
- **Findings & Evidence:**
  - Tested on audited Male Novice fixtures (`tests/private_fixture_hooks/test_compiler_fixtures.py:54-266`):
    - Replacing Walk view 0 frame 0 layer 0 modifies exactly 1 slot (slot 8).
    - Unaffected 103 action slots and 455 frames remain byte/structurally untouched (`preservation_summary.untouched_action_slots = 103`).
    - Separate head resources (`head.act` and `head.spr`) are preserved unmodified and separate (`preservation_summary.head_resources_preserved_unchanged = true`).
    - Classic retained art is explicitly declared outside completeness (`preservation_summary.classic_retained_outside_completeness = true`).
    - Compilation manifest marks `status.export_ready = false` and `status.production_authorized = false`.

### Criterion 3: Retain transformed multilayer positions, tint/alpha, events, delays and anchors; meaningful layer order survives serialization.
- **Status:** **PASS**
- **Findings & Evidence:**
  - Layer coordinates `(x, y)`, scaling factors `(scale_x, scale_y)`, rotation angles, mirror flags, and color DWORDs are preserved across serialization and decode-after-write (`compiler.py:1310-1320`).
  - Anchors, sound event IDs, and float32 action delays are verified unchanged (`compiler.py:1280-1286, 1304`).
  - Tested on Orc Skeleton 12-layer Death frame (Action 32, Frame 21) in `test_orc_skeleton_multilayer_compilation_with_oracle`; independent Rust oracle validated parity with zero discrepancies (`schema: rsf.oracle-parity/v1`, result `AGREEMENT`).

### Criterion 4: Source resources remain immutable and compatibility/output policy is explicit.
- **Status:** **PASS**
- **Findings & Evidence:**
  - Original ACT/SPR binaries, source PNG images, and stored blobs remain immutable and content-addressed (`tests/test_compiler.py:1150-1154`).
  - `publish_compilation()` uses atomic filesystem writes and explicitly prohibits overwriting an existing `compilation-manifest.json` (`compiler.py:1511-1515`).
  - Registered candidate resources in workbench are stored as new immutable entities without mutating existing resources (`workbench.py:599-610`).
  - Truthful verification state: manifest schema enforces `native_korangar: "UNVERIFIED"`, preventing premature claims of native playback before RSF-24.

---

## 4. Milestone Gate Statuses

| Gate | Status | Evidence |
|------|--------|----------|
| **M5-S (Structural & Preservation)** | **PASS** | 418 unit tests pass; byte-exact no-op roundtrip verified on synthetic and private fixtures; exact copy-on-write reference isolation. |
| **M5-I (Independent Rust Oracle)** | **PASS** | `rsf-rust-oracle` produces byte-for-byte identical canonical decoded JSON reports for Male Novice and Orc Skeleton compiled pairs. |
| **M5-N (Native Korangar Proof)** | **UNVERIFIED** | Truthfully marked `UNVERIFIED` in `compilation-manifest-v1.json` and compiler manifest output; deferred to RSF-24. |

---

## 5. Summary & Recommendation

RSF-23 meets all architectural, structural, and verification criteria outlined in the v1.1 implementation plan and Kaneo task specification. Code is well-structured, typed, and accompanied by comprehensive synthetic and private fixture regression tests.

**Recommendation:** Proceed to update Kaneo task `vn81mars8cnptoeyxxi592po` to `Accepted`. Next actionable gap is RSF-24 (`[M5] Native Korangar walk playback proof and slot mapping`).
