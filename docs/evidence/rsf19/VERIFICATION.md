# RSF-19 Verification Evidence Packet

## Task Overview
- **Task**: RSF-19 — [M4] Deterministic PNG-sequence ingestion and staging
- **Ticket ID**: `q9eh2soodxcc0qucu0pkoiy4`
- **Milestone**: Milestone 4 (External Ingestion and Walk vertical slice)
- **Implementer**: AGY (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)
- **Reviewer**: `forge-qa-reviewer`

---

## Acceptance Criteria Verification Summary

### Criterion 1: Import ordered PNG sequences without inferred choreography, retain raw source hash plus staged pixel/asset identities and explicit source order
- **Status**: **VERIFIED**
- **Evidence**:
  - `src/ro_sprite_forge/core/ingestion.py` implements `validate_sequence(sequence_id, name, frames)`.
  - Frames are strictly ordered by explicit ordinals $0, \dots, N-1$.
  - Canonical sequence digest is computed over the ordered list of individual frame SHA-256 hashes:
    $$\text{sequence\_sha256} = \text{digest}(\text{canonical\_bytes}([\text{frame}[\text{sha256}] \text{ for frame in sorted\_frames}]))$$
  - Reordering frames changes sequence digest while keeping individual source file hashes unchanged (`test_20_sequence_reordering_changes_sequence_sha256`).
  - No choreography, mirror inference, or frame extrapolation is performed.

### Criterion 2: Validate dimensions, decode budget, transparency expectations, hashes and invalid frame order with exact source/requirement error IDs
- **Status**: **VERIFIED**
- **Evidence**:
  - Tested across all 28 synthetic scenarios in `tests/test_ingestion.py` (`IngestionValidationTests`).
  - Strict error IDs raised:
    - `INVALID_PNG_SIGNATURE` for non-PNG magic header.
    - `DIMENSION_EXCEEDED` for dimensions $> 4096$.
    - `DECODE_BUDGET_EXCEEDED` / `DECOMPRESSION_BOMB` for $> 16\text{ MP}$ allocations.
    - `CORRUPTED_PNG_DATA` for truncated/corrupted chunk structures.
    - `PAYLOAD_TOO_LARGE` for files $> 32\text{ MiB}$.
    - `SOURCE_HASH_MISMATCH` for expected digest mismatch.
    - `DUPLICATE_FRAME_ORDINAL` for non-unique ordinals.
    - `FRAME_ORDINAL_GAP` for gaps in contiguous $0..N-1$ sequence.
    - `EMPTY_SEQUENCE` / `SEQUENCE_TOO_LARGE` for length boundaries.
  - Transparency is classified into `OPAQUE`, `PARTIALLY_TRANSPARENT`, and `FULLY_TRANSPARENT` across RGBA, LA, P, RGB, and L modes.

### Criterion 3: Same sources/settings and pinned decoder/color policy reproduce identical staged hashes; original files are immutable
- **Status**: **VERIFIED**
- **Evidence**:
  - `test_26_immutability_and_idempotency` proves that staging identical or repeated frames stores blobs under content-addressed SHA-256 paths (`blobs/{sha256}`) without modifying existing disk bytes.
  - Re-staging the same sequence reproduces identical canonical sequence manifests and digests.
  - `test_27_transaction_atomicity_on_failure` proves that a failed frame in a batch sequence leaves project revision and files unmodified.

### Criterion 4: Expose imported candidates to the existing assignment/preview API and local import tray without automatic assignment/approval
- **Status**: **VERIFIED**
- **Evidence**:
  - Staged PNG frames are cataloged in `source_catalog(root, manifest)` with `origin = "AUTHORED"`, `kind = "IMAGE"`, `availability = "AVAILABLE"`, `validation = "VALID"`, and technical metadata (`width`, `height`, `mode`, `transparency_kind`).
  - `manifest["ledger"]["assignments"]` remains empty after ingestion (no auto-assignment).
  - `manifest["review_events"]` remains empty after ingestion (no auto-approval).
  - Candidates are exposed in `#art-source` dropdown in the workbench UI and can be assigned directly to required occurrences.
  - End-to-end browser journeys documented in `tests/browser/rsf19-mcp.js`.

---

## Test Execution Summary

| Test Suite | Command | Exit Code | Result | Evidence Log |
|---|---|---|---|---|
| Ingestion & 28 Scenarios | `.venv/bin/python -m unittest tests/test_ingestion.py` | 0 | 29/29 PASS | `docs/evidence/rsf19/ingestion-tests.log` |
| Full Public Discovery | `.venv/bin/python -m unittest discover -s tests -p "test_*.py"` | 0 | 347/347 PASS | `docs/evidence/rsf19/public-tests.log` |
| Private Fixtures | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p "test_*.py"` | 0 | 36/36 PASS | `docs/evidence/rsf19/private-tests.log` |
| Schema Conformance | `scripts/check_*schema*.py` (7 checkers) | 0 | ALL PASS | `docs/evidence/rsf19/schema-tests.log` |
| Clean Distribution | `tests/check_distribution.py` | 0 | `DISTRIBUTION_CHECK_PASS` | `docs/evidence/rsf19/distribution.log` |
