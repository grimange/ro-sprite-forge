# RSF-21 Verification Evidence Packet

## Task Summary
- **Ticket**: `RSF-21` (ID: `tnco42miae37x8m268gi6s4g`)
- **Title**: [M4] Explicit reversible image transformation recipes
- **Milestone**: M4 (Staging and Preview vertical slice)
- **Primary Implementer**: AGY (Codex Senior Graphics Pipeline / Transformation Architect)
- **Independent Reviewer**: `forge-qa-reviewer`

---

## Acceptance Criteria Checklist & Evidence Mapping

### Criterion 1: Every transform class is operator-requested and recorded with pinned algorithm/settings and source/staged hashes; originals remain recoverable
- **Evidence**:
  - `src/ro_sprite_forge/core/transformations.py`:
    - All operation parameters (`crop`, `flip`, `scale`, `offset`, `matte_key`, `color_mode`) are explicitly declared by the operator and validated against schema constraints (`validate_operation`).
    - Every recipe is validated under `rsf.image-recipe/v1` (`validate_recipe`), canonicalized, and cryptographically sealed (`recipe_sha256 = compute_recipe_sha256(clean_recipe)`).
    - Transformation execution generates a sealed `rsf.transformation-record/v1` binding `source_sha256`, `derived_sha256`, `recipe_sha256`, and technical metadata.
    - Original source blobs in `blobs/{source_sha256}` are strictly read-only and immutable; derived images are stored in distinct blobs (`blobs/{derived_sha256}`).
  - Verification: `tests/test_transformations.py` (`OperationValidationTests`, `test_01_apply_transform_stages_derived_candidate_without_auto_approval`, `test_01_transform_preview_and_apply_endpoints`), browser test `tests/browser/rsf21-mcp.js`.

### Criterion 2: Show before/after and require operator approval for applied transform classes; no hidden aesthetic repair or generated imagery
- **Evidence**:
  - `src/ro_sprite_forge/service/workbench.py`: `transform_preview()` calculates an in-memory transformation returning before/after base64 PNGs, dimension facts, transparency analysis, and loss disclosures without writing to disk or mutating the project.
  - `src/ro_sprite_forge/static/workbench.js`: Dedicated before/after side-by-side comparison UI (`#transform-before-img`, `#transform-after-img`, `#transform-facts`) for operator visual inspection before staging.
  - Zero automated background estimation, zero heuristic edge smoothing, and zero synthetic image generation.
  - Staging a derived image does not assign it or approve it (`project.ledger.assignments` and `project.review_events` remain untouched unless explicitly requested).
  - Verification: `tests/test_transformations.py` (`test_01_transform_preview_and_apply_endpoints`, `test_01_apply_transform_stages_derived_candidate_without_auto_approval`), browser test `tests/browser/rsf21-mcp.js`.

### Criterion 3: Raw bytes, staged pixels, preview RGBA and encoded output representation remain distinct; palette conversion reports information loss
- **Evidence**:
  - `src/ro_sprite_forge/core/transformations.py`: `execute_operation` separates raw bytes (input PNG), decoded pixel arrays (Pillow Image), color space modes (`RGBA` vs `P`), and deterministic output encoding.
  - Information loss is actively analyzed and reported in `loss_report`:
    - `CROPPED_DISCARDED_PIXELS` (crop)
    - `DOWNSCALED_DISCARDED_PIXELS` (downscaling)
    - `INTERPOLATED_RESAMPLING` (bilinear / bicubic scaling)
    - `CANVAS_CLIPPED_PIXELS` (offset clipping)
    - `ALPHA_CHANNEL_KEYED` (matte color replacement)
    - `PALETTE_INDICES_DISCARDED` (palette-to-RGBA conversion)
    - `COLOR_QUANTIZATION_LOSSY` (RGBA-to-palette conversion)
  - Verification: `tests/test_transformations.py` (`TransformationExecutionTests`: `test_01_crop_extracts_exact_pixels_and_discloses_loss`, `test_05_downscale_discloses_loss`, `test_06_interpolated_scaling_discloses_interpolation`, `test_08_matte_background_keying_replaces_color_with_alpha`, `test_09_palette_to_rgba_conversion_discloses_palette_indices_discarded`).

### Criterion 4: Identical source/recipe versions produce identical staged hashes; recipe edits invalidate only affected composition approval
- **Evidence**:
  - Strict determinism: applying the identical recipe to identical source bytes produces bit-for-bit identical output PNG bytes and identical `derived_sha256`.
  - Order sensitivity: operations execute in strict sequential order. `Crop -> Flip` produces different pixels and a different digest than `Flip -> Crop`.
  - Scoped invalidation: replacing an assigned layer source with a derived image alters the canonical composition digest (`basis_sha256`) of that layer occurrence only. RSF-18 review evaluator marks only that occurrence's review as `STALE` (`COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`), while reviews for other occurrences remain `APPROVED`.
  - Verification: `tests/test_transformations.py` (`test_10_order_sensitivity_crop_then_flip_vs_flip_then_crop`, `test_11_repeated_execution_is_strictly_idempotent`, `test_02_replacing_assigned_source_with_derived_invalidates_affected_approval_only`), browser test `tests/browser/rsf21-mcp.js` (Journey F).

---

## Test Execution Results & Preserved Logs

1. **Unit & Integration Suite (`tests/test_transformations.py`)**:
   - Command: `.venv/bin/python -m unittest tests/test_transformations.py -v`
   - Log: `docs/evidence/rsf21/transformation-tests.log`
   - Result: 22 / 22 tests passed (OK).

2. **Full Public Regression Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - Log: `docs/evidence/rsf21/public-tests.log`
   - Result: 395 / 395 tests passed in 20.865s (OK).

3. **Audited Private Reference Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v`
   - Log: `docs/evidence/rsf21/private-tests.log`
   - Result: 36 / 36 tests passed (OK).

4. **Schema Conformance Suite**:
   - Commands: `scripts/check_*.py`
   - Log: `docs/evidence/rsf21/schema-tests.log`
   - Result: All schema validators passed (including `check_transformation_schema.py`: 1 schema, 4 valid instances, 8 invalid instances rejected).

5. **Isolated Wheel Distribution Suite**:
   - Command: `.venv/bin/python tests/check_distribution.py --python .venv/bin/python --wheelhouse /tmp/rsf4-wheelhouse`
   - Log: `docs/evidence/rsf21/distribution.log`
   - Result: Wheel built without dependencies; installed into isolated virtual environment; 395 tests passed (OK). `DISTRIBUTION_CHECK_PASS`.

6. **End-to-End Browser Journeys (Playwright & Google Chrome)**:
   - Script: `tests/browser/rsf21-mcp.js`
   - Journeys verified:
     - Journey A: Create new project in Workbench UI.
     - Journey B: Define target with 4 Walk frames and explicit layer topology (`body`, 32 layer requirements).
     - Journey C: Stage PNG source image into project.
     - Journey D: Crop & horizontal flip recipe with before/after preview, facts disclosure, and staging.
     - Journey E: Matte background keying with color tolerance and loss reporting (`ALPHA_CHANNEL_KEYED`).
     - Journey F: Assignment & scoped review invalidation (occurrence 0 becomes `STALE`, occurrence 1 remains `APPROVED`).
     - Journey G: Error handling (out-of-bounds crop rejected with `CROP_OUT_OF_BOUNDS`).
   - Result: `ALL RSF-21 BROWSER JOURNEYS COMPLETED SUCCESSFULLY`.
