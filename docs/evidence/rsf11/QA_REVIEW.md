# Independent QA Review Report: RSF-11 [M2]

**Reviewer Identity:** Independent Read-Only QA Reviewer (`forge-qa-reviewer`)  
**Target Task:** RSF-11 — `[M2] Order-preserving multilayer preview compositor`  
**Internal Task ID:** `gspmf9so83jbn57y0anhz522`  
**Project ID:** `oq6fp33cmdnwl5h0v48zcr3u` (`RO Sprite Forge`)  
**Active Baseline / Dependencies:** RSF-10 Accepted (`uzuir12040jroddz4idk8ahi`); RSF-9 Accepted (`bbiahdelxdqg6o5aupyfj699`); M0 Verified retained.  
**Plan Reference:** `docs/architecture/RO_SPRITE_FORGE_COMPREHENSIVE_IMPLEMENTATION_PLAN_v1.1.md` §§2.3, 4.3–4.4, 6/M2, 7 (SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e` verified)

---

## 1. Verified Files, Hashes & Provenance

Implementation Manifest SHA-256: `f5bc4b408103c8cfa2dfa8c546a362f68285586fe086c2f34ee6900fec125f4a`  
Implementation Source Archive: `docs/evidence/rsf11/implementation-source.tar.gz` verified to contain only delivery files. Zero proprietary game art, ACT, SPR, or GRF files are bundled in the repository or wheels.

| File Path | SHA-256 Digest | Status |
|---|---|---|
| `docs/architecture/RSF11_PREVIEW.md` | `9fb502e5c891e92f6792ad306b14e256cdbb20573bc78a4a1ad7f16fe22804d9` | MATCH |
| `src/ro_sprite_forge/cli.py` | `799e531bf9f1e5e221944315b5b2afbf8d108b6b12df09809db2ea4d525f8bc9` | MATCH |
| `src/ro_sprite_forge/formats/preview.py` | `7bbc90c767a2412843524b14b8c992935d47c9051bca9ccc1efb252aedbf126f` | MATCH |
| `src/ro_sprite_forge/schemas/preview-result-v1.json` | `ecc47dfcdd95e4ce8cc833c7c4df1e385799cc055bf9e601704ee53d40fddf31` | MATCH |
| `tests/private_fixture_hooks/test_preview_fixtures.py` | `cfc54eb514854f9a9382bea387b541ae5e4cf7b539148e6a01c44574b61d84fe` | MATCH |
| `tests/test_preview.py` | `9b4f0fdd49ed80ba43c53740612dd316ed4beb2d987eeb90e67134d4e8bbc497` | MATCH |
| `docs/evidence/rsf11/examples.json` | `5e89a572a10689b78297b77ceb3ccab39039a067ff0c8227e7f60742f1cf54eb` | MATCH |

---

## 2. Independent Test Execution & Exit Statuses

All verification commands were executed independently with `PYTHONDONTWRITEBYTECODE=1`:

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest tests/test_preview.py -v`
   - **Result:** Ran 20 synthetic pixel scenario tests in 0.192s — **OK (exit code 0)**
2. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p "test_*.py"`
   - **Result:** Ran 192 public tests in 2.651s — **OK (exit code 0)**
3. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests:tests/private_fixture_hooks .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p "test_*.py" -v`
   - **Result:** Ran 22 private fixture tests in 4.308s — **OK (exit code 0, 0 skips)**
4. `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14`
   - **Result:** Package build, wheel install, 192 installed unit tests in isolated venv — `DISTRIBUTION_CHECK_PASS` — **OK (exit code 0)**
5. `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/evidence/rsf11/reproduce_examples.py`
   - **Result:** Regenerated 8 canonical examples matching `examples.json` — **OK (exit code 0)**
6. Independent JSON Schema Draft 2020-12 validation:
   - **Result:** All 8 canonical example reports in `examples.json` passed Draft 2020-12 validation.
   - Negative cases (invalid fidelity enum, missing required fields, negative dimensions) properly rejected.

---

## 3. Evaluation of Acceptance Criteria

### Criterion 1: Visible layer order and moving multilayer placement, tint/alpha/scale/rotation/mirroring semantics
- **Status:** **PASS**
- **Findings:**
  - Sequential layer composition in exact ACT layer order verified: top layers occlude bottom layers (`test_02_two_overlapping_layers_order`, `test_03_reversed_layer_order`, `test_13_multilayer_occlusion_five_layers`).
  - Integer-center placement convention $\text{shift}_x = - \lfloor \frac{\text{width} - 1}{2} \rfloor$, $\text{shift}_y = - \lfloor \frac{\text{height} - 1}{2} \rfloor$ accurately reproduces Ragnarok and pinned Korangar native geometry (`vector2_i32_to_f32(-((frame_part.size - Vector2::new(1, 1)) / 2))`).
  - Horizontal mirroring (`mirror == 1` and negative scaling), bilinear non-uniform scaling (`scale_x`, `scale_y`), clockwise screen-space rotation, 32-bit color tinting, and alpha modulation are faithfully implemented and independently verified in pixel-level tests (`test_08` through `test_12`).
  - Unsupported semantics (such as attached parts with mismatched action counts or absent anchors) are explicitly recorded in `unsupported_semantics` without silent corruption.

### Criterion 2: Preview imported and assigned actions for single-layer Novice and multipart Orc death/other actions without flattening
- **Status:** **PASS**
- **Findings:**
  - Audited Novice body + head actor preview verified for Idle (slot 0, frame 0) and Walk (slot 8, frame 0) with parent-child anchor offset shifting `(ba["x"] - ha["x"], ba["y"] - ha["y"])` (`test_novice_body_head_preview_idle_walk`).
  - Audited Orc Skeleton Attack (slot 16, frame 0) and Death (slot 32, frame 21) verified (`test_orc_skeleton_multilayer_attack`, `test_orc_skeleton_12_layer_death_frame`).
  - In Orc Skeleton Action 32 Frame 21, all 12 animated visible layers are composited in exact ACT order with individual sprite IDs `[44, 45, 46, 47, 46, 47, 47, 42, 40, 41, 43, 47]`, mirroring on layer 10, and individual rotation angles `[4.0, 70.0, 111.0, 330.0, 211.0, 339.0, 348.0, 12.0, 234.0, 293.0, 260.0, 266.0]`. No moving layers are flattened away or discarded.
  - Native RSF-6 parity confirmed in `test_native_rsf6_structural_parity`: preview layer indices, mirror flags, and $(x, y)$ offsets match Korangar native prepared frame parts bit-for-bit.

### Criterion 3: Raw indexed/palette and source bytes remain separate from preview RGBA; preview never silently converts export representation
- **Status:** **PASS**
- **Findings:**
  - Sprite pool separation is strictly preserved: `indexed_images` (pool 0) and `rgba_images` (pool 1) remain untouched.
  - Calling `composite_frame()` on an SPR document decodes indexed images to RGBA strictly for the temporary display canvas buffer. The underlying `SprDocument.indexed_images`, `SprDocument.palette`, and raw pixel bytes remain byte-exact and unmodified (`test_orc_skeleton_12_layer_death_frame` and independent mutation assertions).
  - Unchanged assets maintain byte-exact round-trip preservation.

### Criterion 4: Renderer behavior identity is versioned and reports fidelity VERIFIED/PARTIAL/UNVERIFIED with unsupported semantics
- **Status:** **PASS**
- **Findings:**
  - Draft 2020-12 schema `rsf.preview-result/v1` defines `renderer_version: "1.0.0"` and `fidelity: ["VERIFIED", "PARTIAL", "UNVERIFIED", "INVALID"]`.
  - Every composite frame report includes `schema`, `renderer_version`, `fidelity`, `dimensions`, `origin`, `bounds`, `layers_rendered`, `layers`, `unsupported_semantics`, `errors`, and `png_sha256`.
  - Negative handling verified: corrupt/missing sprite references raise `CodecError` in strict mode and yield `fidelity: "INVALID"` with descriptive errors in non-strict mode (`test_17_out_of_bounds_sprite_handling`).
  - CLI `ro-sprite-forge preview` supports `--act`, `--spr`, `--action`, `--frame`, `--head-act`, `--head-spr`, `--origin`, `--canvas-size`, `--auto-fit`, `--output`, `--json`, and `--stdout-json`, returning atomic output and structured error reporting on stderr.

---

## 4. Invariant and Boundary Checks

1. **Human Visual Authority:** The compositor only performs mathematical 2D rendering and layer positioning; it performs zero aesthetic scoring, automated frame healing, or unverified visual sign-off.
2. **Determinism:** Bitwise identical PNG bytes and SHA-256 digests across repeated renders (`test_18_output_determinism`).
3. **Draft 2020-12 Compliance:** Schema validation strictly rejects malformed reports and unknown fidelity statuses.
4. **Clean Distribution:** Distribution check passed under Python 3.14 wheel build and execution.

---

## 5. Scope & Milestone Gate Declaration

- **Task Scope:** RSF-11 (M2-01) — Order-preserving multilayer preview compositor.
- **Milestone Gate Impact:**
  - M0 Gates (`M0-S`, `M0-I`, `M0-N`): PASS retained.
  - M1 Contracts (RSF-7, RSF-8, RSF-9, RSF-10): Accepted retained.
  - M2 Preview Core: **PASS** (RSF-11 requirements verified).
  - Note: Operator visual approval and native runtime verification for new candidate artwork remain separate gates for M3–M5.

---

## 6. QA Verdict

**Verdict:** `QA_PASS`

All 4 acceptance criteria for RSF-11 are fully met with rigorous synthetic and audited private fixture test coverage, strict format preservation, deterministic binary output, and complete Draft 2020-12 schema compliance.
