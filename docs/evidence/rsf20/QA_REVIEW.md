# Independent QA Review Report: RSF-20

- **Task Ticket**: `RSF-20` (Task ID: `okckipkcfdqspilmisaewm5y`)
- **Task Title**: `[M4] Spritesheet extraction and rectangle validation`
- **Milestone**: M4 (Staging and Preview vertical slice)
- **Review Mode**: Strictly Read-Only Independent Review
- **Verdict**: **`QA_PASS`**

---

## 1. Executive Summary

Task RSF-20 introduces deterministic PNG spritesheet extraction and rectangle validation into RO Sprite Forge. The implementation strictly adheres to the product contract and architecture invariants of Plan v1.1 and `AGENTS.md`:
1. It mandates explicit operator-defined coordinates, dimensions, and ordering, with zero automatic pose classification, feature grouping, or visual guessing.
2. It enforces precise integer coordinate and dimension bounds validation with typed errors and strict atomicity (batch fails completely if any crop is out of bounds or invalid).
3. It preserves four orthogonal cryptographic digests (`source_sha256`, `recipe_sha256`, `extracted_sha256`, `collection_sha256`), ensuring 100% idempotent and deterministic repeat extractions.
4. Extracted frames enter the standard content-addressed project blob store and source catalog tray with `origin = 'AUTHORED'`, `kind = 'IMAGE'`, `availability = 'AVAILABLE'`, `validation = 'VALID'`, without automatic assignment to target requirements and without silent visual approval.

---

## 2. Acceptance Criteria Assessment

| Criterion | Requirement | Finding | Status |
| :--- | :--- | :--- | :---: |
| **AC-1** | Operator specifies cell rectangles/order and maps resulting images explicitly; no automatic pose identification. | `validate_rectangle_spec` and `expand_grid_spec` require explicit bounding box coordinates $[x, y, x+w, y+h)$ and unique IDs. Ordinals follow explicit enumeration or row-major sequence. Workbench UI provides manual rectangle table and grid parameters. Staged frames do NOT auto-assign (`manifest["ledger"]["assignments"]` untouched) or auto-approve (`manifest["review_events"]` untouched). | **PASS** |
| **AC-2** | Reject out-of-bounds/invalid crops, dimensions and source-hash mismatch with precise errors. | Negative coordinates (`INVALID_RECTANGLE_COORDINATES`), non-positive dimensions (`INVALID_RECTANGLE_DIMENSIONS`), sheet boundary overflow (`RECTANGLE_OUT_OF_BOUNDS`), grid overflow (`GRID_OUT_OF_BOUNDS`), duplicate IDs (`DUPLICATE_RECTANGLE_ID`), non-contiguous ordinals (`DUPLICATE_RECTANGLE_ORDINAL`, `RECTANGLE_ORDINAL_GAP`), and mismatched source hashes (`SOURCE_HASH_MISMATCH`) are strictly rejected. Atomicity ensures zero writes on any batch failure. | **PASS** |
| **AC-3** | Store original sheet hash, rectangles/settings and extracted hashes so repeated extraction is identical. | Manifest schema `rsf.spritesheet-extraction/v1` records source hash, collection hash, and item-level rectangle recipes and extracted hashes. Repeat execution on unchanged inputs produces identical canonical hashes. Content-addressed blob deduplication correctly preserves distinct recipe identities. | **PASS** |
| **AC-4** | Sheet candidates use the same staging, preview and exact requirement assignment path as PNG sequences. | Crops are staged into `blobs/{sha256}`. Manifest `sources` records extraction provenance (`extraction_id`, `recipe_sha256`, `source_sheet_sha256`, `rect_id`, `crop_rect`). Crops appear in workbench source tray dropdown (`#art-source`) for operator assignment, batch mapping, and preview. Direct tampering of `extractions` via generic project PUT is rejected. | **PASS** |

---

## 3. Independent Verification & Test Execution Evidence

All verification commands were executed independently under `PYTHONDONTWRITEBYTECODE=1`:

1. **Extraction Test Suite**:
   - Command: `.venv/bin/python -m unittest tests/test_extraction.py`
   - Exit code: `0`
   - Result: 26 tests run, 26 passed (0 failures, 0 errors).
   - Scope covered: Coordinate validation, zero/negative bounds, out-of-bounds rejection, ID/ordinal uniqueness, grid expansion, explicit cells, determinism, deduplication, atomicity, workbench mutation integration, HTTP API routes, and anti-tamper guards.

2. **Extraction Schema Conformance**:
   - Command: `.venv/bin/python scripts/check_extraction_schema.py`
   - Exit code: `0`
   - Result: `EXTRACTION_SCHEMA_PASS schemas=1 valid=3 invalid=8`

3. **Core Schema Checks**:
   - Command: `.venv/bin/python scripts/check_contract_schemas.py`
   - Exit code: `0`
   - Result: `JSON_SCHEMA_PASS jsonschema=4.19.2 schemas=3 valid=13 invalid=55`
   - Command: `.venv/bin/python scripts/check_ingestion_schema.py`
   - Exit code: `0`
   - Result: `INGESTION_SCHEMA_PASS schemas=1 valid=3 invalid=6`

4. **Full Regression Test Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - Exit code: `0`
   - Result: 373 tests run, 373 passed (0 regressions).

5. **Private Reference Fixture Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'`
   - Exit code: `0`
   - Result: 36 tests run, 36 passed (Novice body/head, Orc Skeleton inventory & byte preservation intact).

6. **Isolated Wheel Distribution Verification**:
   - Command: `.venv/bin/python tests/check_distribution.py --python $(pwd)/.venv/bin/python --wheelhouse /tmp/rsf4-wheelhouse`
   - Exit code: `0`
   - Result: `DISTRIBUTION_CHECK_PASS` (clean isolated venv installation, stdlib core isolation verified without Pillow runtime dependency in core).

7. **Code & Artifact Digest Audit**:
   Verified all 10 implementation paths against `docs/evidence/rsf20/implementation-manifest.json`:
   - `src/ro_sprite_forge/core/extraction.py`: `015b6bc3c741055aaa4cd09bce03f46625403cf105e6756cd4a7d7c7092a1e08` (MATCH)
   - `src/ro_sprite_forge/schemas/project-v1.json`: `80e6804e6a767817a3c5f4aa34b810cf4cbb4f711764d5b91fd5bbd2b602e371` (MATCH)
   - `src/ro_sprite_forge/service/workbench.py`: `6e48ae8e6250f11fe69fc49849ebba3aea9d4f4df6c28454d24754eafe5427ac` (MATCH)
   - `src/ro_sprite_forge/service/server.py`: `4e9cda7da56b028a5b79b381c8bcc4ad9f8a37bf863c504590a1ba60fb27138d` (MATCH)
   - `src/ro_sprite_forge/static/index.html`: `a503c103e0c72b74a8dd5e8fed0baca0b271ddf00eda40937d3312565a9aa22c` (MATCH)
   - `src/ro_sprite_forge/static/workbench.js`: `d76d1e672ae70ad867ecb0b669e86d8051d6c1e37d1f0ca476d008b7685fe9b5` (MATCH)
   - `scripts/check_extraction_schema.py`: `719a5dc2ae3aeaeeb6395ccf01970143a6e3e7aca52f6fdce3c0db2a6bce2069` (MATCH)
   - `tests/test_extraction.py`: `d0f8d20ee2b1104237967f88a6f5914b8096e140527c01b4a13da764431ea236` (MATCH)
   - `tests/browser/rsf20-mcp.js`: `7140529a7fcea972cc422ddbd3ba5d07be905ae4a748ccd939fad9f68e7519f4` (MATCH)
   - `docs/architecture/RSF20_EXTRACTION.md`: `8c7c8661201f9e08c1f1548b77a882b7186899a31c409c9afc1c19f04133d81a` (MATCH)

---

## 4. Architectural Invariant Review

1. **Separation of Authorities**: Observed resources, target requirements, staging candidates, and the assignment ledger remain strictly decoupled. Staging candidate crops does not modify target requirements or create unreviewed ledger assignments.
2. **Determinism**: Canonical byte encoding and SHA-256 digests ensure stable IDs and repeatable collections.
3. **Immutability & Anti-tampering**: `PUT /api/projects/{id}` explicitly rejects modifications to `extractions`, requiring the validated `extract-spritesheet` workbench mutation route.
4. **No Visual Autonomy**: No heuristic boundary finding, auto-cropping, or pose identification is performed.

---

## 5. Conclusion & Verdict

**Verdict**: **`QA_PASS`**

The implementation of RSF-20 is complete, correct, fully tested, and ready for transition to Accepted in Kaneo PMP.
