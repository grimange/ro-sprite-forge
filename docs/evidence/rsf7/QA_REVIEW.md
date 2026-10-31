# RSF-7 independent review — QA_PASS

Reviewer: repository-configured `forge_qa_reviewer`, separate context `/root/rsf7_independent_qa`. The reviewer made no implementation, evidence, Git or Kaneo changes. The coordinator records the returned verdict here.

> QA_PASS — RSF-7 corrected implementation independently verified.

The reviewer inspected AGENTS.md, installed QA skill and reviewer configuration, relevant plan sections, live task criteria, complete accepted baseline, implementation manifest, schemas, code, tests and evidence. All four live RSF-7 acceptance criteria are supported. No implementation defect remains open.

## Findings and independently verified corrections

| Finding | Root cause and implementer correction | Independent retest |
| --- | --- | --- |
| Schema accepted trailing-LF identifier | `$` permits a position before a final LF; all identifier/hash/version regexes now use true end matching | External Draft 2020-12 validator rejects at `id`; twelve new trailing-LF negatives PASS |
| Contradictory/undefined timing actions | Missing cross-field reference checks; loader now validates known action identities and disjoint loop/nonloop lists | `Walk` conflict rejects `INVALID_INPUT /timing/nonlooping/5`; undefined name rejects `/timing/looping/2` |
| Malformed sealed inventory raised raw `KeyError` | Digest checking did not establish structural prerequisites; bounded checks now validate the fields consumed by inheritance | Missing namespace rejects `INVALID_INPUT /inventories/0/namespace`; eight malformed-observation variants PASS |

The v1→v2 exporter narrows global loop/nonloop timing name lists to actions declared by that category. Original M0 profile bytes, evidence and hashes remain unchanged. Other descriptive timing fields remain intact. No runtime mappings were invented to resolve the validation conflict.

## Independent commands and observations

CPython 3.14.4, Linux. Every command exited **0**.

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | 94 public tests PASS, including 25 contract tests |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 12 private tests PASS, no skips |
| `.venv/bin/python scripts/check_contract_schemas.py` | 3 schemas, 12 valid and 48 invalid cases PASS; jsonschema 4.19.2 |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; installed 94 tests; repeated wheel bytes identical |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/test_parity.py` | 11 tests PASS |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/private_parity.py` | All three audited pairs AGREEMENT, no mismatches |
| `PYTHONPATH=src .venv/bin/python tools/korangar-native/test_verifier.py` | 9 verifier unit tests PASS |

Private tests preserve separate Novice body/head resource identities and Orc Skeleton's 512 motions, 1,776 visible layers, 55/57 referenced/stored images and unused indices 36/39. Distribution isolation excludes private artwork and runtime Rust dependency.

The reviewer verified every final implementation-manifest entry, independently recomputed all twelve recorded contract identities, and verified the complete 122-file baseline archive. Of those baseline files, 121 remain unchanged; only `pyproject.toml` changes for schema packaging. No commit or push occurred.

## Final reviewed identities

- implementation-manifest.json: `9f133c72d3b63268d3c35eeb887642dfcc1f9e8bed4260180b8bb9c154994057`
- contracts.py: `7e2153a8192fe50b9eb52da1c9aeff742a5019e6d30774d11b9923df8552a064`
- contract-identities.json: `5b7a63985e4fe65d1bbd5d3a92b6481304d4a814f7f9c65499fecacaf31790d4`
- sdist: `ae8867394d3d63becb8341a5afad06825aa740d1420033890848d4c61f3237cd`
- wheel: `35c75689e11e18d5cbfb21244274b4f05a9b5a51001062bc43de3f6ab4d48aec`

## Acceptance and limits

Verified: actor/category/job/visual identity separation, unknown/custom mappings, Player-only relationships, explicit/inherited topology, underspecified diagnostics, scoped/full intent, revision/hash reference boundaries, deterministic outputs, inventory immutability and M0 regression compatibility. Artwork assignments remain a future separate authority; contracts grant no new visual/native approval.

Python 3.12/3.13 are NOT_RUN (unavailable). New native playback and cross-platform rendering were NOT_RUN. Existing operator-accepted M0-S PASS, M0-I PASS, M0-N PASS and M0_VERIFIED remain applicable to their original scope. The reviewer independently read RSF-6 Accepted with five checked criteria and the operator decision. RSF-7 was QA Review during review. The coordinator must record this QA_PASS, final counts/hashes, check supported criteria and verify Accepted read-back. Earlier handoff snapshots retain pre-fix counts; final `kaneo-readback.json` records the accepted current evidence.
