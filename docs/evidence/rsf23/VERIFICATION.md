# RO Sprite Forge — RSF-23 Implementation & Verification Evidence

## Task Identification
- **Task ID:** `vn81mars8cnptoeyxxi592po`
- **Ticket ID:** `RSF-23`
- **Title:** `[M5] Modified ACT/SPR writer and metadata-preserving replacements`
- **Milestone:** `M5: Deterministic Sprite Compilation and Native Verification`
- **Implementer:** `ICJQmirJliEFAZN3jBl3ZitHCandT0FG` ("AGY")

---

## Acceptance Criteria Verification Summary

### Criterion 1: Compile validated images and ordered ACT layers without flattening, retaining supported raw metadata/opaque fields and rejecting unsupported lossless modifications.
- **Status:** **VERIFIED**
- **Evidence:**
  - `src/ro_sprite_forge/formats/spr.py`: Implemented exact zero-run RLE encoder `encode_rle(pixels)` and binary serializer `write_spr(doc)` supporting byte-exact preservation of untouched indexed sprites, palettes, and RGBA truecolor pool additions.
  - `src/ro_sprite_forge/formats/act.py`: Validated ACT 2.4 serializer `write_act(doc)` preserving all 10 opaque reserved bytes, 8-integer motion bounding boxes, uint32 color DWORDs, scale, angle, and delay multipliers.
  - `src/ro_sprite_forge/core/compiler.py`: Implemented non-flattening multilayer compilation where individual visual layers remain distinct ACT clips; rejects unsupported operations (e.g. unexecutable recipes) with typed `ForgeError(ErrorCode.INVALID_INPUT)`.
  - Automated tests: `tests/test_compiler.py` (`test_01_synthetic_exact_noop_preservation`, `test_04_multilayer_preservation_and_non_flattening`, `test_05_unsupported_modifications_rejected`).

### Criterion 2: Bounded Novice action replacement preserves unrelated numeric ACT slots and head resources; classic retained art remains explicitly outside new-art completeness.
- **Status:** **VERIFIED**
- **Evidence:**
  - `src/ro_sprite_forge/core/compiler.py`: Tested replacement of bounded Novice Walk view 0; unreplaced classic slots (Idle, Attack, Hit, Die, etc., covering 103 of 104 slots and 455 of 456 frames) remain untouched.
  - Head resources (`head.act` and `head.spr`) are preserved separate and unmodified without merging into the body sprite pool (`preservation_summary.head_resources_preserved_unchanged = true`).
  - Retained classic art is explicitly declared outside new-art completeness in `preservation_summary.classic_retained_outside_completeness = true`.
  - Manifest marks `status.export_ready = false` and `status.production_authorized = false`.
  - Automated tests: `tests/test_compiler.py` (`test_02_bounded_action_replacement_preserves_unrelated_slots`, `test_03_head_resources_preserved_separate_and_unmodified`) and `tests/private_fixture_hooks/test_compiler_fixtures.py` (`test_novice_bounded_walk_replacement_with_oracle_and_head_preservation`).

### Criterion 3: Retain transformed multilayer positions, tint/alpha, events, delays and anchors; meaningful layer order survives serialization.
- **Status:** **VERIFIED**
- **Evidence:**
  - Clip positioning `(x, y)`, scaling factors `(scale_x, scale_y)`, rotation angles, mirror flags, and color DWORDs are preserved across ACT 2.4 serialization.
  - Per-frame attachment anchors, action delays, and sound events survive round-trip compilation and deserialization.
  - 12-layer Orc Skeleton Death animation frame (Action 32, Frame 21) round-trips with layer order, clip count, and bounding box identically preserved.
  - Independent Rust oracle (`rsf-rust-oracle`) validates both Novice body+head and Orc Skeleton compiled binaries with zero corruption or discrepancies.
  - Automated tests: `tests/test_compiler.py` (`test_04_multilayer_preservation_and_non_flattening`, `test_06_clip_transforms_tint_alpha_and_anchors_preserved`, `test_07_delays_and_events_preserved`) and `tests/private_fixture_hooks/test_compiler_fixtures.py` (`test_orc_skeleton_multilayer_compilation_with_oracle`).

### Criterion 4: Source resources remain immutable and compatibility/output policy is explicit.
- **Status:** **VERIFIED**
- **Evidence:**
  - Source resources and input blobs remain immutable and content-addressed (`src/ro_sprite_forge/service/workbench.py` and `src/ro_sprite_forge/core/compiler.py`).
  - Bounded outputs are written to atomic directories via `publish_compilation()`, and optionally registered as distinct candidate resources (e.g. `monster-compiled`) without altering the original imported reference.
  - Truecolor RGBA replacement policy is explicit (`replacement_policy="explicit_rgba"`), preserving full color depth in Pool 1 without silent palette quantization.
  - Manifest explicitly records `native_korangar: "UNVERIFIED"`, truthfully deferring native execution proof to RSF-24.
  - Automated tests: `tests/test_compiler.py` (`test_08_immutable_source_preservation`, `test_09_explicit_rgba_policy_and_isolation_strategy`, `test_10_native_korangar_truthful_unverified_status`) and browser test `tests/browser/rsf23-mcp.js`.

---

## Test Suite Execution Evidence

1. **Compiler Unit & Integration Tests:**
   ```bash
   .venv/bin/python -m unittest tests/test_compiler.py -v
   ```
   *Result:* Ran 13 tests in 1.482s, `OK` (exit code 0).

2. **Audited Private Fixture & Rust Oracle Tests:**
   ```bash
   .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v
   ```
   *Result:* Ran 38 tests in 15.570s, `OK` (exit code 0). Both Novice Walk replacement and Orc Skeleton multilayer compilation validated by independent Rust oracle binary `tools/rust-oracle/target/debug/rsf-rust-oracle`.

3. **Complete Repository Test Suite:**
   ```bash
   .venv/bin/python -m unittest discover -s tests -v
   ```
   *Result:* Ran 418 tests in 24.147s, `OK` (exit code 0).

4. **Wheel & Distribution Isolation Test:**
   ```bash
   .venv/bin/python tests/check_distribution.py --python "$PWD/.venv/bin/python" --wheelhouse /tmp/rsf4-wheelhouse
   ```
   *Result:* Clean venv install, stdlib core isolation, and public tests: `DISTRIBUTION_CHECK_PASS` (exit code 0).

5. **JSON Schema Conformance:**
   ```bash
   for s in scripts/check_*_schema.py scripts/check_contract_schemas.py; do .venv/bin/python "$s"; done
   ```
   *Result:* All 10 schema checkers passed (including `check_compilation_schema.py`: `COMPILATION_SCHEMA_PASS schemas=2 valid=3 invalid=6`).

6. **End-to-End Workbench Browser Automation:**
   ```bash
   NODE_PATH="/home/ra/.npm/_npx/51691537fc71f2b0/node_modules" node ... tests/browser/rsf23-mcp.js
   ```
   *Result:* All 10 journeys passed (create project, import pair, declare target topology, stage PNG, assign, blocked plan before review, review approval, ready plan, compile & register candidate, and candidate comparison).
