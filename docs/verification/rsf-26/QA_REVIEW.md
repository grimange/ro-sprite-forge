# Independent RSF-26 QA

Reviewer: repository-configured `forge_qa_reviewer`, separate agent `/root/rsf24_qa`.
The agent name is reused from earlier reviews; this report concerns RSF-26 only.
Coordinator saved the reviewer's returned verdict below. Reviewer made no repository
edits, Kaneo writes, ownership changes or commits.

**QA_PASS — RSF-26 independent read-only verification passed.** No mandatory acceptance finding remains open.

I independently read the live task `tju1c32n1jrxitklr5hnj6la`, repository instructions, `forge-qa` skill, relevant M5 plan section, implementation diff, new tests and verification evidence. Kaneo was **QA Review / `in-review`**, assigned to Codex account `aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. I made no repository edits, Kaneo writes, ownership changes or commits.

| Live acceptance criterion | Verdict and independent evidence |
|---|---|
| Synthetic distributable monster with declared Walk requirements and explicit assignments/review | **PASS.** Tests declare all eight Walk views and inherited ordered layer topology before staging synthetic PNG artwork. Assignments identify exact occurrences, including deliberate reuse and an explicitly transformed source. Review records are simulated test inputs; this review grants no artistic approval. |
| Production compilation twice, deterministic hashes and independent ordered-layer/image/timing/anchor decoding | **PASS.** Reproduction ran two separate CLI processes with different working directories, hash seeds, invocation identifiers and source argument order. ACT, SPR and canonical manifests matched. Direct Rust decoding checked original and output resources. The comparator normalizes only selected references before comparing complete ACT structures. |
| Orc multilayer reconstruction and bounded Novice preservation | **PASS.** Independently ran all three new private tests. Novice preserved 455 unaffected visible occurrences, 103 untouched slots and separate head resources. Orc preserved 1,775 unaffected visible occurrences and all 112 twelve-layer Death frames. Explicit serializer reconstruction was tested separately from byte-preserving no-op serialization. |
| Durable requirements, assignment, composition, output, coverage and oracle evidence | **PASS.** Independent reproduction matched golden canonical build, compilation, effective mapping and private regression evidence. All 24 manifest-listed file hashes matched; all 90 baseline source/test/schema/Rust hashes remained unchanged. |
| Smaller scopes remain diagnostic; structural/oracle success grants no native acceptance | **PASS.** Bounded output remains explicitly diagnostic with production authorization false. Current-authority, approval, stale-input and cache checks remain enforced. Native Korangar status remains **UNVERIFIED**. |

The following commands were independently executed from the repository root:

| Command | Exit | Result |
|---|---:|---|
| `.venv/bin/python -m unittest discover -s tests -p test_walk_compilation.py -v` | 0 | 7 PASS |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p test_walk_compilation_fixtures.py -v` | 0 | 3 PASS |
| `.venv/bin/python -m unittest discover -s tests -q` | 0 | 452 PASS |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 0 | 41 discovered: 40 PASS, 1 existing native-report SKIP |
| `.venv/bin/python tools/rust-oracle/test_parity.py` | 0 | 11 PASS |
| `.venv/bin/python docs/verification/rsf-26/reproduce.py --output-dir /tmp/rsf26-independent-qa` | 0 | Two clean CLI builds and both private regressions passed |
| All ten `scripts/check_*schema*.py` checkers, invoked separately through a Python subprocess loop | 0 each | All accepted valid examples and rejected required invalid examples |

Additional independent assertions verified the exact synthetic target set `{(8,0,0), (8,2,2), (8,3,0)}`, three targeted occurrences, 51 unaffected visible occurrences and six hidden occurrences. Unaffected pixel identities and dimensions matched. Comparator sensitivity tests reject wrong output pixels, metadata drift and layer-order drift. Negative tests cover missing or corrupted staged sources, stale revisions, invalid occurrences/policies, revoked approval and corrupted cache entries, while preserving original resources and previously published history.

Independent output hashes matched sealed evidence:

- ACT: `43fffe83c1333772126a51e171a5d33d3b03ab1706f670f869099b1633b7617b`
- SPR: `0d49b375c22b5cd738c8a448d564409e4bfdbf90a1a6593a62ec4db3756a6a81`
- Canonical build JSON: `3a7832608569ed9248bf42e1d3f0274ba0548937c76897e3450918aa219d1bd1`
- Compilation JSON: `456fc60cb1fde32c618412517717b757d5b3f0b0ed02b79ee661850c1c1e8ba8`
- Effective mapping JSON: `8f3685df84d47bb713de0469be6365fb46eef85a89e49df8250eda83de89535a`

An initial whole-snapshot comparison exited 1 because ephemeral project creation/update timestamps—and the project snapshot hash containing them—differed. Investigation isolated those differences; semantic requirements, assignments, reviews and coverage matched, and canonical build evidence matched byte-for-byte. This is expected behavior, with timestamps excluded from canonical binary identity.

Verification used CPython **3.14.4**. Python 3.12/3.13 were unavailable and are **NOT_RUN**. Installed-distribution results were inspected, not independently rerun: coordinator evidence records exit 0, 443 PASS and nine optional skips across 452 discovered tests. Browser verification is **NOT_RUN** because this change adds no UI controls. The skipped private native-report crosscheck is not native success; actual Korangar loading/rendering remains **UNVERIFIED**.

Scope consists of the two new Walk test modules and RSF-26 evidence; existing production implementation remains unchanged. Verified implementation-manifest SHA-256: `9abb48737184ef3cbaefd468dd143f6eb8aafb36b8b7242903ca1fa8238ffc47`.

**M5-S: PASS for this bounded slice. M5-I: PASS within the Rust oracle's supported contract. M5-N: UNVERIFIED. M5 remains open.** RSF-26 is technically eligible for acceptance. The next action is for the coordinator to record this independent verdict, synchronize acceptance and read back final Kaneo status and ownership.
