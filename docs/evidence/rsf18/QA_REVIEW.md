# RSF-18 independent QA

Verdict: **QA_PASS**, configured `forge_qa_reviewer`, separate context
`/root/rsf18_independent_qa`, 2026-10-30. Coordinator transcribes the reviewer's
returned findings; reviewer made no source/evidence edits or Kaneo writes.

Reviewer independently inspected the live five acceptance criteria, relevant plan,
implementation, schemas, tests and 386-file accepted baseline. No files missing.
No mandatory reproducible defects remain.

Independent execution, Python 3.14:

| Check | Result, exit 0 |
|---|---|
| Public unittest discovery | 318 PASS, 15.897 seconds |
| Private fixture discovery | 36 PASS, 11.374 seconds |
| Focused `test_review.py` | 19 PASS |
| Contract schemas | 3 schemas, 13 valid / 55 invalid PASS |
| Ledger schema | 4 valid / 8 invalid PASS |
| Coverage schema | 2 valid / 8 invalid PASS |
| Animation schemas | 14 valid / 6 invalid PASS |
| Comparison schemas | 11 valid / 13 invalid PASS |
| Review-event schema | 3 valid / 6 invalid PASS |

Commands used `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest
discover -s tests -q`, the corresponding `tests/private_fixture_hooks` discovery,
focused `-p test_review.py`, and all six `scripts/check_*schema*.py` checkers.

## Independent browser execution

Reviewer directly executed `tests/browser/rsf18-mcp.js` using **Playwright MCP**,
Chromium **156.0.8078.73**, fresh isolated synthetic project
`rsf18-1793352647508`. This is independent browser execution, rather than screenshot
inspection alone. Initial shared-profile lock was resolved by coordinator closing
its MCP session; reviewer then controlled its own fresh context.

All seven journeys passed: RSF-17 assignment/reuse/playback/comparison regression;
individual approval/reopen; rejection; exact batch; A/B/C stale with D preserved;
separate-context stale submission conflict; unexecuted translation blocked.
No unexpected JavaScript errors or network failures. Expected negative HTTP
responses: 422, 409, 409. Final synthetic counts: 1 APPROVED, 3 STALE,
44 UNVERIFIED; export_ready=false.

Reviewer inspected the actual review dialog screenshot, including synthetic image,
exact member basis/evidence identities and PARTIAL/provisional limitations.
Copies: `synthetic-review-dialog-qa.png`, `synthetic-review-workbench-qa.png`.

## Correction and final build distinction

Coordinator corrected the ephemeral ledger review projection to retain the recorded
displayed-evidence hash instead of putting a composition hash in that metadata field.
Historical event hashes were already correct. Reviewer's current-source 318/36 and
focused/schema runs include the correction. Its browser run used the preceding
installed build. Coordinator subsequently rebuilt/reinstalled and reran all seven
browser journeys successfully on final wheel
`d7c46473d8acae0cfb0b66be25e685b488337b59bf45420fd99f0948edeaba9c`;
see `browser-release-results.json`. No source change followed independent QA.

Packaging verification was coordinator-executed, not independently rerun by reviewer.
Python 3.12/3.13, other platforms and full native Korangar were NOT_RUN. Private
artwork received no automated approval. QA scope is explicitly provisional ordered
source-layer review mechanics, not compiled-animation/native/artistic acceptance.
