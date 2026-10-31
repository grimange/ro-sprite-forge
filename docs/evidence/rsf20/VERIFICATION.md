# RSF-20 Verification Evidence Packet

## Task Summary
- **Ticket**: `RSF-20` (ID: `okckipkcfdqspilmisaewm5y`)
- **Title**: [M4] Spritesheet extraction and rectangle validation
- **Milestone**: M4 (Staging and Preview vertical slice)
- **Primary Implementer**: AGY (Codex Senior Graphics Pipeline / Spritesheet Extraction Specialist)
- **Independent Reviewer**: `forge-qa-reviewer`

---

## Acceptance Criteria Checklist & Evidence Mapping

### Criterion 1: Operator specifies cell rectangles/order and maps resulting images explicitly; no automatic pose identification
- **Evidence**:
  - `src/ro_sprite_forge/core/extraction.py`: `validate_rectangle_spec` and `expand_grid_spec` require explicit operator specification of rectangle bounds $[x, y, x + w, y + h)$ and unique rectangle IDs. `expand_grid_spec` accepts explicit row/column configuration or sparse cell selections. No automated edge detection, color thresholding, pose classification, or visual guessing is performed.
  - `src/ro_sprite_forge/static/workbench.js`: Dedicated UI controls for manual rectangle input and grid parameter configuration.
  - Verification: `tests/test_extraction.py` (`test_01_valid_rectangle_within_bounds`, `test_01_uniform_grid_expansion`, `test_04_grid_with_explicit_cells`, `test_01_extract_spritesheet_via_upload`).

### Criterion 2: Reject out-of-bounds/invalid crops, dimensions and source-hash mismatch with precise errors
- **Evidence**:
  - `src/ro_sprite_forge/core/extraction.py`:
    - Rejects negative coordinates with `INVALID_RECTANGLE_COORDINATES`.
    - Rejects non-positive dimensions with `INVALID_RECTANGLE_DIMENSIONS`.
    - Rejects coordinates exceeding spritesheet bounds with `RECTANGLE_OUT_OF_BOUNDS`.
    - Rejects grid dimensions exceeding sheet bounds with `GRID_OUT_OF_BOUNDS`.
    - Rejects duplicate IDs with `DUPLICATE_RECTANGLE_ID`.
    - Rejects duplicate or non-contiguous ordinals with `DUPLICATE_RECTANGLE_ORDINAL` and `RECTANGLE_ORDINAL_GAP`.
    - Rejects source hash mismatch with `SOURCE_HASH_MISMATCH`.
    - Atomic validation guarantees that if any crop in a batch is invalid, the entire operation is aborted with zero mutations.
  - Verification: `tests/test_extraction.py` (`test_05_negative_coordinate_rejected`, `test_06_zero_or_negative_dimensions_rejected`, `test_07_out_of_bounds_crop_rejected`, `test_03_grid_out_of_bounds_rejected`, `test_03_duplicate_rectangle_id_rejected`, `test_04_duplicate_ordinal_rejected`, `test_05_ordinal_gap_rejected`, `test_06_expected_sheet_sha256_mismatch_rejected`, `test_07_atomicity_any_out_of_bounds_aborts_all`, `test_02_http_extract_out_of_bounds_rejected`).

### Criterion 3: Store original sheet hash, rectangles/settings and extracted hashes so repeated extraction is identical
- **Evidence**:
  - Four distinct orthogonal cryptographic digests are tracked:
    1. `source_sha256`: original spritesheet PNG digest.
    2. `recipe_sha256`: canonical extraction recipe hash covering source hash, rectangle coordinates $[x, y, w, h]$, ID, and ordinal.
    3. `extracted_sha256`: deterministic PNG digest of extracted crop bytes (enabling content-addressed blob deduplication).
    4. `collection_sha256`: canonical digest sealing the ordered array of extracted hashes.
  - Repeated extraction on unchanged sheet bytes and rectangle parameters produces bit-for-bit identical manifests, collection digests, and recipe digests.
  - Verification: `tests/test_extraction.py` (`test_01_extract_spritesheet_determinism`, `test_02_content_addressed_deduplication_preserves_distinct_recipes`, `test_03_repeated_extraction_is_idempotent`).

### Criterion 4: Sheet candidates use the same staging, preview and exact requirement assignment path as PNG sequences
- **Evidence**:
  - Extracted subregions are staged as content-addressed blobs in `blobs/{sha256}`.
  - Sources catalog entry (`source_catalog`) exposes extracted frames with:
    - `origin = "AUTHORED"`
    - `kind = "IMAGE"`
    - `availability = "AVAILABLE"`
    - `validation = "VALID"`
    - Extraction metadata: `extraction_id`, `recipe_sha256`, `source_sheet_sha256`, `rect_id`, `crop_rect`.
  - Manifest contains `extractions` array governed by sealed schema `rsf.spritesheet-extraction/v1`.
  - Staging does NOT assign frames (`manifest["ledger"]["assignments"]` remains untouched) and does NOT approve frames (`manifest["review_events"]` remains untouched).
  - Staged frames appear in operator workbench dropdown (`#art-source`) for direct operator assignment and visual review.
  - Verification: `tests/test_extraction.py` (`test_01_extract_spritesheet_via_upload`, `test_02_extract_spritesheet_from_existing_staged_blob`, `test_01_http_extract_spritesheet_endpoint`), browser test `tests/browser/rsf20-mcp.js`.

---

## Test Execution Results & Preserved Logs

1. **Extraction Unit & Integration Suite**:
   - Command: `.venv/bin/python -m unittest tests/test_extraction.py -v`
   - Log: `docs/evidence/rsf20/extraction-tests.log`
   - Result: 26 / 26 tests passed (100% pass rate).

2. **Full Public Test Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`
   - Log: `docs/evidence/rsf20/public-tests.log`
   - Result: 373 / 373 tests passed.

3. **Audited Private Reference Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v`
   - Log: `docs/evidence/rsf20/private-tests.log`
   - Result: 36 / 36 tests passed.

4. **Schema Conformance Suite**:
   - Commands: `check_contract_schemas.py`, `check_extraction_schema.py`, `check_ingestion_schema.py`
   - Log: `docs/evidence/rsf20/schema-tests.log`
   - Result: All schemas valid; valid instances passed, invalid instances rejected.

5. **Isolated Wheel Distribution Suite**:
   - Command: `.venv/bin/python tests/check_distribution.py --python $(pwd)/.venv/bin/python --wheelhouse /tmp/rsf4-wheelhouse`
   - Log: `docs/evidence/rsf20/distribution.log`
   - Result: `DISTRIBUTION_CHECK_PASS`. Pure stdlib runtime, zero external runtime dependencies.
