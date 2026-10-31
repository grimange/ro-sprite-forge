# RSF-12 independent QA

**Verdict: QA_PASS** for the corrected snapshot. Reviewer:
`/root/rsf12_independent_qa`, repository-configured `forge_qa_reviewer`, separate
read-only context. The reviewer inspected code and independently ran verification;
no implementation edits, Kaneo writes, ownership changes or commits were made by QA.
This record transcribes the reviewer's final report; the coordinator owns tracker updates.

## Reviewed identity and acceptance

Manifest SHA-256: `e29850704258af8abeba319f175ecdf31cf42a7a336cbc83ddb15e206b9de9ea`.
Source archive SHA-256: `c62ab7f524c09077c978e0438621a5b7546b4cd09bef97345ccfa66201057765`.
QA verified all 11 manifest entries and all 11 archived members against current source,
and verified the authoritative plan digest recorded in VERIFICATION.md.

All four live RSF-12 criteria PASS for the declared Python inspection scope:

1. Pinned timing/reachability, raw delays and explicit diagnostic timing. Source-backed
   formulas, external context, unresolved semantics and fallback rejection independently checked.
2. Offsets, registration, origin and supported Player body/head synchronization.
   Geometry and private attachment tests pass; the one-child-anchor condition matches source.
3. Deterministic manual/timed stepping, loop/terminal behavior, speed and action/view
   selection. Boundaries, invalid inputs and repeatability independently checked.
4. Versioned renderer 1.1.0, geometry 1.0.0 and timing 1.0.0 bind canonical identities.
   Inconsistent selection versions are rejected.

## Findings, implementation corrections and independent retest

Initial verdict was QA_FAIL. All four findings were corrected by the implementer and
independently reproduced on the corrected snapshot with passing results:

- F1: Returned source anchors/events and selection data aliased internal/caller state.
  Defensive copies now prevent report mutation from changing later reports or callers.
- F2: Re-hashed selections could include false derived action/timing/fallback metadata.
  Complete reconstruction from declared inputs and canonical comparison now reject the
  prior forged Die/SILENT case with a typed error.
- F3: Fixed +/-1,000,000 auto-fit extrema rejected valid large signed offsets.
  Infinite initial extrema now yield the expected 36x34 canvas and [16,16,20,18]
  transformed bounds at +/-2,000,000 offsets, clipping INSIDE.
- F4: Huge integer timing values raised OverflowError. Pre-conversion range guards
  now produce typed errors for speed=10**1000 and elapsed_ms=10/speed=10**308.
  The latter multiplication path required one additional implementer correction and retest.

No unresolved mandatory finding remains.

## Independently executed commands

Environment: Python 3.14.4; Pillow 12.1.1; jsonschema 4.19.2.
Every command below exited 0 on the reviewed snapshot.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests:tests/private_fixture_hooks .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_animation_schema.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_contract_schemas.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_ledger_schema.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_coverage_schema.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14
```

Public: 229 PASS, 3.466 s. Private: 28 PASS, 5.132 s. Installed: 229 tests,
OK with one optional jsonschema skip; schema tooling was separately installed/tested.
Animation schemas: 2 schemas / 14 valid / 6 invalid; contracts: 3 / 13 / 55;
ledger: 1 / 4 / 8; coverage: 1 / 2 / 8, all PASS.
Python 3.12/3.13 unavailable: NOT_RUN.

Private checks compare all 160 archived native cases / 1,664 frame selections, source
slots/delays/fallbacks, Novice body/head anchors, Walk/terminal progression and ordered
12-layer Orc death frame. Inventory and byte preservation remain intact, including
Orc 512 motions / 1,776 visible references / 55 referenced of 57 stored images.
The accepted RSF-11 archive's per-file entries were also independently verified.

Repeated independent synthetic timed inspection produced identical report/PNG bytes:
report canonical SHA-256 `b31bde2c2eaff2dbd0ffe2b12d9757a667c857f209fe01ae0caf333e63a04ca0`;
PNG SHA-256 `0846ae73faccae095b155d1dc4979b49820f5179d2f859df068ee39b649374c4`.
These identify the reviewer's separate probe, distinct from examples.json.

Independent wheel SHA-256:
`9fc2a08ec15ed4c176b26d611c4c45062278d6c9b5dda7e9d19cd00470f48239`.
Independent sdist SHA-256:
`b7ea62750cd8a0a99442906e51869d2a909aa68f257d613aa8c8f381666a1c84`.
Repeated wheels matched within the checker and matched the implementer's wheel.
The independently created sdist digest differs from the implementer's; cross-run
byte-identical sdists are not claimed. The checker verifies isolated installation,
packaged schemas, source-archive asset exclusions and stdlib core operation without Pillow.
Full independent distribution output was at /tmp/rsf12-independent-qa-distribution.log;
this durable record preserves its commands, results and identities.

## Scope and tracker separation

No fresh native run, physical GPU comparison, audible playback, new Rust parity run or
artistic approval occurred. Archived native evidence was compared. Overall preview
fidelity remains PARTIAL; CPU/native pixel parity and artwork review remain UNVERIFIED.
Contact sheets and comparison/sequence exports remain live RSF-13 work.
M0-S/I/N retain their previously accepted PASS; M2 is not declared complete.

The reviewer's earlier MCP read saw In Progress/Codex with unchecked criteria. The
coordinator subsequently read back QA Review/Codex before recording this final QA_PASS.
Final acceptance/read-back is coordinator work, recorded in VERIFICATION.md.
