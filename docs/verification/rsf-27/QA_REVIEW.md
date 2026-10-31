# Independent RSF-27 review — QA_PASS

Reviewer: repository-configured `forge_qa_reviewer`, separate context
`/root/rsf24_qa`. Read-only review; no source edits, Kaneo writes, ownership changes
or artistic approvals. Coordinator records the review here from the reviewer's final
response; independently executed checks are distinguished from reviewed evidence.

Reviewed implementation-manifest.json SHA-256:
`09158eb6674dc68b54128452d5d66f098fe675d4e612ed752173025a5123939e`.
All 13 implementation/document paths and 69 evidence file hashes independently match.

Reviewer verdict: **QA_PASS — RSF-27. No mandatory technical finding remains open.**
Each of the five live acceptance criteria PASS within the declared diagnostic scope.
The reviewer independently fetched live task criteria and the final QA Review state;
only the coordinator subsequently synchronizes acceptance.

## Independently executed verification

| Invocation/check | Actual result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -q` | 452 PASS, exit 0 |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 40 PASS, one existing legacy native-report skip of 41, exit 0 |
| `.venv/bin/python tools/rust-oracle/test_parity.py` | 11 PASS, exit 0 |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tools/korangar-native -v` | 17 PASS, exit 0 |
| Pinned `cargo test --offline --locked --manifest-path /tmp/rsf27-native-sealed/Cargo.toml` with recorded environment | 4 PASS, exit 0 |
| All ten `scripts/check_*schema*.py` validators | PASS, exit 0 each |
| Native executable to `/tmp/rsf27-qa-native-1` and `/tmp/rsf27-qa-native-2` | exit 0; identical reports and corresponding captures |
| verify_walk.py on independently generated report | exit 0, NATIVE_CHECKS_PASSED |
| walk_controls.py to `/tmp/rsf27-qa-controls-1` | exit 0, 17 rejected controls, source integrity PASS |
| Fresh reproduce.py to `/tmp/rsf27-qa-reproduce`, sealed stage/executable, `--private` | exit 0, six subprocesses exit 0, REPRODUCED |

Exact fresh reproduction arguments/working directories/statuses are retained in
reviewer-reproduction-commands.json. Native execution used DISPLAY/WAYLAND_DISPLAY
unset and `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json`, from the sealed stage.
The reviewer independently checked all 89 upstream hashes, generated stage hashes,
executable identity, actual loaded-byte identities, prepared metadata and texture
selection, all 56 capture hashes/dimensions, source immutability and private exclusion.

The schema script list is animation, comparison, compilation, contract, coverage,
extraction, ingestion, ledger, review and transformation. The final response's script
enumeration accidentally omitted ingestion; the reviewer immediately reran
`.venv/bin/python scripts/check_ingestion_schema.py`: exit 0,
`INGESTION_SCHEMA_PASS schemas=1 valid=3 invalid=6`; QA_PASS unchanged.

## Independently established native evidence

176 cases; 1,060 prepared frames; 2,796 prepared layers; 1,080 selected frames;
4,144 drawn layer occurrences; 56 actual Vulkan readback captures; 196 preserved
selection samples; three targeted raw layer occurrences; zero mandatory mismatches.
All eight Walk views with camera directions 0/4 resolve through pinned native code
to the expected slots 8–15. Native selected frames, ordered layers and effective
textures match independently decoded expectations. Python does not choose native frames.

The mixed pool keeps five indexed entries and appends two truecolor replacements;
the targeted occurrences use textures 6, 6 and 7. Shared unaffected consumers retain
original contents. Independent Rust checks all synthetic occurrences and ACT metadata
outside authorized reference changes. Orc 12-layer Death ordering/placement and
Novice body/head preparation/native Walk are preserved. Private compilation tests
independently verify the other 103 Novice slots and separate head resources; modified
Novice native playback is not claimed.

Eight actual negative native executions and nine tampering controls all reject false
proof. Two wrong-pair native runs render successfully but fail canonical-pair checking.
Six other native failures exit 101 with no successful report; invalid pool index uses
the existing native bounds panic, accurately disclosed. Fallback/modulo/masked-direction
observations are excluded from exact success.

The repeated report hash is
`af20687d42dcd9dda8bc9b9288daf81b498723e9676837f666009bf1a6db46c5`.
The independently checked executable hash is
`27986612b7cb3af691f6f0b2853721d03c11089e66bdc921ee9d460f441f391d`.
Compiled ACT/SPR/build-manifest hashes match VERIFICATION.md and the sealed provenance.

## Findings and final scope

No binary/runtime defect was found. Two evidence wording findings were corrected and
independently reread before sealing: physical paths belong to inputs/provenance while
native loader observations establish actual returned hashes/logical names/lengths;
event preservation belongs to Rust whole-ACT comparison, while native event fields
are recorded but not independently asserted by the native checker. No implementation
change followed the reviewed manifest.

Installed distribution was **evidence-reviewed, not independently rerun**: sealed log
reports 452 discovered / 443 PASS / nine optional schema/Rust skips, exit 0,
DISTRIBUTION_CHECK_PASS. Private resources and captures are excluded; public captures
are synthetic. The 146-file baseline has 143 unchanged entries; only existing main.rs,
prepare.py and README changed, alongside the declared new files. Production code,
schemas, Rust oracle and previous tests remain unchanged.

Python 3.14.4 tested. Python 3.12/3.13 and pinned rustfmt unavailable: NOT_RUN.
Browser NOT_RUN because no UI controls changed. Hardware GPUs, ordinary gameplay,
audible sound and universal/reference pixel parity are UNVERIFIED/NOT_TESTED.
Same-backend report/capture repeatability does not establish reference-render parity.

Reviewer gate verdict: **M5-S PASS; M5-I PASS; M5-N PASS** for bounded exact compiled
synthetic Walk load, selection and actual software-Vulkan rendering in the isolated
pinned corridor. Level D reference pixel parity remains UNVERIFIED. This supports
the documented scoped engineering milestone acceptance; no full-profile production
artwork readiness or real-art approval is granted. Output remains PARTIAL_DIAGNOSTIC.

At final reviewer live read-back, RSF-27 was QA Review (`in-review`), owned by Codex
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. Reviewer requested coordinator record QA_PASS,
check the five evidenced criteria, synchronize acceptance and read back the final state.
