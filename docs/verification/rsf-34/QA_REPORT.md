# Independent RSF-34 QA

Verdict: **QA_PASS**. Reviewer: configured `forge_qa_reviewer`, separate agent
`/root/rsf34_qa`. The coordinator preserved this report and the reviewer's original
logs/probe after receiving the verdict. The reviewer made no repository edits,
Kaneo writes or ownership changes. No reproducible defect was found; no correction
or independent retest cycle was required.

The reviewer independently read the live task's four criteria, dependency and plan,
baseline comparisons and all six changed implementation/schema/test paths. RSF-33
was Accepted; RSF-34 was QA Review under Codex when reviewed. All four live mandatory
criteria passed within the documented bounded scope. Character, external gameplay
context, underlying body and appearance remain separate. Source-bound mappings,
partial coverage, attachment geometry/order, the approved-art adapter boundary,
retained-reference exclusions and RSF-18 scoped/aggregate invalidation were verified.

## Independent execution

Commands use `PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`. Every command below
exited 0. Original logs are preserved under `independent-qa/`; the reviewer initially
wrote them in `/tmp/rsf34-qa/`. Public/distribution commands used approved sandbox
escalation for the existing bounded loopback HTTP tests.

| Command | Actual result | Log |
|---|---|---|
| `.venv/bin/python -m unittest test_appearance test_profile_registry test_attachment_compatibility -v` | 79 PASS: 35 appearance, 25 registry, 19 attachment | `focused.log` |
| `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` | 618 PASS | `public.log` |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v` | 52 run; 51 PASS, one documented legacy native-report skip | `private.log` |
| `.venv/bin/python tools/rust-oracle/test_parity.py` | 11 PASS | `rust.log` |
| All 12 `scripts/check_*schema*.py` scripts | All PASS, each exit 0; exact individual argv/stdout retained | `schema-results.json` |
| `.venv/bin/python docs/verification/rsf-34/reproduce.py /tmp/rsf34-qa/synthetic` | Four representations; all generated artifacts byte-identical to retained synthetic evidence | `reproduce.log` |
| `.venv/bin/python /tmp/rsf34-qa/probes.py` | Fresh independently constructed semantic probes PASS | `probes.log` |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | 618 run; 606 PASS, 12 optional Rust-tool skips; DISTRIBUTION_CHECK_PASS | `distribution.log` |

The isolated distribution check independently passed repeated clean wheel identity,
installed execution, stdlib core import and private artifact exclusion.

## Fresh semantic probes

Preserved `independent-qa/probes.py` is the original reviewer-authored script. It uses
the reproduction directory `/tmp/rsf34-qa/synthetic` from the preceding command.
It separately verified Draft 2020-12 validation, exact frame-1 selection, and actual
half-alpha green over opaque red: pixel **(127, 128, 0, 255)**. External gameplay
context, requirements, registry and source bytes remained unchanged. An independently
hash/profile-rebound ACT with pool 7 was rejected with `ForgeError: Unknown sprite pool
7; expected 0 (indexed) or 1 (rgba)`. All six implementation hashes matched. Every
reproduced synthetic artifact matched retained evidence byte-for-byte.

Synthetic determinism SHA-256:
`68ae25c64b6a6894245d7bb3916777bbb856497a46481d12fc7d01327e856be9`.
Reviewer probe SHA-256:
`31afb28c322be293ce481a16eb3eb97152eba944da9a45cd72957e8933cbc296`.

## Private evidence and boundaries

Independent private execution includes three actual Rust source-pair comparisons,
decoded structure/pixel agreement and byte-exact ACT/SPR no-op preservation.
Genetic/Jack has 104 mapped slots and 456 frame correspondences. Genetic/shield has
96 supported slots; Pickup slots 24–31 remain incompatible (3 versus 2 frames).
Novice/Genetic visual-body selection preserves the separate head identity and blocks
unbound head composition. The existing shield pairing actually names
`novice-male-body-v1`; no enrolled hash-bound Dragon Knight body supports a broader
claim. Substituted parent bytes are rejected as `SOURCE_HASH_MISMATCH`.

Costume changes stale four dependent/aggregate reviews while preserving four
independent body/unrelated approvals and all history. No automatic approval occurs.

Python 3.14.4 was tested; 3.12/3.13 unavailable, NOT_RUN. The existing Rust executable
was used; Rust/Cargo rebuild NOT_RUN (tools unavailable on PATH). Browser NOT_RUN
because no operator controls changed. Native GPU NOT_RUN; new cosmetic compilation
and native status remain UNVERIFIED. Source-resource Rust parity does not prove
native cosmetic eligibility. QA_PASS grants no artistic approval or M7 closure.
