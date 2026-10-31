# RSF-17 verification

Task `j4bq4r7uxi9z6l378go7oomo`; implementer Codex
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. Plan SHA-256 remains
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.

Implementation adds exact-source assignment, explicit batches/reuse, authoritative
Python playback, resource/frame inspection and comparison to the existing workspace.
See `docs/architecture/RSF17_INTERACTIVE.md` and the implementation manifest.

## Executed verification

Python 3.14.4, Pillow 12.1.1, jsonschema 4.19.2. Python 3.12/3.13 NOT_RUN:
interpreters unavailable. Each following command exited zero:

```
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_interactive.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14
```

Focused: 13 PASS. Public: 299 PASS. Private: 36 PASS. Installed distribution:
299 tests OK, one expected optional-Pillow skip in its stdlib-only environment;
`DISTRIBUTION_CHECK_PASS`, repeated build/isolation/private-exclusion checks PASS.
Local HTTP checks require loopback socket permission; the first sandboxed focused
invocation could not create sockets, then the authorized socket-enabled run passed.

All five schema scripts passed: contracts (3 schemas, 13 valid/55 invalid), ledger
(1, 4/8), coverage (1, 2/8), animation (2, 14/6), comparison (3, 11/13).
`node --check src/ro_sprite_forge/static/workbench.js` passed.

## Actual browser execution

Playwright MCP, Chromium 156.0.8078.73, installed wheel in an isolated environment,
loopback service port 8180. `browser-results.json` preserves actual results.
The full synthetic journey exercised project creation, explicit Walk topology,
UNASSIGNED filtering, tree selection, work-order download, pair import, source tray,
single and batch assignment, mirror reuse, save/reopen, keyboard selection,
step/scrub/play/pause/speed/action/view controls, side-by-side/difference comparison,
missing candidate, unresolved timing and two-browser stale save conflict.

Observed: 48 requirements; 3 direct + 1 reused; 44 unassigned; zero approvals;
zero unexpected console errors and zero failed requests. Expected HTTP 422/409
responses are separate from unexpected browser errors. Comprehensive automation
accepts mapping confirmations with an explicit test shim. A fresh MCP tab separately
verified native confirmation text, `browser_handle_dialog(accept=true)`, canonical
publication (fifth explicit synthetic assignment), and no visual approval.

Audited Novice UI import verified original ACT/SPR hashes and computed 104 slots,
456 motions, 110 referenced images and 108 distinct contents. Direct/reuse changes
persisted across reload. Reviewer-selected MCP retests observed initial resume frame
3, speed-change resume frame 3 and terminal Attack frame 4. Deleting only a synthetic
SPR blob still permitted reopen with 48 requirements, preserved assignments and a
MISSING/UNVERIFIED source diagnostic. The synthetic blob was restored afterward.
Private UI testing produced no screenshot artifact. Public screenshot is synthetic.

## Independent correction loop

Reviewer found that missing blobs blocked the project read routes and that Play
restarted after scrubbing/speed changes. Both root causes were corrected. New HTTP
regression verifies corrupt and deleted blob inspectability. Resume positions are
calculated using Python timeline seeks; focused tests cover speeds 0.5, 1 and 2.
Reviewer independently reran focused/public tests and inspected the actual MCP
results, plus independent private/schema/distribution checks. See `QA_REVIEW.md`.
Reviewer's tool context lacks MCP browser tools; reviewer-selected browser assertions
were relayed through the coordinator's MCP connection. This is not described as a
separate reviewer-controlled browser launch.

## Identity and preservation

`accepted-baseline.json` preserves 364 accepted-file hashes. No accepted files were
deleted; the modified existing files are the server, project schema and three static
assets. Distribution build metadata may refresh; no Git commit/push was made.
Existing source archive fallback is preserved. New implementation/evidence hashes
are in `implementation-manifest.json`; deterministic canonical workspace/ledger
results and exact example IDs are in `determinism.json`. No private ACT/SPR/GRF or
private screenshot is added to the source/distribution.

M0_VERIFIED, M1 accepted planning and M2_PREVIEW_AND_DIAGNOSTICS_VERIFIED remain
applicable. No new native run or artistic approval is claimed. RSF-18 remains future;
M3 is not complete. Assignment-source preview executes mirror only on this path;
other recipes are diagnosed. Animation previews select explicit existing resources,
and do not imply a modified compiled resource or approved replacement artwork.
