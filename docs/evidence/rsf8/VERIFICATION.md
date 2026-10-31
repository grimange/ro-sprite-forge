# RSF-8 implementation verification — accepted

Task: akj2012swhvsebugprsl0v5j, RSF-v1.1/M1-02. The live five-criterion
checklist and sole blocking dependency RSF-7 Accepted were verified via MCP.
RSF-8 moved Ready → In Progress with read-back before implementation.

Implementation: core/topology.py, bounded contracts.py/target-v2 schema extension,
CLI `resolve`, schema checker, synthetic/private tests, RSF8_TOPOLOGY.md.
The implementation-manifest pins exact source identities. No ACT/SPR codec,
frozen profile, existing v1 requirements, Rust oracle or native harness changes.

## Verification performed

All commands below exited 0 using CPython 3.14.4 (Linux).

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_topology.py -v` | 25 new tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | 119 public tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 14 private tests PASS, no skips |
| `.venv/bin/python scripts/check_contract_schemas.py` | 3 schemas, 13 valid, 55 invalid cases PASS; jsonschema 4.19.2 |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS, installed 119 tests, repeated wheel bytes identical |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/test_parity.py` | 11 tests PASS |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/private_parity.py` | Novice body/head and Orc AGREEMENT |
| `PYTHONPATH=src .venv/bin/python tools/korangar-native/test_verifier.py` | 9 verifier unit tests PASS |
| `.venv/bin/python docs/evidence/rsf8/generate_examples.py` | Repeated canonical report bytes identical, including reversed private inventory input order |

Logs retain actual results. examples.json contains computed counts, canonical
report and serialized hashes, stable ID samples and exact source provenance.
Regenerate with the command above; private fixtures use existing external hooks.
No private pixels or original binary assets are stored in this evidence packet.

Computed examples: single 8 slots / 48 frames / 48 layers; multipart 8/48/96;
mixed 8/48/56; named version-1 single-layer template 8/48/48; missing topology
8/48/unknown, zero resolved layers, PROVISIONAL. Orc full inheritance computes
40 slots / 512 frames / 1776 visible layers. Novice body/head are 208 slots /
912 frames / 912 visible layers across two distinct resources. Orc retains
57 stored identities, 55 referenced and unused 36/39; Novice body retains
110 referenced identities / 108 decoded contents. Ordered inherited raw records,
source ordinals, anchors, events and delay remain reference observations.

Missing declarations never default. Missing inherited sources retain both the
source-unavailable cause and UNDERSPECIFIED_LAYER_TOPOLOGY; incorrect hashes,
versions, parts, slots and frame counts fail at precise input paths. Unknown
semantics retain explicit numeric source slots without claiming runtime mappings.
Only immutable inventories are reference authorities; reference cycles cannot
be expressed by the closed contract. No artwork is assigned or approved.

## Preservation and limits

The accepted RSF-7 implementation-manifest was fully verified before editing.
The earlier 122-file baseline was also verified except the already accepted
RSF-7 replacements. This assignment retains a 143-file baseline manifest/archive
(the accepted source union and RSF-7 technical evidence), not a Git commit.
Git HEAD remains f1bb19bb130beea8b89cf6c029209e93fb241d5a. Work remains untracked;
local AI configuration is excluded. No commit, push, reset or cleanup occurred.
Baseline archive SHA256: de960b8fa8482ec22e5938ebb5183dc5a448aa555b7afeffc66bcddc8a71c433.

Python 3.12/3.13 NOT_RUN (unavailable); no cross-platform result claimed.
Full native playback NOT_RUN for this task, as topology resolution does not
change the native path. Previously accepted M0-S PASS, M0-I PASS, M0-N PASS /
M0_VERIFIED remain applicable to their original artifact/configuration scope.
RSF-8 is a structural task, not overall M1 acceptance. RSF-9 is not started.
Independent QA is recorded separately in QA_REVIEW.md when the reviewer returns the final verdict.

## Final implementation identities

- implementation-manifest.json: f9a08a6bd65e637044af2f3b0f44576b42861c4f3ac2bb9c245d0a19e00fc3dc
- examples.json: 65f37331f83ddc840fcb26c94072d80831c209d90093784c70e4c997387e35f1
- installed wheel: 050b29bf6dc8629c5c24a3ecc3114cb8f5e0be23e8c2dfcb432ec497b619680d
- source distribution: 91caa3744b92045940ebacb4322b10594fcb9da3bbd058257437c35731049589

A self-audit before final review corrected empty action-part/view accounting:
unknown dimensions now retain nullable exact counts and an explicit unexpanded
declaration count. Targeted, public, private, schema and installed-distribution
checks were rerun after the correction. The readable checklist also exposes role,
authority/source and source ordinal. Both updates are in the final manifest.
Only four previously accepted files changed; every other baseline entry remains
byte-identical. New resolver, tests and documentation are separate additions.
No local baseline commit was created; read-only Git metadata and existing
untracked accepted-source state are preserved using the verified archive.

## Tracker closure

Independent QA_PASS recorded; RSF-8 Accepted (`done`), five of five acceptance
criteria checked. Fresh task and comment read-back confirm the final identities
and verdict. kaneo-readback.json records the exact task, QA comment and next-task
relations; pending operations are empty. RSF-9 [M1] Artwork ledger and explicit
transform-reuse graph (bbiahdelxdqg6o5aupyfj699) remains Backlog (`to-do`); its
sole blocking dependency RSF-8 is now Accepted. It was not started or modified.
