# Independent QA Review Report: RSF-19

**Task**: RSF-19: `[M4] Deterministic PNG-sequence ingestion and staging`  
**Ticket ID**: `RSF-19` (`q9eh2soodxcc0qucu0pkoiy4`)  
**Milestone**: Milestone 4 (External Ingestion & Walk Vertical Slice)  
**Role**: Independent Read-Only QA Reviewer (`forge-qa-reviewer`)  
**Verdict**: **`QA_PASS`**

---

## 1. Acceptance Criteria Review

| Acceptance Criterion | Verification Status | Objective Evidence |
|---|---|---|
| **AC 1: Import ordered PNG sequences without inferred choreography, retain raw source hash plus staged pixel/asset identities and explicit source order** | **PASS** | Evaluated `validate_sequence` and `stage-sequence` mutation in `workbench.py`. Frames are keyed by explicit $0 \dots N-1$ ordinals. Canonical sequence hash is deterministically calculated as $\text{digest}(\text{canonical\_bytes}([\text{frame}[\text{sha256}] \dots]))$. Reordering frames changes sequence digest while leaving individual blob hashes unchanged (`test_20_sequence_reordering_changes_sequence_sha256`). Zero inferred choreography, extrapolation, or mirror guesswork. |
| **AC 2: Validate dimensions, decode budget, transparency expectations, hashes and invalid frame order with exact source/requirement error IDs** | **PASS** | `validate_png` and `validate_sequence` strictly enforce: `INVALID_PNG_SIGNATURE` for non-PNG bytes, `DIMENSION_EXCEEDED` for $>4096$, `DECODE_BUDGET_EXCEEDED` / `DECOMPRESSION_BOMB` for $>16\text{ MP}$, `CORRUPTED_PNG_DATA` for truncated/broken chunks, `PAYLOAD_TOO_LARGE` for $>32\text{ MiB}$, `SOURCE_HASH_MISMATCH` for hash divergence, `DUPLICATE_FRAME_ORDINAL` for repeated ordinals, `FRAME_ORDINAL_GAP` for gaps, `EMPTY_SEQUENCE` / `SEQUENCE_TOO_LARGE` for count bounds. Transparency is classified into `OPAQUE`, `PARTIALLY_TRANSPARENT`, and `FULLY_TRANSPARENT` across RGBA, LA, P, RGB, and L modes (`test_01`–`test_24`). |
| **AC 3: Same sources/settings and pinned decoder/color policy reproduce identical staged hashes; original files are immutable** | **PASS** | Staging writes content-addressed files under `blobs/{sha256}`. Repeated uploads or identical frames across ordinals are stored once and remain byte-identical (`test_25_duplicate_image_content_in_sequence`, `test_26_immutability_and_idempotency`). Re-staging reproduces identical canonical sequence manifests. Transaction atomicity confirmed in `test_27_transaction_atomicity_on_failure`: a validation failure in any frame leaves project revision and files untouched. |
| **AC 4: Expose imported candidates to the existing assignment/preview API and local import tray without automatic assignment/approval** | **PASS** | Ingested candidates are added to `manifest["sources"]` with `origin = "AUTHORED"`, `kind = "IMAGE"`, `availability = "AVAILABLE"`, `validation = "VALID"`, and populated in `source_catalog`. Candidates appear in workbench UI source dropdown (`#art-source`) with live thumbnail and metadata facts. `manifest["ledger"]["assignments"]` and `manifest["review_events"]` remain strictly empty upon ingestion (`test_28_no_auto_assignment_and_no_auto_approval` and end-to-end browser journey `tests/browser/rsf19-mcp.js`). Human assignment and visual approval remain separate, explicit actions. |

---

## 2. Code and File Inspection

The following changed and new files were inspected in detail:
- `src/ro_sprite_forge/core/ingestion.py`: Clean, pure core implementation with bounded constants (`MAX_DIMENSION = 4096`, `MAX_PIXELS = 16 * 1024 * 1024`, `MAX_SEQUENCE_FRAMES = 1024`), typed error codes, dual-pass Pillow verification + transparency analysis, and deterministic sequence ordering.
- `src/ro_sprite_forge/schemas/project-v1.json`: Schema updated with optional `sequences` array (`rsf.sequence/v1`) and technical metadata fields on source records (`width`, `height`, `mode`, `transparency_kind`, `has_transparency`, `sequence_id`, `ordinal`).
- `src/ro_sprite_forge/service/workbench.py`: Integrated `stage-sequence` and `stage-png` operations, catalog population for authored image blobs, and immutable content-addressed blob storage.
- `src/ro_sprite_forge/service/server.py`: Exposed `POST /api/projects/{id}/stage-sequence`, `POST /api/projects/{id}/stage-png`, and `GET /api/projects/{id}/sequences` routes with CSRF verification and protected project sequence updates.
- `src/ro_sprite_forge/static/index.html`: Added Sequence Import and Single PNG Import accordion controls with order adjustment table, natural sort, and clear operator messaging.
- `src/ro_sprite_forge/static/workbench.js`: Implemented sequence file selection, client-side base64 encoding with payload limits, interactive reordering table, and non-automatic assignment integration.
- `tests/test_ingestion.py`: 29 comprehensive tests covering all 28 synthetic scenarios, immutability, idempotency, atomicity, no auto-assignment, no auto-approval, and HTTP API endpoints.
- `tests/browser/rsf19-mcp.js`: Full 6-journey browser workflow testing sequence import, source tray display, manual assignment, save/reload persistence, and zero auto-approval.
- `scripts/check_ingestion_schema.py`: Conformance script validating 3 valid instances and 6 negative/invalid boundary cases against `project-v1.json`.
- `docs/architecture/RSF19_INGESTION.md`: Technical architecture specification documenting limits, hash calculations, and invariants.
- `docs/evidence/rsf19/VERIFICATION.md`: Verification evidence packet and log paths.

---

## 3. Independent Verification Execution Results

All commands were independently executed in read-only mode with byte-code generation disabled:

1. **Ingestion Unit & Scenario Tests**:
   - **Command**: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_ingestion.py`
   - **Exit Code**: `0`
   - **Result**: `Ran 29 tests in 0.629s — OK`

2. **Full Public Test Discovery Suite**:
   - **Command**: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_*.py"`
   - **Exit Code**: `0`
   - **Result**: `Ran 347 tests in 18.541s — OK`

3. **Private Fixtures & Round-Trip Tests**:
   - **Command**: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p "test_*.py"`
   - **Exit Code**: `0`
   - **Result**: `Ran 36 tests in 12.752s — OK`

4. **Schema Conformance Suite**:
   - **Command**: `for s in scripts/check_*schema*.py; do echo "=== $s ==="; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$s"; done`
   - **Exit Codes**:
     - `check_animation_schema.py`: Exit `0` (`ANIMATION_SCHEMA_PASS`)
     - `check_comparison_schema.py`: Exit `0` (`COMPARISON_SCHEMA_PASS`)
     - `check_contract_schemas.py`: Exit `0` (`JSON_SCHEMA_PASS`)
     - `check_coverage_schema.py`: Exit `0` (`COVERAGE_SCHEMA_PASS`)
     - `check_ingestion_schema.py`: Exit `0` (`INGESTION_SCHEMA_PASS`)
     - `check_ledger_schema.py`: Exit `0` (`LEDGER_SCHEMA_PASS`)
     - `check_review_schema.py`: Exit `0` (`REVIEW_SCHEMA_PASS`)

5. **Clean Isolated Wheel Distribution Verification**:
   - **Command**: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --python $(pwd)/.venv/bin/python --wheelhouse /tmp/rsf4-wheelhouse`
   - **Exit Code**: `0`
   - **Result**: Built sdist/wheel, installed in clean venv, verified stdlib-only core import, ran full test discovery (347 tests) -> `DISTRIBUTION_CHECK_PASS`.

---

## 4. Separation of Duties Confirmation

- **Read-Only Verification**: No files were created, edited, modified, staged, committed, reset, or deleted by this reviewer.
- **Tracker Status**: In accordance with the governance protocol, this reviewer does **not** update Kaneo PMP directly; the verdict and evidence are provided to the parent session / operator for synchronization.

---

## 5. Final QA Verdict

**`QA_PASS`**
