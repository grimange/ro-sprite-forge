# RSF-10 verification

Task: `uzuir12040jroddz4idk8ahi` — [M1] Coverage evaluation and exported missing-art work orders.
The live five acceptance criteria were retrieved before implementation; RSF-9 was Accepted and the only blocking dependency.

## Implementation identity and preservation

- Implementation plan SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e` (verified).
- Accepted baseline: All 163 files from RSF-9 baseline manifest preserved; previous 7 implementation files from RSF-9 remain intact and unchanged. Unrelated operator `.gitignore` edit preserved.
- RSF-10 implementation manifest SHA-256: `e4098f1ad55a5f810d9489b9093b232f01e47236873f7053c7aad2cb01b4ceb7`.
- Seven implementation paths:
  1. `docs/architecture/RSF10_COVERAGE.md`
  2. `scripts/check_coverage_schema.py`
  3. `src/ro_sprite_forge/cli.py`
  4. `src/ro_sprite_forge/core/coverage.py`
  5. `src/ro_sprite_forge/schemas/coverage-report-v1.json`
  6. `tests/private_fixture_hooks/test_coverage_fixtures.py`
  7. `tests/test_coverage.py`
- Archive `implementation-source.tar.gz` contains only these seven files. Zero private ACT, SPR, GRF, raster images, or videos are included.
- No Git commit, permission change, reset, clean, or push was performed. Git working-tree changes remain inspectable.

## Contract and limits

- Closed Draft 2020-12 schema `rsf.coverage-report/v1` describes canonical machine-readable coverage reports.
- `evaluate_coverage` consumes `rsf.resolved-requirements/v1` and either an `AssignmentLedger`, declaration dict, `rsf.resolved-ledger/v1`, or None (evaluated as unassigned).
- Rejects mismatched target references, mismatched requirements SHA-256, and invalid ledger schemas.
- Preserves orthogonal status dimensions:
  - `structural_specification`: `COMPLETE_FOR_FULL_PROFILE`, `COMPLETE_FOR_DECLARED_SCOPE`, `UNDERSPECIFIED`
  - `assignment_coverage`: `COMPLETE_FOR_FULL_PROFILE`, `COMPLETE_FOR_DECLARED_SCOPE`, `PARTIAL`, `UNASSIGNED`
  - `accepted_artwork_coverage`: `COMPLETE_FOR_FULL_PROFILE`, `COMPLETE_FOR_DECLARED_SCOPE`, `INCOMPLETE`
  - `completeness`: `COMPLETE_FOR_FULL_PROFILE`, `COMPLETE_FOR_DECLARED_SCOPE`, `INCOMPLETE`, `UNDERSPECIFIED`
  - `technical_validation`: strictly `NOT_RUN`
  - `preview_fidelity`: strictly `UNVERIFIED`
  - `native_evidence`: strictly `UNVERIFIED`
  - `export_ready`: strictly `false`
- Nine actionable work-order categories: `SUPPLY_ARTWORK`, `RESTORE_OR_LOCATE_SOURCE`, `CORRECT_INVALID_SOURCE_OR_ASSIGNMENT`, `RESOLVE_REQUIREMENTS`, `VERIFY_SOURCE_CONTENT`, `VERIFY_TRANSFORMATION`, `REVIEW_ARTWORK`, `REVIEW_STALE`, `RESOLVE_RUNTIME_SUPPORT`.
- CLI commands `coverage` and `missing` provide canonical JSON publication and human-readable work-order text export with atomic no-overwrite guarantees.

## Reproducible accounting and examples

Run `.venv/bin/python docs/evidence/rsf10/reproduce_examples.py`.
It computes seven coverage scenarios deterministically and verifies byte-exact equality across runs.
Canonical `examples.json` SHA-256: `04e3795e1f5af14aa768bf678e5269f2551a46add89dd2244a465d54b3195d92`.

1. **Fully unassigned Walk:** 48 required frames, 48 required layers. 48 unassigned, 0 assigned. All 48 items are `SUPPLY_ARTWORK` (`UNASSIGNED_OCCURRENCE`). `assignment_coverage`: `UNASSIGNED`, `completeness`: `INCOMPLETE`.
2. **Partially assigned Walk (RSF-10 synthetic scenario):**
   - 48 frames, 48 layers (8 directions × 6 frames × 1 layer).
   - Assignments: A direct (`art-a`), B reuse A (`mirror_x`), C reuse B (`translate(3, -2)`), D direct (`art-d`).
   - 2 direct assignments, 2 explicit reuse, 44 unassigned occurrences.
   - 4 valid assignments, 0 invalid, 0 unverified.
   - Pending technical checks: 4 image decoding (`NOT_RUN`), 2 transform execution (`NOT_RUN`).
   - Reviews: 0 approved, 0 rejected, 4 unverified, 0 not_required, 0 stale.
   - 0 approved source art roots, 0 validated replacement occurrences.
   - Work order: 44 `SUPPLY_ARTWORK`, 4 `REVIEW_ARTWORK`. Total 48 unresolved items.
   - Status: `structural_specification`: `COMPLETE_FOR_DECLARED_SCOPE`, `assignment_coverage`: `PARTIAL`, `accepted_artwork_coverage`: `INCOMPLETE`, `completeness`: `INCOMPLETE`.
3. **Missing source bytes:** `art-a` content is None. Occurrences A, B, C propagate `RESTORE_OR_LOCATE_SOURCE`. Independent assignment D remains unaffected (`VALID`).
4. **Invalid source hash:** `art-a` has corrupted bytes. Occurrences A, B, C propagate `CORRECT_INVALID_SOURCE_OR_ASSIGNMENT` (`SOURCE_HASH_MISMATCH` / `DEPENDENCY_INVALID`).
5. **Full profile target:** All actions in player profile specified. `full_profile_specified`: `true`, `structural_specification`: `COMPLETE_FOR_FULL_PROFILE`.
6. **Underspecified topology:** Slot with `frame_count: None` and slot with `topology: None`. Produces `RESOLVE_REQUIREMENTS` items. `structural_specification`: `UNDERSPECIFIED`, `completeness`: `UNDERSPECIFIED`.
7. **Source revision change:** Source `art-a` updated to revision 2 with new bytes. Reevaluated deterministically without auto-approval.

## Automated execution

Linux, CPython 3.14.4, jsonschema 4.19.2. All commands returned exit code 0. Logs are adjacent to this file.

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_coverage.py -v` | 19 coverage tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | 172 public tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 18 private tests PASS, no skips |
| `.venv/bin/python scripts/check_contract_schemas.py` | 3 contract schemas; 13 valid / 55 invalid PASS |
| `.venv/bin/python scripts/check_ledger_schema.py` | 1 ledger schema; 4 valid / 8 invalid PASS |
| `.venv/bin/python scripts/check_coverage_schema.py` | 1 coverage schema; 2 valid / 8 invalid PASS |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; 172 installed tests; wheel hash equality and isolation PASS |
| `.venv/bin/python docs/evidence/rsf10/reproduce_examples.py` | Repeated canonical bytes identical |

Python 3.12 and 3.13: NOT_RUN (unavailable locally). Rust decoder parity and native Korangar playback: NOT_RUN (their input codecs and resources are unaffected; previously verified M0 evidence remains applicable).

## Private references

Private fixtures remain strictly outside Git and public deliverables. The 18-test private suite includes `test_coverage_fixtures.py`:
- Novice body and head reference: 912 combined frames/layers across separate `body` and `head` resources. Evaluates to 912 unassigned occurrences, zero replacement artwork, `COMPLETE_FOR_FULL_PROFILE` structural specification, and `UNASSIGNED` assignment coverage.
- Orc Skeleton: 512 frames, 1,776 visible layer occurrences. Evaluates to 1,776 unassigned occurrences, zero replacement artwork, `COMPLETE_FOR_FULL_PROFILE` structural specification, and `UNASSIGNED` assignment coverage.

## Gates and milestone status

- `M0-S`: PASS, `M0-I`: PASS, `M0-N`: PASS; overall `M0_VERIFIED` retained.
- `RSF-7`: Versioned actor, target and runtime-profile contracts: Accepted.
- `RSF-8`: Explicit/inherited ordered layer-topology requirements: Accepted.
- `RSF-9`: Artwork ledger and explicit transform-reuse graph: Accepted.
- `RSF-10`: Coverage evaluation and exported missing-art work orders: Implemented, verified, ready for independent QA.
- No new native or visual acceptance is claimed. `export_ready` remains false.
