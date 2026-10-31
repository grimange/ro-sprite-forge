# RSF-35 implementation and verification

**RSF-35_IMPLEMENTED_AND_QA_PASSED.** Independent configured reviewer
`/root/rsf35_qa` returned QA_PASS with no product findings. Kaneo task
`ly1cfaohrp6e00qxg4g1tfcj`, implementer Codex
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. Verified transitions: Backlog → Ready →
In Progress → QA Review → Accepted. Final MCP read-back confirms `done`,
Codex ownership and all four criteria checked. QA comment ID:
`h9a1r6hnxbvbanzybxr34m73`. Final tracker evidence is retained in
`kaneo-final-readback.json`.

The optional target action contract `rsf.offline-action/v1` extends the existing
target, topology, assignment, coverage, preview and review systems. Existing
non-offline target and default registry canonical identities are preserved.
Offline action IDs cannot collide with native profile action IDs. Optional
`offline_actions` references extend `rsf.compatibility-registry/v1` compatibly.
See [USAGE.md](USAGE.md) for the supported Python API.

| Case | Authoring / preview | Runtime | Compilation | Native |
|---|---|---|---|---|
| Wave, four frames, view 0, body layer 0 | Four exact assigned colors, 80 ms explicit diagnostic loop | UNSUPPORTED, no slot | UNSUPPORTED for standalone topology | UNVERIFIED |
| Guard / Dodge with original inherited storage | Exact existing four-frame topology | UNSUPPORTED, no runtime slot | Bounded diagnostic replacement in declared storage slot 8 | UNVERIFIED |
| Existing monster Walk, view 0 | Existing requirements and preview unchanged | Source-backed slot 8 | Existing policy | Existing evidence only; no new native run |

Guard and Dodge each preserve the original 40-slot ACT inventory. Only the selected
first frame/layer changes effective pixels; all other occurrences and metadata are
compared after writing. Original source bytes remain unchanged. Repeat builds
produce identical ACT, SPR and canonical build manifest bytes. Different action
identities retain distinct canonical provenance even when resulting binaries match.

The synthetic original ACT hash is
`645b5fa1381b520d1740bfe5610dda73158e07344f45428f9399bb454addab4b`;
original SPR hash is
`670ac543acfa7323e2be20ec7cf093d78d4337d20186649256da3c30d92d213d`.
Both bounded cases produce ACT
`b37cd2da8f93246f4c3244aa19305688163e49d51c68559fc54ff4b10905056b`
and SPR
`cf90f1d8b4eb51ce47fde9375ef8aab18e5d8361c929dbd5557c9674153c68cd`.
Actual canonical build identities, output manifests and independent Rust report
identity are in [synthetic/compilations.json](synthetic/compilations.json).

Review regression uses explicit isolated synthetic decisions. Changing a custom
source stales that dependent decision; changing its timing/topology changes the
action basis. Unrelated Walk review remains applicable. No review is automatically
created or promoted into runtime evidence. Production export rejects offline
runtime authority even with assigned, reviewed diagnostic artwork. Missing source,
bad hash, stale revisions, invalid frame/layer/view, fake slot/native claims and
conflicting action identities are rejected with typed diagnostics.

Pinned Korangar source `3f3d88a583203f09d079712f43343c1041258ffd` defines
existing player/monster actions; Guard, Dodge and Wave have no dispatch mapping.
Unsupported action normalization to Idle is fallback, not exact support. No client,
server, ACT encoder, image-pool resolver or runtime dispatcher was changed.

Verification commands and logs are retained alongside this report. Focused tests:
18; public suite: 636; private suite: 52 run / 51 pass / one preexisting legacy
native-report skip; independent Rust parity: 11; schema scripts: 13. All completed
checks exit 0. Final installed-distribution verification ran 636 tests: 624 passed,
12 optional checks skipped (four JSON Schema dependency checks and eight Rust
executable checks). The source-environment schema and Rust checks passed separately.
The wheel was rebuilt twice byte-identically; package/private-artifact exclusions passed. The initial
distribution run exposed a test-only import path assumption in the hash-seed probe;
the probe now locates its copied test directory rather than assuming `tests/`.

Python 3.14.4, Pillow 12.1.1 and JSON Schema Draft 2020-12 are used. Python 3.12 and
3.13 are unavailable (NOT_RUN). Browser and native GPU runs are NOT_RUN because no
browser/runtime changes or new native claims are made. Existing M5 native evidence
remains bounded to its original tested resources. Public evidence contains only
synthetic PNGs and contract/hash records; proprietary resources remain excluded.

Exact changed implementation paths and baseline/current hashes:
[implementation-paths.json](implementation-paths.json). A bounded diff is retained
in `implementation.diff` because the repository's accepted source tree is untracked.
No commits, pushes, history rewrite or source cleanup were performed.

M7 is **FULLY_ACCEPTED** within the existing plan scope after independent QA
and final live RSF-32–35 Accepted read-back. The four tasks each have four checked
criteria. See [M7_GATE_PACKET.md](M7_GATE_PACKET.md). The
authoritative plan is §6/M7, SHA-256
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.


Actual self-verification commands (all exit 0):

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest test_custom_actions -v
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tools/rust-oracle -p 'test_*.py' -v
.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /home/ra/Documents/ro-sprite-forge/.venv/bin/python
PYTHONPATH=src:tests .venv/bin/python docs/verification/rsf-35/reproduce.py docs/verification/rsf-35/synthetic
```

Each of the 13 schema validators has its exact argv and exit status retained in
`schemas.log` and `commands.json`. Existing bounded loopback HTTP tests required
approved sandbox escalation for the public and installed-distribution runs.

Reproducible wheel SHA-256:
`3afb4bef662c8931f1c7d2731dc480d3e27b1f270b5d20f03a7cc5120cada15a`.
Source distribution SHA-256:
`33f3ce0b7fc2fed6b0a2332ccc0cebff07fcaaf7b2319a47f64c32a23f5233f7`.
The latter is a recorded artifact identity; repeated wheel identity is the measured
package reproducibility claim.

Preservation accounting: 146 baseline files, 137 byte-unchanged, nine intentionally
modified, zero missing or unexpectedly changed; three new implementation/test
files. The generated package source list is included among the changed paths.
No original binary codec or Rust decoder implementation was changed.


Independent reviewer executions reproduced all test counts above and additionally
compared all 49 layer occurrences in each Guard/Dodge case: one intended change,
48 unaffected, zero effective-image or metadata mismatches. Direct Rust comparisons
reported AGREEMENT with zero mismatches. A fresh two-layer preview confirmed
exact ordered pixels. All 15 independently reproduced files matched across different
paths and hash seed 97. See [QA_REPORT.md](QA_REPORT.md) and the original copied
`independent-qa/` logs/probe. No implementation correction/retest was required.

Final M7 verdict: FULLY_ACCEPTED for the four authoritative compatibility criteria;
RSF-32, RSF-33, RSF-34 and RSF-35 are individually Accepted. Existing M5 structural,
independent Rust and bounded native evidence retain their prior scopes. Custom
Wave/Guard/Dodge runtime mapping remains UNSUPPORTED and native UNVERIFIED.
No automatic visual approval, production authority or custom gameplay dispatch
is implied by milestone acceptance.

The live next task is RSF-36 — [M8] Portable packaging, CI and reproducible release
artifacts, ID `zhk7olqfex25j8tewzoragi0`; dependencies RSF-26/31/35 all Accepted.
It remains Backlog/unassigned and was not started. Recommended implementer: Codex
with High reasoning for release provenance/CI/version compatibility, Python/build
and JSON Schema tools, forge-kaneo/verification and a separate forge_qa_reviewer.
No publication or deployment follows from this recommendation.
