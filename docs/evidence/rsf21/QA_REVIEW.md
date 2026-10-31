# Independent QA Review Report: RSF-21 ([M4] Explicit reversible image transformation recipes)

**Task Ticket:** RSF-21 (Kaneo Task ID: `tnco42miae37x8m268gi6s4g`)  
**Reviewer:** `forge-qa-reviewer` (Independent Read-Only QA Session)  
**Verdict:** **`QA_PASS`**

---

## 1. Executive Summary & Verification Context

RSF-21 implements reversible, non-destructive image transformation recipes for staged candidates in Milestone M4.

As an independent, strictly read-only reviewer:
- No repository files, test code, or Kaneo PMP task records were modified.
- All file hashes in `docs/evidence/rsf21/implementation-manifest.json` were independently computed and verified bit-for-bit against current workspace files.
- All unit, integration, schema conformance, public regression, private reference, and isolated wheel distribution test suites were independently rerun and passed.
- All 4 acceptance criteria and architectural invariants were evaluated and confirmed satisfied.

---

## 2. Cryptographic Manifest Hash Verification

Every file in the manifest matches its SHA-256 digest:

| File Path | Manifest SHA-256 | Verified Local SHA-256 | Status |
|---|---|---|---|
| `src/ro_sprite_forge/core/transformations.py` | `cba06b238ae94d338e2aae22b98fa39b866d4e767f2de37697e3ec46d02932be` | `cba06b238ae94d338e2aae22b98fa39b866d4e767f2de37697e3ec46d02932be` | **MATCH** |
| `src/ro_sprite_forge/schemas/project-v1.json` | `a091f59824f728f91119827ef49eb5a4dcc896a468bc4f606ebcab711e0ded34` | `a091f59824f728f91119827ef49eb5a4dcc896a468bc4f606ebcab711e0ded34` | **MATCH** |
| `src/ro_sprite_forge/service/workbench.py` | `60603cc9cda7bbe1eb467819b8c7ec2070339a54ba4b89a2fd58043429f725d7` | `60603cc9cda7bbe1eb467819b8c7ec2070339a54ba4b89a2fd58043429f725d7` | **MATCH** |
| `src/ro_sprite_forge/service/server.py` | `6707f64a3bc483996734bf9e3cdd23d0ff99ae46577b15256da3ad46cdc91ac0` | `6707f64a3bc483996734bf9e3cdd23d0ff99ae46577b15256da3ad46cdc91ac0` | **MATCH** |
| `src/ro_sprite_forge/static/index.html` | `fd265878bb32218192ccb352e07172b21ee45f190d8614ee959b7d715b9dbd2d` | `fd265878bb32218192ccb352e07172b21ee45f190d8614ee959b7d715b9dbd2d` | **MATCH** |
| `src/ro_sprite_forge/static/workbench.js` | `9bbdb1bf7d6d9e39824cde3935239c2eb920626077a97e5a92f15d8337fdf85d` | `9bbdb1bf7d6d9e39824cde3935239c2eb920626077a97e5a92f15d8337fdf85d` | **MATCH** |
| `scripts/check_transformation_schema.py` | `bf0b0f0b4a2ac51d0ceb72db178a0862eea6a000ab02999d6fccbbee6c8f5e14` | `bf0b0f0b4a2ac51d0ceb72db178a0862eea6a000ab02999d6fccbbee6c8f5e14` | **MATCH** |
| `tests/test_transformations.py` | `b5a5e6d0fb2b8372bab768727e1a0d183c717c8838906bb9a4b8205a17472ba5` | `b5a5e6d0fb2b8372bab768727e1a0d183c717c8838906bb9a4b8205a17472ba5` | **MATCH** |
| `tests/browser/rsf21-mcp.js` | `8611e5eabd91c8fd82aacf15b3a5f82e9f82d028d93ceb8546c3d9ed23e88694` | `8611e5eabd91c8fd82aacf15b3a5f82e9f82d028d93ceb8546c3d9ed23e88694` | **MATCH** |
| `docs/architecture/RSF21_TRANSFORMATIONS.md` | `0b56154656545cdde8096615e70a0f2a2ce9e0e56aad5eefc1c9041b4cbc000d` | `0b56154656545cdde8096615e70a0f2a2ce9e0e56aad5eefc1c9041b4cbc000d` | **MATCH** |

---

## 3. Independent Test Execution & Gate Results

All commands were independently executed in Python 3.14 with `PYTHONDONTWRITEBYTECODE=1`:

1. **Focused Transformation Unit Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_transformations.py -v`
   - Result: **22 / 22 PASS** (1.217s, exit 0).
   - Validated: crop out-of-bounds rejection, zero-dimension rejection, flip directions, nearest-neighbor pixel blocks, loss reporting, matte keying, palette conversion, order sensitivity, idempotency, preview/apply HTTP endpoints, and scoped review invalidation.

2. **Schema Checker Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_transformation_schema.py`
   - Result: **TRANSFORMATION_SCHEMA_PASS** (schemas=1, valid=4, invalid=8 rejected, exit 0).
   - Full schema check across all 9 schema scripts: all **PASS** (14 schemas, 54 valid instances, 116 invalid instances rejected).

3. **Public Regression Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - Result: **395 / 395 PASS** (19.460s, exit 0). Zero failures, zero errors.

4. **Private Reference Fixture Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v`
   - Result: **36 / 36 PASS** (11.567s, exit 0). Audited Male Novice and Orc Skeleton inventory, byte-exact preservation, and multilayer preview fixtures verified intact.

5. **Wheel Distribution & Packaging Check**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --python "$PWD/.venv/bin/python" --wheelhouse /tmp/rsf4-wheelhouse`
   - Result: **DISTRIBUTION_CHECK_PASS** (exit 0).
   - Built sdist (`1c2fa0ff0a69...`) and wheel (`63af945ab8...`). Verified stdlib core zero-dependency import and execution, followed by running all 395 tests in isolated clean venv.

6. **Browser Journey Evaluation**:
   - Evaluated `tests/browser/rsf21-mcp.js` covering Journeys A–G. The implementation in `workbench.js` and `index.html` exposes all required elements (`#transform-source`, `#transform-recipe-id`, `#transform-steps-list`, `#preview-transform-btn`, `#apply-transform-btn`, `#transform-before-img`, `#transform-after-img`, `#transform-facts`, `#transform-status`), matching the documented end-to-end browser journeys and verified Playwright log output.

---

## 4. Acceptance Criteria Evaluation

### [x] Criterion 1: Every transform class is operator-requested and recorded with pinned algorithm/settings and source/staged hashes; originals remain recoverable
- **Evaluation: SATISFIED**
- Operations supported: `crop`, `flip`, `scale`, `offset`, `matte_key`, `color_mode`. All operations and arguments are strictly validated against discrete parameters in `validate_operation()`.
- Recipes are represented as versioned, serializable records conforming to `rsf.image-recipe/v1` and sealed with `compute_recipe_sha256()`.
- Execution produces an `rsf.transformation-record/v1` capturing `source_sha256`, `derived_sha256`, `recipe_sha256`, and technical metadata.
- Original source blobs remain untouched in immutable content-addressed storage `blobs/{source_sha256}`; derived images are staged into distinct blobs `blobs/{derived_sha256}`.

### [x] Criterion 2: Show before/after and require operator approval for applied transform classes; no hidden aesthetic repair or generated imagery
- **Evaluation: SATISFIED**
- `POST /api/projects/{id}/transform-preview` calculates in-memory preview without mutating state or persisting files, returning base64 images of both before and after, dimensions, transparency, and loss reports.
- Side-by-side preview UI in `#transform-preview-container` enables human visual comparison before applying.
- Zero AI generation, inpainting, edge synthesis, or aesthetic repair exists in `transformations.py` or anywhere in the codebase.
- Applying a transformation (`apply-transform`) stages the candidate as a source but does **not** auto-assign or auto-approve it.

### [x] Criterion 3: Raw bytes, staged pixels, preview RGBA and encoded output representation remain distinct; palette conversion reports information loss
- **Evaluation: SATISFIED**
- The pipeline separates raw bytes (input PNG blob), loaded pixel array (Pillow Image), color modes (`RGBA`, `RGB`, `P`, `L`, `LA`), and output byte serialization.
- Loss categories are explicitly detected and reported in `loss_report`:
  - `CROPPED_DISCARDED_PIXELS` (crop)
  - `DOWNSCALED_DISCARDED_PIXELS` (downscaling)
  - `INTERPOLATED_RESAMPLING` (bilinear / bicubic scaling)
  - `CANVAS_CLIPPED_PIXELS` (offset clipping)
  - `ALPHA_CHANNEL_KEYED` (matte color replacement)
  - `PALETTE_INDICES_DISCARDED` (palette-to-RGBA conversion)
  - `COLOR_QUANTIZATION_LOSSY` (RGBA-to-palette quantization)

### [x] Criterion 4: Identical source/recipe versions produce identical staged hashes; recipe edits invalidate only affected composition approval
- **Evaluation: SATISFIED**
- Determinism and idempotency verified: repeatedly running identical recipes on identical sources produces bit-for-bit identical output bytes and SHA-256 (`test_11_repeated_execution_is_strictly_idempotent`).
- Order sensitivity enforced: `crop -> flip` produces distinct pixels and distinct SHA-256 compared to `flip -> crop` (`test_10_order_sensitivity_crop_then_flip_vs_flip_then_crop`).
- Scoped review invalidation verified: replacing an assigned layer with a derived image changes that specific layer's composition digest (`basis_sha256`). The RSF-18 review evaluator marks only that layer occurrence as `STALE` (`COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`), while unaffected approved layers remain `APPROVED` (`test_02_replacing_assigned_source_with_derived_invalidates_affected_approval_only`).

---

## 5. Architectural & Workspace Constraints Verification

- **Zero dependencies in `pyproject.toml`:** Confirmed `dependencies = []` in `pyproject.toml`.
- **Vanilla frontend:** Confirmed plain HTML5, CSS, and vanilla DOM manipulation in `index.html` and `workbench.js` without external frameworks, CDNs, or bundlers.
- **Operator-controlled:** Human operator drives every transformation step, previews before/after, and explicitly stages candidates.
- **Read-only reviewer compliance:** No files created or edited; no Git branch or commit changes; no direct Kaneo write.

---

## 6. Final Verdict

**Verdict:** **`QA_PASS`**
