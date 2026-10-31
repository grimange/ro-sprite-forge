# RSF-9 independent QA

Final verdict: **QA_PASS** for corrected implementation.
Reviewer: `/root/rsf9_independent_qa`, repository-configured `forge_qa_reviewer` role.
Coordinator transcribed the review below; reviewer made no source/evidence edits or Kaneo writes.

Reviewed implementation-manifest SHA-256: `f0c0a7a125e25b1430da6f895c1d5ddcdf5d818aa188f550bee70a7d0520f74b`. All seven listed file hashes matched. Reviewer read repository policy/QA skill/config, live RSF-9 criteria, relevant plan sections, implementation source and tests. All 163 baseline files remain present; only the intentionally extended preexisting CLI differs.

## Finding, correction and fresh retest

Initial verdict: QA_FAIL. A correctly sealed `{'schema':'rsf.resolved-ledger/v1'}` caused `compare_ledgers` to raise KeyError for missing assignments. The CLI therefore failed with a traceback instead of the established typed error. The implementer corrected the input boundary with bounded closed report-shape, enum, duplicate-ID and source/occurrence/lineage/graph/attachment validation and added three regression tests.

Reviewer independently reproduced the corrected original case: ForgeError INVALID_INPUT with a precise field pointer; CLI exit3, no traceback, no published output. An additional independent mutation sweep rejected 284 malformed top-level/nested cases with typed errors and zero unhandled exceptions. No mandatory finding remains.

## Independently executed verification

CPython 3.14.4. Every command below returned exit0 on the corrected snapshot.

| Command | Independent result |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q` | 153 public tests PASS |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 16 private tests PASS |
| `.venv/bin/python scripts/check_contract_schemas.py` | 3 schemas, 13 valid / 55 invalid cases PASS |
| `.venv/bin/python scripts/check_ledger_schema.py` | 1 schema, 4 valid / 8 invalid cases PASS |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; 153 installed tests, repeated wheel equality and package exclusions PASS |

Independent synthetic case: 48 required layers, two direct/two explicit reused assignments, 44 unassigned; zero accepted reuse/approved roots without operator review records. A→B→C lineage retained mirror_x→translate ordering. Loss of A's source affected A/B/C while independent D was unaffected. Mixed attachment/reuse cycle was rejected. Private checks retained Novice body/head separation, source hashes and Orc's 512 motions /1776 visible layers /55 referenced of57 stored images. Inherited topology stayed unassigned until an explicit selection.

## Live acceptance assessment

1. PASS: exact requirement/source/revision bindings, ordered recipes, declared reuse and explicit attachment links.
2. PASS: missing/stale dependencies, self/indirect cycles, hash changes and accepted-reuse boundaries.
3. PASS: independent availability, validation, operator review, classic-reference origin and runtime-support states.
4. PASS: effort/root accounting follows explicitly approved dependencies; identical content does not infer reuse, aesthetic equivalence or replacement coverage.

Python3.12/3.13, fresh Rust parity and native playback were NOT_RUN. This slice does not modify those implementations. Source validity checks nonempty content identity only; image decoding and transform execution are explicitly NOT_RUN. QA does not approve artwork or establish new native/rendering claims. Accepted M0 gates remain applicable. Unrelated operator `.idea/` files were observed during review and must remain excluded/preserved.
