# RSF-12 verification

Implementation: deterministic timeline and source-bound animation inspection, reusing the
accepted compositor. Scope is live task RSF-12 `[M2] Profile timing, registration and
body/head synchronization` (`ib2tllmtwl17psayj009pem7`). Independent QA_PASS was obtained for the final snapshot; see QA_REVIEW.md.
Codex is the verified implementer/assignee (`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`).
Ready → In Progress and assignee were read back through authenticated kaneo-local MCP.

## Identity and preservation

Plan SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.
Git HEAD: `472b1d3f9e29630b505fc2b3b7315f6b4e00beba`. No commit or push was made;
project files remain untracked. Read-only Git/AI metadata was not changed.
All six accepted RSF-11 manifest entries matched before implementation. The original
RSF-11 archive and manifest remain intact (manifest SHA-256
`35908b0a8d654ef677179ef0c20c71c33b02d19000b7b2e67b36e2a5b8104e73`).
The historical RSF-11 QA note records a different whole-manifest digest (`f5bc4b…`);
the actual file hash above is used here. All six per-file entries match the preserved
archive exactly; no source-content mismatch was found. The historical record is unchanged.
`accepted-preview.diff` compares changed accepted source against that archive.
`implementation-manifest.json` and `implementation-source.tar.gz` pin the new snapshot.
Final implementation manifest SHA-256:
`e29850704258af8abeba319f175ecdf31cf42a7a336cbc83ddb15e206b9de9ea`.
Source archive SHA-256:
`c62ab7f524c09077c978e0438621a5b7546b4cd09bef97345ccfa66201057765`.
Archives contain source only; private resources and rendered private images are excluded.

## Behavior and source evidence

See `docs/architecture/RSF12_ANIMATION.md` for API/CLI, exact source-file hashes,
coordinate conventions, timing arithmetic, bounds and limitations. Renderer semantics
are 1.1.0 (corrected exactly-one-child-anchor rule); timing/geometry semantics are 1.0.0.
The separate packaged closed contracts are timeline-selection/v1 and animation-inspection/v1.
Source ACT/SPR hashes, raw delays, profile identity, selected numeric slot/motion and
computed results remain separate. No coverage/review ledger is changed.

Pinned Korangar revision `3f3d88a583203f09d079712f43343c1041258ffd` was inspected
through immutable Git objects. The six new private tests compare **all 160 archived native
cases / 1,664 frame selections**, exact slots, delays and fallback states with the accepted
RSF-6 report. This is comparison with previous native evidence, not a fresh native run.
They also check player body/head separation/anchors, Walk and terminal sequences,
Orc death frame 21's twelve ordered layers, original hashes and repeated render/report bytes.

At movement speed 150, the actual Novice Walk delay 3 yields 60 ms and sequence
`0,1,2,3,4,5,6,7,0,1`. Orc Walk delay 2 yields 40 ms and `0,1,2,3,4,5,0,1`.
Novice Attack requires explicit duration and holds frame 4; Orc Die holds frame 21.
An initial new test assumed an 80 ms Novice interval; checking source delay established
60 ms and the test input was corrected. Production timing was not changed to match the test.

## Executed verification

Environment: Linux x86_64; Python **3.14.4**, Pillow **12.1.1**, jsonschema **4.19.2**.
Python 3.12/3.13 unavailable: NOT_RUN. No untested-platform reproducibility is claimed.
All commands below exited **0** on the final implementation snapshot:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests:tests/private_fixture_hooks .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_animation_schema.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_contract_schemas.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_ledger_schema.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python scripts/check_coverage_schema.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14
```

- Public: **229 PASS** (192 accepted + 37 new); public-tests.log.
- Private: **28 PASS**, no skips (22 accepted + 6 new); private-tests.log.
- Animation schemas: 2 schemas, 14 valid / 6 deliberately invalid cases PASS.
- Actor/runtime/target: 3 schemas, 13 valid / 55 invalid PASS.
- Ledger: 1 schema, 4 valid / 8 invalid PASS. Coverage: 1 schema, 2 valid / 8 invalid PASS.
- Installed distribution: **229 tests, OK, 1 optional jsonschema test skipped** in clean
  wheel environment; separate schema validators above ran with jsonschema installed.
  Repeated wheel identity and sdist rebuilt wheel agree; stdlib core runs without Pillow
  or Rust. Distribution log records build/install commands and exit statuses.
- Distribution SHA-256: wheel
  `9fc2a08ec15ed4c176b26d611c4c45062278d6c9b5dda7e9d19cd00470f48239`, sdist
  `741d9f0c4d278f8e233adc5212f354df8ccbd8995fe831e26ef01a1b98f92828`.

Synthetic tests independently assert arithmetic and half-open geometry; they include f32
boundaries, manual wrapping vs timed playback, external durations, view-zero completion,
unknown timing, no fallback, alpha bounds, even centers, mirrored/scaled/rotated extents,
clipping, empty/transparent frames, anchor rules, invalid inputs, bounded allocation,
canonical schemas, source immutability, no-overwrite and publication rollback.
`examples.json` records real computed synthetic/private report and PNG hashes, bounds,
Walk sequences and repeat equality. `synthetic-inspection.json` is a public example;
private PNGs are not retained in the evidence directory. Its file SHA-256 is
`96e23d05de5ec32921d778b7fed3d139db8a93d4ac7ba0ef5b871e92143bdc36`.
The report's embedded canonical identity excludes its own digest field and is distinct
from the full file hash.

## Independent correction loop

The separate read-only forge_qa_reviewer initially reported QA_FAIL for four reproduced
API/geometry defects. The implementer corrected each and added regression coverage:

1. Returned anchors/events/selection shared mutable state. Reports now detach these
   values from decoded snapshots and caller-owned selections.
2. Re-hashed selections could carry inconsistent derived timing/action metadata.
   Selection use now reconstructs and compares the complete canonical record.
3. Auto-fit used fixed +/-1,000,000 extrema, rejecting valid larger signed offsets.
   Bounds now start with infinities and follow actual image extents; +/-2,000,000 is tested.
4. Huge integer timing inputs could escape as OverflowError. Numeric range guards now
   reject invalid multipliers and scaled ticks before conversion; tests include speed
   10**1000 and elapsed=10/speed=10**308. The latter was caught on the first correction
   retest and corrected in the final snapshot.

Public/private/distribution commands above were rerun after the final correction.
Independent retest of the pinned final snapshot returned QA_PASS. The reviewer independently
ran 229 public tests, 28 private tests, installed-distribution checks and all schema validators,
and retested all four direct reproductions. All four live acceptance criteria passed.
See QA_REVIEW.md for the exact reviewer identity, commands, corrections and limits.

## Gate scope / exclusions

M0-S PASS, M0-I PASS, M0-N PASS remain the previously accepted results; no new native
execution or Rust decoder change is claimed. Geometry is verified only for the declared
CPU rasterizer. Overall preview fidelity remains PARTIAL; native WBOIT, native action-wide
billboard registration and cross-GPU pixels remain UNVERIFIED. Raw zero-clip motion
compaction parity is explicitly UNVERIFIED. Timing without required external context stays
UNVERIFIED; an operator-supplied interval is labeled DIAGNOSTIC. No artistic approval.
Contact sheets, sequence exports and candidate comparison remain RSF-13. M2 is not complete.

## Final Kaneo read-back

RSF-12 `ib2tllmtwl17psayj009pem7` is Accepted (`done`), assigned to Codex
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. All four live checklist items are checked.
Independent QA_PASS and source identities were posted in final comment
`ihrqys0kmzuofh3i2bb5km6b`, then task, assignee, criteria and comments were read back.
No tracker writes remain pending. Machine-readable summary: kaneo-readback.json.
Transitions: Backlog → Ready → In Progress → QA Review → FAILED → In Progress →
QA Review → Accepted; Codex ownership was preserved through review/correction.

Next is RSF-13 `[M2] Reference comparison and exported preview diagnostics`,
`sr7zifcthz9m09btrmjlaosv`, Backlog/unassigned, blocked only by RSF-12 before acceptance.
RSF-13 is not started. RSF-14 `[M2] Independent preview parity and fidelity evidence`
also remains Backlog. M2 is incomplete; RSF-11 and RSF-12 are accepted.
