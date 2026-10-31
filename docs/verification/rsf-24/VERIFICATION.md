# RSF-24 verification packet

Implementer: Codex `aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`.
Live task, four acceptance criteria and dependency graph read; RSF-23 Accepted.
Ownership read back before implementation. Backlog → Ready → In Progress → QA Review;
review findings recorded, FAILED → In Progress for correction → QA Review.
Independent read-only reviewer: `/root/rsf24_qa`, repository `forge_qa_reviewer` role.

The accepted compiler is extended, with no codec or Rust source changes. Complete effective
occurrence mappings, explicit policy handling, safe defaults, conversion-loss provenance,
pre-write plans and pair publication validation are implemented. See SEMANTICS.md and
implementation.diff. Baseline repository is untracked; pre-edit snapshots were captured
under /tmp. No commit, push, reset or external source modification was performed.

All following final commands exited 0:

| Command | Actual result | Evidence |
|---|---|---|
| `.venv/bin/python -m unittest discover -s tests -p test_image_pool_remapping.py` | 13 PASS; 9 Rust-checked pool/policy subcases | focused.log |
| `.venv/bin/python -m unittest discover -s tests -v` | 431 PASS | public.log |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 38 discovered; 37 PASS, 1 native-report-dependent skip | private.log |
| `.venv/bin/python tools/rust-oracle/test_parity.py` | 11 PASS | rust-parity.log |
| Ten `.venv/bin/python scripts/check_*schema*.py` commands | 10 PASS | schemas.json |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; 431 discovered, 428 PASS, 3 external-tool skips; repeated wheel identity and private-art exclusion PASS | distribution.log |
| `.venv/bin/python docs/verification/rsf-24/reproduce.py` | Three independent compiled ACT/SPR bytes and canonical manifests identical; Rust PASS | environment.json, golden-manifest.json |

Python 3.14.4 and Pillow 12.1.1 were used. Python 3.12/3.13 NOT_RUN: unavailable.
Installed-distribution skips: optional jsonschema in two existing tests and the repository-only
Rust golden matrix; all schema checks and Rust matrix ran successfully in the source environment.
Initial distribution attempt failed because the offline Pillow wheel was missing; pinned
Pillow 12.1.1 was downloaded into /tmp/rsf24-wheelhouse, then the complete check passed.

Private fixtures: Novice hashes and counts, 103 unaffected slots, separate head and Rust parity
passed. Orc 40 slots, 512 frames, 1,776 visible layers, 57 stored/55 referenced images,
12-layer Death preservation and compiler/Rust regressions passed. Initially absent Orc assets
were recovered from the local archive and matched both audited hashes; see
PRIVATE_FIXTURE_RECOVERY.md. The sole private skip reads earlier RSF-6 native layer-report
files missing under /tmp/rsf6-native-run-final-1. No missing private artwork checks remain.

Real Chromium coordinator journeys use tests/browser/rsf23-mcp.js, extended to assert the
preserve_pool default and explicitly select RGBA. All ten journeys passed through MCP.
The final run on a freshly started final-code server used an isolated browser after MCP's
shared profile became locked:
`node docs/verification/rsf-24/browser-run.cjs /home/ra/.npm/_npx/9833c18b2d85bc59/node_modules/playwright`.
Exit 0; browser.log ends RSF24_CHROMIUM_TEN_JOURNEYS_PASS. The runner changes only
port 8182 to 8183 and trims the MCP function-expression terminator. Server command:
`.venv/bin/python -m ro_sprite_forge serve --projects-dir /tmp/rsf24-browser-final --port 8183`.
A fresh server was used so backend checks include the final corrections.
Synthetic browser reviews are test records and confer no subjective artwork approval.

Independent QA found and implementer corrected:

1. Implicit RGBA default: core, CLI, API and workbench now preserve_pool unless RGBA selected.
2. Actual bounded manifest profile_version mismatched the prior schema; profile references
   now validate while retaining legacy compatibility. Writer 1.1 requires remapping evidence,
   canonical ordering, valid pool/texture indices and target/unaffected identity agreement.
3. Publication checked body hashes only; head presence, complete pair, length, hashes and
   decoded inventory now validate before publication. Corrupt/missing head outputs fail closed.

Additional regressions cover exact indexed palette/alpha/hidden-RGB rejection, unchanged
raw RLE and palette bytes, deterministic order/reuse, duplicate and unused original identities,
shared copy-on-write, mixed-pool boundary movement, maximum supported index 4095, count
append overflow, invalid occurrence references, no-op byte identity and existing-output safety.
Accepted compiler tests were changed only to explicitly request RGBA where their artwork
requires it. Existing stale/hash/source/approval/ledger guards remain covered by regressions.

M5-S: PASS for this bounded structural/preservation task.
M5-I: PASS for generated binaries plus both audited private actor compiler regressions.
M5-N: UNVERIFIED; no new native run. M5 remains open. Full actor export/visual approval
readiness is not inferred from this task. Final reviewer verdict and tracker read-back follow
in QA_REVIEW.md and KANEO_READBACK.json.
