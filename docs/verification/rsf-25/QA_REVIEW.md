# Independent final QA — QA_PASS

Reviewer: repository-configured `forge_qa_reviewer`, separate verification context
`/root/rsf24_qa`. Reviewer made no file edits, tracker writes or ownership changes.
All five live RSF-25 criteria PASS within the documented supported compilation scope.
No mandatory finding remains open. Initial QA_FAIL and root cause: QA_INITIAL.md.

## Independent correction verification

The reviewer independently reconstructed the original fully covered per_frame target,
using ordered roles from actual visible clips and approved assignments for every required
occurrence. Both original ACT and changed ACT (Walk x -3→97, delay 6→12) now reject
UNBOUND_PRODUCTION_COMPOSITION. Neither production attempt creates a final output.
Both production plans have ready_to_compile=false and production_authorized=false.
Both explicit-topology bounded variants publish PARTIAL_DIAGNOSTIC.txt and retain
production authorization false. Valid resource-bound inherited full-profile production
still compiles and publishes atomically. These probes exited 0 on corrected code.

## Five live criteria

1. PASS: independent focused clean CLI subprocess tests change paths, names, hash seeds,
   filesystem insertion order and time environment; ACT/SPR/canonical build bytes match.
2. PASS: reviewed ordering, preserved semantic layers, float32 encodings, encoder/palette
   policies, Pillow pin and tool/source identities; focused tests pass.
3. PASS: canonical identity excludes physical paths, invocation IDs, output names and
   native/oracle evidence; outer invocation manifests may differ.
4. PASS after correction: missing/invalid/stale/unapproved/incomplete and unbound
   production compositions reject; scoped/explicit diagnostic output remains partial.
5. PASS after correction: source/contract/policy/tool/prebuild composition/output hashes,
   immutable originals and atomic cache/publication pass; approval bypass is closed.

## Independently executed commands and scope

All commands exit 0:

- `.venv/bin/python -m unittest discover -s tests -p test_canonical_builds.py -v`:
  final corrected code, 14 PASS.
- `.venv/bin/python -m unittest discover -s tests -v`: pre-correction baseline, 444 PASS.
- `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v`:
  38 discovered, 37 PASS and one existing native-report skip.
- `.venv/bin/python tools/rust-oracle/test_parity.py`: 11 PASS.
- All ten `scripts/check_*schema*.py` checkers separately: PASS.
- Independent inline reproduction/publication probe: PASS on corrected code.
- SHA-256 validation of every final implementation-manifest entry: PASS.

Independent private checks include Novice body/head preservation and Orc multilayer
compilation with Rust. Public/private regressions verify no-op bytes, raw indexed RLE,
palettes, metadata, ordered layers and effective image references. Atomic/cache tests
cover interruption, process exit, concurrent publication, corrupt cache/pairs, safe names,
symlinks and overwrites.

Reviewer separately inspected sealed final coordinator results: public445 PASS;
private37 PASS/1 existing skip; installed445 discovered/441 PASS/4 optional skips,
DISTRIBUTION_CHECK_PASS. Final broad/distribution runs were executed by implementer;
reviewer's final independent reruns covered correction/probe/focused14.

Final reviewed implementation-manifest SHA256:
`0bb46f2dbffed272c1ba7ed62469bca8dd2ef8c231d17798c6a6ad59ef00e77f`.
All listed source/preservation/evidence entries matched. Canonical build-manifest SHA256:
`226129845c393d8899ea031c9e08f9e6b31efb534fb8fbf7a05f7fb7d2b0ebce`.

CPython3.14.4 used. Python3.12/3.13 NOT_RUN unavailable. Browser NOT_RUN no UI controls
changed. Installed distribution evidence reviewed, not independently rerun. Native
Korangar UNVERIFIED; no subjective artwork/native approval. M5-S PASS for bounded
structural/build task; M5-I PASS within supported oracle scope; M5-N UNVERIFIED.

Coordinator must synchronize QA_PASS and acceptance with live Kaneo read-back. This
separate report supplements the frozen reviewed implementation-manifest; it does not
modify reviewed source or its hashes.
