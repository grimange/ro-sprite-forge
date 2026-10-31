# RSF-7 implementation verification

Task `RSF-7` / `rnecskanbq7j2i8m936ti62p`: versioned actor, target and runtime-profile contracts. Implementation complete; independent QA_PASS from the configured separate reviewer /root/rsf7_independent_qa.

## Scope and source identity

The bounded implementation adds `core/contracts.py`, three packaged JSON Schemas, public/private contract tests, the optional schema-check script and `docs/architecture/RSF7_CONTRACTS.md`. `implementation-manifest.json` pins these paths. `pyproject.toml` includes schemas as package data. Existing codecs, inventories, v1 runtime profiles, CLI commands, Rust oracle and native harness are unchanged.

`baseline-manifest.json` pins 122 accepted files after operator M0 closure. `baseline-source.tar.gz` preserves that complete selected snapshot. `baseline-diff.json` records actual Git HEAD, archive identity and the sole change to an existing baseline file (`pyproject.toml`). All 121 other baseline files remain byte-identical. No baseline or RSF-7 commit was created; no push or history rewrite occurred. Existing unrelated operator files remain untouched. Local AI configuration is excluded from the archive.

Plan v1.1 SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.

## Contract behavior

- Actor/v1 separates arbitrary gameplay job identity, visual body family, sex/body variant, costume, parts, action-profile identity and evidence-backed attachment compatibility.
- Runtime-profile/v2 pins source revision/evidence, semantic version, numeric groups/slots, ordered views, selection/timing rules, parts and relationships. Mapping and gameplay reachability have separate support states. NPC/monster profiles cannot inherit the Player body/head rule. Frozen v1 records are explicitly exported without rewriting old inventories or hashes.
- Target/v2 pins actor revision and runtime-profile version/hash. It declares required, optional and excluded actions, parts, views, frame counts, explicit/per-frame/inherited ordered topology, scoped/full intent and compatibility. Unknown custom IDs remain UNVERIFIED. Missing frame/topology data produces precise underspecified diagnostics; no artwork or one-layer default is invented.
- Closed bounded schemas and cross-record validation reject unsupported versions, conflicting references, invalid counts/slots, malformed declarations, bad revisions and digest mismatches. Returned contract snapshots are immutable; dictionary exports are independent copies. Revisions pin predecessors; supplying the previous record verifies continuity. Without that record, the predecessor is a declared hash link, not verified history.
- Artwork remains UNASSIGNED; native, visual and compatibility evidence remain independent. No assignment ledger, work-order expansion, reuse graph, UI, ingestion or compiler was added.

## Actual verification

Linux x86-64; CPython **3.14.4**. Commands below exited **0**. Python 3.12 and 3.13 are unavailable locally and were NOT_RUN.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p test_contracts.py -v` | 25 tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | 94 public tests PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 12 private tests PASS, no skips |
| `.venv/bin/python scripts/check_contract_schemas.py` | Draft 2020-12: 3 schemas, 12 valid records, 48 invalid shape cases; jsonschema 4.19.2 |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | offline distribution PASS; installed wheel runs 94 tests; repeated wheels byte-identical |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/test_parity.py` | 11 synthetic oracle tests PASS |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/private_parity.py` | all 3 audited pairs AGREEMENT; no mismatches; see `private-parity.json` |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tools/korangar-native -v` | 9 native-harness unit tests PASS; no new native playback run claimed |

The schemas are installed package data. JSON Schema tooling is an optional verification dependency; core loading remains standard-library-only. The installed-distribution checker verifies isolated imports, absence of private assets and Rust runtime dependency, standard-library core smoke behavior, CLI error contracts and all public tests.

Final independent distribution identities after QA corrections:

- sdist SHA-256 `ae8867394d3d63becb8341a5afad06825aa740d1420033890848d4c61f3237cd`
- wheel SHA-256 `35c75689e11e18d5cbfb21244274b4f05a9b5a51001062bc43de3f6ab4d48aec`

The reviewer independently built these artifacts and verified repeated wheel identity. Canonical contract outputs exclude runtime timestamps and paths. `contract-identities.json` records 12 payload and serialized identities across Player, NPC, monster and unverified categories; repeated loads/serialization are tested byte-for-byte. The manifest SHA-256 is `5b7a63985e4fe65d1bbd5d3a92b6481304d4a814f7f9c65499fecacaf31790d4`.

Private tests compute Novice body/head inventories separately (104 slots/456 motions each; 110 and 15 referenced identities) and Orc Skeleton inventory (40 slots, 512 motions, 1,776 visible layers, 55/57 referenced/stored, unused 36/39). Inherited contracts preserve those observations, hash-pinned source identities and inventory bytes. Original assets remain outside source/distributions and are accessible through existing private hooks. No proprietary artwork or captures were added.

## M0 closure and limits

Operator acceptance was recorded and RSF-6 read back **Accepted**, five criteria checked. See `../rsf6/OPERATOR_ACCEPTANCE.md` and `../rsf6/closure-readback.json`. Existing independently verified evidence remains applicable: **M0-S PASS; M0-I PASS; M0-N PASS; M0_VERIFIED**. Its tested pinned configuration and limitations remain unchanged. No additional native run was necessary for these declarations; new contracts do not themselves establish native compatibility, gameplay reachability or visual approval.

## QA corrections

The independent reviewer reproduced three defects: JSON Schema `$` accepted trailing-LF IDs; timing lists accepted overlapping/undefined action names; sealed malformed inventories could raise raw `KeyError`. The implementer corrected true-end regex matching, cross-field timing validation and bounded prerequisite observation validation. Regression tests cover timing conflicts and eight malformed observation variants; the optional schema checker adds twelve trailing-LF negatives. The explicit v1→v2 exporter narrows only loop/nonloop name lists to category-declared actions because legacy global timing names include NPC/monster fallback actions. Original M0 records remain untouched. Targeted 25 tests, full 94 public tests, 12 private tests and schema 3/12/48 checks pass after corrections. Independent retest confirms all three reproductions now reject with typed field diagnostics; fresh installed distribution runs 94 tests and passes. Final QA verdict is recorded separately.

## Independent QA

Separate `forge_qa_reviewer` context `/root/rsf7_independent_qa` returned **QA_PASS** after independent code/schema review, negative probes, full public/private/distribution checks and regression execution. All three reported defects were corrected by the implementer and independently retested. See `QA_REVIEW.md` for commands, exact findings, identities and limits. All four live acceptance criteria are supported; final tracker state is recorded in `kaneo-readback.json`.

## Final Kaneo synchronization

RSF-7 was read back **Accepted** (`done`), four checked criteria and zero unchecked criteria, after independent QA_PASS. QA evidence comment: `c5p6mc41its6tycw18oxzfb5`. Final snapshot: `kaneo-readback.json`. No tracker writes remain pending. RSF-8, `[M1] Explicit or inherited ordered layer-topology requirements`, remains **Backlog** (`to-do`); its only blocking predecessor RSF-7 is now completed. See `next-task-readback.json` and `next-task-relations.json`. RSF-8 was not modified or started.
