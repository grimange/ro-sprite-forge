# RSF-25 implementation verification

Implementer: Codex (`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`). Task: `udjjt7jp22k3owbo05s8mnf8`.
RSF-24 dependency was read back Accepted before implementation. Ownership and Ready → In Progress were read back.

## Final commands and observed results

All commands ran from the repository root with CPython 3.14.4. Exit status 0 for each:

| Command | Result | Durable evidence |
| --- | --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p test_canonical_builds.py -v` | 14 PASS | focused.log |
| `.venv/bin/python -m unittest discover -s tests -v` | 445 PASS | public.log |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 38 discovered, 37 PASS, 1 SKIP | private.log |
| `.venv/bin/python tools/rust-oracle/test_parity.py` | 11 PASS | rust-parity.log |
| `.venv/bin/python scripts/check_*schema*.py` (each of 10 scripts separately, exact argv in evidence) | 10 checkers PASS | schemas.json |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | DISTRIBUTION_CHECK_PASS; installed suite 445 discovered, 441 PASS, 4 SKIP; repeat wheels and asset exclusions PASS | distribution.log |
| `.venv/bin/python docs/verification/rsf-25/reproduce.py` | 2 clean subprocess builds: ACT, SPR and canonical build manifest byte equality; invocation manifests differ as expected | clean-builds.log, environment.json, golden-build.json, golden-compilation.json |

Private skip: existing RSF-6 native-report check requires unavailable `/tmp/rsf6-native-run-final-1`. Installed distribution skips three optional jsonschema checks and the repository-only Rust matrix. Those checks pass in the repository environment. Rust verification of generated outputs also passes in focused/reproduction checks. No proprietary image/binary is included in this packet.

Python 3.12 and 3.13: NOT_RUN, executables unavailable. Chromium: NOT_RUN, no operator controls/static/service changes. Existing HTTP journeys are in the public and installed suites. Native Korangar: NOT_RUN / UNVERIFIED. Local HTTP test execution required the sandbox's approved network exception; an initial unprivileged compiler-suite invocation had a socket permission failure, then the final full suite passed with the exception.

## Scope and regression evidence

See CONTRACT.md for canonical ordering, numeric encoding, toolchain pins, build/evidence separation, approval/export gates and atomic publication. implementation.diff compares the five edited existing files with pre-edit snapshots and includes two new source/test files. This repository has an untracked baseline; no commit, reset, push or history change was performed.

The 14 focused tests cover independent CLI builds with changed paths/names/hash seeds/time environment; canonical order and float32 tie-to-even/signed zero; toolchain identity; full versus scoped coverage; valid production and missing/invalid/stale/unapproved failures; changed-one-source review invalidation; original-resource binding; corrupt cache and no cache bypass of checks; interrupted process publication; concurrent publication; CLI production atomic-directory requirement; corrupt/inconsistent pairs, reserved names, symlinks and existing outputs. Original/staged byte equality is checked on failure. Synthetic approval fixtures do not grant human artwork approval.

No production codec or Rust oracle was changed. Existing private Novice/body/head and Orc Skeleton compiler, multilayer metadata, raw RLE/palette/no-op and unaffected effective-image checks pass. M5-S PASS and M5-I PASS for this bounded scope; M5-N UNVERIFIED. M5 remains open.

Initial independent QA_FAIL and correction: see QA_INITIAL.md. Production now rejects explicit/per_frame/template role-only topology because its accepted review basis does not bind original registration/timing/anchors. Resource-bound inherited topology remains eligible. Independent retest pending; checklist remains unchecked until QA_PASS.
