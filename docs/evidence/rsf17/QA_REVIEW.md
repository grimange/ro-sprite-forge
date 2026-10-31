# RSF-17 independent QA

**QA_PASS — RSF-17 objective implementation scope.** No mandatory findings remain.

Reviewer: configured `forge_qa_reviewer`, session `/root/rsf17_independent_qa`.
The reviewer inspected live acceptance criteria, source, accepted baseline, tests and
actual browser evidence. Reviewer made no implementation/evidence edits, Kaneo
writes, ownership changes or artistic approvals. This report records the reviewer's
final returned verdict, synchronized by the coordinator.

Independently executed with Python 3.14.4, all exit 0:

- Focused `tests/test_interactive.py`: 13 PASS.
- Full public unittest discovery after corrections: 299 PASS.
- Private fixture discovery: 36 PASS.
- `scripts/check_contract_schemas.py`: 3 schemas, 13 valid/55 invalid cases PASS.
- Offline `tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python
  /usr/bin/python3.14`: PASS, 298 installed tests at the earlier snapshot; repeated
  wheels, package isolation and exclusions passed. Coordinator separately repeated
  the distribution check on the final corrected source: 299 tests, one optional
  Pillow skip, DISTRIBUTION_CHECK_PASS. Other Python versions were NOT_RUN.

Two findings were corrected and independently retested:

1. Missing/corrupt blobs blocked project read routes. Reads now preserve an
   inspectable manifest; content-consuming operations retain hash validation.
   Added HTTP regression and relayed MCP missing-source assertion pass.
2. Play after scrub/speed change restarted at frame zero. The backend now derives
   and verifies the selected resume offset through the canonical Python timeline.
   Tests cover frame 3 at speeds 0.5, 1 and 2; MCP assertions observed frame 3 on
   initial and speed-adjusted resume.

Browser verification scope: reviewer independently exercised an earlier Chromium
journey that exposed a selection defect; that run was not a complete E2E PASS.
After the operator required Playwright MCP, the reviewer context lacked MCP browser
tools. Coordinator executed the complete MCP journeys and reviewer-selected extra
assertions; reviewer inspected both scripts and `browser-results.json`. This is
not a separate reviewer-controlled MCP browser launch.

Final Chromium 156.0.8078.73 evidence: synthetic journey PASS (3 direct, 1 reused,
44 unassigned, zero approvals); no unexpected JavaScript errors/network failures;
expected HTTP 422 missing candidate and 409 stale save are separate. Private Novice
UI import/assignment/reopen PASS (104 slots, 456 motions, 110 referenced images,
108 contents). Additional MCP assertions PASS: resume frame 3, speed resume frame
3, Attack terminal frame 4, missing-source reopening, native confirmation dialog.
No private screenshot was published.

The Python core remains authoritative for ledger, dependencies, coverage, timing
and compositing. Batch validation precedes one optimistic save. Source provenance,
availability, validation, fidelity and review remain separate. No baseline files
were deleted. Existing codecs, canonical engines and frozen runtime evidence are
unchanged. Final reviewed hashes are recorded in `implementation-manifest.json`.

M0/M2 accepted evidence remains applicable; no new native run or artistic approval
is claimed. RSF-17 does not complete M3. RSF-18 remains outside this review.
