# RSF-9 verification

Task: `bbiahdelxdqg6o5aupyfj699` — [M1] Artwork ledger and explicit transform-reuse graph.
The live four acceptance criteria were retrieved before implementation; RSF-8 was Accepted and the only blocking dependency. Tracker writes were read back. Final independent verdict and acceptance read-back are recorded separately in this directory.

## Implementation identity and preservation

Plan SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e` (verified).
Accepted baseline: 163 files in `baseline-manifest.json`, SHA-256 `5b670c840feeb00c8ba34c3830140e2382fe366ffd86498f9b1885c8c9e47f16`.
Snapshot `baseline-source.tar.gz`: `b626d1e5592a71429c3d75f868b78f1b4e8ce414a927b85fd0fbf24c88350fa0`.
All baseline files remain present; the only existing file changed by RSF-9 is `src/ro_sprite_forge/cli.py`. New source files are enumerated in `implementation-manifest.json`. A final check after QA also observed an unrelated `.gitignore` edit uncommenting `.idea/`; it is preserved and excluded from RSF-9 implementation identity. The initial final-audit assertion expecting only the CLI difference reported this external edit; follow-up inspection confirmed all seven reviewed implementation hashes still match.

Final source manifest SHA-256: `f0c0a7a125e25b1430da6f895c1d5ddcdf5d818aa188f550bee70a7d0520f74b`.
The seven paths are `core/ledger.py`, `schemas/assignment-ledger-v1.json`, CLI, public/private ledger tests, `scripts/check_ledger_schema.py`, and `docs/architecture/RSF9_LEDGER.md`.

Existing Git HEAD: `f1bb19bb130beea8b89cf6c029209e93fb241d5a`. No commit, permission change, reset, clean, history rewrite or push was attempted for RSF-9. Git metadata remains read-only; accepted source remains protected by manifests/archive. Existing untracked project directories are preserved. Local AI configuration is excluded. Archive inspection found no ACT, SPR, GRF, raster image, video or cache files. Installed-distribution exclusion checks also passed.

## Contract and limits

Immutable `rsf.assignment-ledger/v1` declarations use exact RSF-8 target/revision, canonical requirements hash and layer occurrence IDs. Sources have declared identity/revision/hash, type/origin, optional imported pool/index and inventory/ACT/SPR provenance. Missing bytes are not invented. Recipes support ordered, validated mirror, offset, rational scale, rotation and crop declarations; no operation executes pixels.

Dependency resolution retains direct/reuse distinction, source/edge lineage, operation owners and explicit attachment parent/child/anchor links. It rejects dangling/stale references, duplicate bindings, and direct/indirect/mixed attachment cycles. Impact follows old and new reuse/attachment edges; changed source observations, composition and current target requirements identify affected and orphaned assignments without remapping them.

Availability, hash validation, operator review and runtime mapping remain independent. `VALID` here means nonempty content with matching hash; image decode and transform execution are NOT_RUN. Recorded review decisions are explicit caller-supplied OPERATOR assertions bound to the composition hash; no identity-authentication service or visual approval UI exists. The engine generates no review decisions. Classic references under explicit unchanged-reference policy never become authored replacement coverage. Accepted reuse requires every relevant bound review and valid observed source. Identical bytes never infer reuse or reduce source-art roots.

Limits: 100000 assignments/requirements, 10000 sources/attachments, 64 operations per assignment, 64 MiB source bytes and 1000000 expanded lineage/operation steps. No database or Rust/native runtime dependency is added to Python commands. Existing Actor/v1, Runtime-profile/v2, Target/v2 and resolved topology identities remain unchanged.

## Reproducible accounting and examples

Run `.venv/bin/python docs/evidence/rsf9/reproduce_examples.py`.
It computes the report twice and asserts byte equality. All supplied content is public synthetic non-image bytes. No operator approvals are supplied.

- Target `winter-walk`, revision 1, SHA-256 `4cfa9577fec2f355c85b090f366e6ab9b905a341b5aebc0b999c995d982da9e7`: 8 views × 6 frames × 1 layer = 48 frames and 48 layer requirements.
- Empty ledger: 0 selected assignments, 48 UNASSIGNED; structural requirements stay resolved.
- Example ledger: A and D DIRECT_SOURCE; B explicitly reuses A with `mirror_x`; C explicitly reuses B with `translate(x=3,y=-2)`. C keeps lineage A,B,C and ordered mirror→translate. Two direct, two reused, 44 unassigned, zero accepted reuse/approved roots/replacement occurrences.
- A requirement ID: `winter-walk/r1/body/action/Walk/slot8/view0/frame0/topologyd42cb041af04217047739b5d172cab9915112a1ef39b5aa11a2b98bcc1c17b94/layer0`. B/C/D use frame1/frame2/frame3. Full IDs of all unassigned occurrences are retained in the example, including view2/frame0.
- Source `art-a/r1`: actual/declared SHA-256 `974d215646e09ce5e059f34daa040e42041174296b2aa5e322d8f9e937b1d512`. Matching source gives A AVAILABLE/VALID/UNVERIFIED and B,C REUSED/VALID/UNVERIFIED. D uses independent source identity `art-d` with identical synthetic content; no automatic deduplication occurs.
- Explicitly missing art-a: MISSING/UNVERIFIED/UNVERIFIED. Changed bytes against the original hash: AVAILABLE/INVALID/UNVERIFIED. Neither becomes an automatic fallback.
- Revised art-a propagates impact to A,B,C; D remains byte-identical and unaffected. Exact replay has no impact. Tests also cover transformation-only changes, stale requirements/orphans and unchanged review evidence.

Canonical `examples.json` SHA-256: `26c83addfa19fd636ee41067f9d1357b9d461d1d36a0399e459cf50ade7e5ed8`.
Resolved example canonical identity: `2deb2b219568d776b4afb98afb771995753e441702565ce1c7c00bfa96770eb9`.
Impact canonical identity: `f8f81fe402f35f2593f4716789c9d258384e6ebc8203d46d53b8f6a6ebbb8621`.

## Automated execution

Linux, CPython 3.14.4, jsonschema 4.19.2. All following commands returned exit 0 after the QA correction; logs are adjacent to this file.

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_ledger.py -q` | 34 ledger tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q` | 153 public tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 16 private tests PASS, no skips |
| `.venv/bin/python scripts/check_contract_schemas.py` | 3 existing schemas; 13 valid / 55 invalid cases PASS |
| `.venv/bin/python scripts/check_ledger_schema.py` | 1 new schema; 4 valid / 8 invalid cases PASS |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; 153 installed tests; repeated wheel equality and isolation PASS |
| `.venv/bin/python docs/evidence/rsf9/reproduce_examples.py` | repeated canonical bytes identical |

Python 3.12 and 3.13: NOT_RUN, unavailable locally. No cross-platform reproducibility claim. Rust parity and full native playback: NOT_RUN for RSF-9 because their source/codec/resource inputs were unaffected; previously accepted M0 evidence remains applicable. No private fixture is required by public tests or installed package tests.

## Private references

All source resources stay outside public artifacts. The 16-test suite includes two new ledger regressions: separately identified Novice body/head topology (912 combined frames/layers) remains entirely unassigned; Orc topology retains 512 frames and 1776 ordered visible layer occurrences, all unique and unassigned. Inventories are unchanged and repeated ledger reports identical.

| Resource | ACT SHA-256 | SPR SHA-256 |
| --- | --- | --- |
| Novice body | a82086ba005506a16ee0740ebd1d33c43de8cc4ee1a622ea933ff9e0502c1c77 | 7f4efe357b0f80e71ba2dcdb93d1c110988b1b8f382e1dbfc722e3a2cf85a533 |
| Novice head | 96cb4c7daada65ead29ade650c34da1cba93937d3b360c5468506c3d056219de | dfc548c5cfd9aeb66616c5912df78773c2798834f9412a309a5a2b4f5868ac95 |
| Orc Skeleton | 31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2 | a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f |

Existing checks retain Novice body's 456 motions, 110 referenced identities/108 decoded contents, and Orc's 55 referenced/57 stored identities with unused indices36,39. These are fixture observations, not production constants. Private source hashes and byte-preservation regressions pass.

## Independent QA correction

Reviewer `/root/rsf9_independent_qa`, configured role `forge_qa_reviewer`, found a malformed externally supplied resolved report could pass its content seal then raise KeyError during comparison. Root cause: content identity was mistaken for structural validity at that boundary. Implementer added bounded closed report shape/enums, unique identities and source/occurrence/lineage/dependency/attachment reference validation before impact processing. New core/CLI regressions require INVALID_INPUT/exit3 and no output publication or traceback. The original failure and correction remain in Kaneo comments; reviewer independently retests the final manifest. See `QA_REVIEW.md` for the final verdict and independent commands.

## Gates and next scope

M0-S PASS, M0-I PASS, M0-N PASS, overall M0_VERIFIED retained for the already accepted scope. No new native or visual acceptance is claimed. RSF-9 provides ledger/provenance/impact only; coverage evaluation and missing-art work orders belong to RSF-10, which remains unstarted.

Final Kaneo read-back in `KANEO_READBACK.json`: RSF-9 status `done` (Accepted), four acceptance checkboxes completed, final independent QA_PASS and corrected source identity recorded. No pending writes. RSF-10 `uzuir12040jroddz4idk8ahi`, [M1] Coverage evaluation and exported missing-art work orders, remains `to-do` (Backlog); its only blocking dependency RSF-9 is completed. It was not started.
