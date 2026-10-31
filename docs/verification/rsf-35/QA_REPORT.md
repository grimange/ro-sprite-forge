# Independent QA — RSF-35

**QA_PASS**, reported by the configured `forge_qa_reviewer` context
`/root/rsf35_qa`. This durable coordinator transcription preserves the reviewer's
verdict, observations, executions and limits. Original independent logs, probe and
two reproduction trees are copied without alteration into `independent-qa/`.

The reviewer independently read live RSF-35 in QA Review under Codex account
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`, all four acceptance criteria, repository QA
instructions, plan §6/M7, bounded diff/source, schemas, evidence and M7 packet.
The reviewer made no implementation edits, tracker writes, ownership changes,
commits or artistic approval decisions. No reproducible mandatory defects were
found; no implementation correction/retest cycle was required.

The versioned offline definitions reuse existing target, requirements, assignment,
coverage, compositor, timeline and persistence systems. Four-frame Wave displays
known red/green/blue/yellow artwork with explicit 80 ms diagnostic intervals.
Walk runtime mapping is unchanged. Wave/Guard/Dodge acquire no runtime slot or
native authority. Collisions, arbitrary slots, fake native declarations and
unsupported requests fail instead of becoming fallback acceptance.

Guard/Dodge explicitly inherit diagnostic storage slot 8. This is distinct from
runtime mapping, which remains UNSUPPORTED; native verification remains UNVERIFIED.
The output stays diagnostic. The reviewer's production fixture attempts fail with
`PRODUCTION_EXPORT_NOT_READY`; independent source inspection also confirms the
selected-offline-action production guard. Source/timing/topology changes stale
dependent reviews, preserving unrelated approvals and historical decisions.
Existing registry canonical identities remain compatible, and offline references
remain bound to profile/target identity. No preview or assignment creates approval.

The independent probe decoded original/output binaries and resolved every layer
against the actual SPR pool, separately from compiler-reported PASS fields.

| Check, for each Guard/Dodge build | Independently observed result |
|---|---|
| Original/output ACT slots | 40 / 40 |
| Compared layer occurrences | 49 |
| Changed occurrence | Exactly slot 8, frame 0, layer 0 |
| Unaffected occurrences | 48; identical effective dimensions and pixels |
| Replacement | 4×4, exact RGBA `(12,34,56,255)` |
| Frame/layer metadata | Equal outside authorized image reference |
| Reserved header, events, delays, bounds, anchors | Preserved |
| Original indexed RLE and palette | Preserved |
| Staged source hashes | Unchanged |
| Direct independent Rust comparison | AGREEMENT, zero mismatches |

A fresh, independently assigned red-back/blue-front two-layer preview produced
exactly 16 blue pixels, confirming expected ordered composition.

| Independently executed command | Exit | Result |
|---|---:|---|
| `PYTHONPATH=src:tests .venv/bin/python -m unittest test_custom_actions -v` | 0 | 18 PASS |
| `PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` | 0 | 636 PASS |
| `PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | 0 | 52 run, 51 PASS, one documented legacy native-report skip |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tools/rust-oracle -p 'test_*.py' -v` | 0 | 11 PASS |
| Each of 13 `scripts/check*schema*.py`, individually using `.venv/bin/python` | 0 each | 13 PASS; exact argv in independent schema log |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /home/ra/Documents/ro-sprite-forge/.venv/bin/python` | 0 | 636 run, 624 PASS, 12 optional skips |
| `PYTHONPATH=src:tests .venv/bin/python docs/verification/rsf-35/reproduce.py /tmp/rsf35-qa-repro` | 0 | PASS |
| `PYTHONPATH=src:tests PYTHONHASHSEED=97 .venv/bin/python docs/verification/rsf-35/reproduce.py /tmp/rsf35-qa-repro-repeat` | 0 | PASS |
| `PYTHONPATH=src:tests .venv/bin/python /tmp/rsf35-qa-probe.py` | 0 | Pixel/preservation/Rust/production/repeat probes PASS |

The 12 installed-distribution skips are four optional `jsonschema` checks and
eight repository Rust-executable cases, not twelve Rust skips. Wheel reproducibility
and private-resource exclusion passed. Python 3.14.4 was exercised; unavailable
3.12/3.13 are NOT_RUN. Browser/native GPU runs are NOT_RUN because no controls or
runtime implementation changed and no new native claim is made.

All 15 reproduced files were byte-identical across output directories and hash
seed 97. Both independent `artifacts.json` files have SHA-256
`f8b3f8223597542669b99be4735dc147ce880d9e2d7d41c536596b6a3034c6cb`.

Independently confirmed compiled ACT SHA-256:
`b37cd2da8f93246f4c3244aa19305688163e49d51c68559fc54ff4b10905056b`.
Compiled SPR SHA-256:
`cf90f1d8b4eb51ce47fde9375ef8aab18e5d8361c929dbd5557c9674153c68cd`.
Guard canonical build:
`e0a082cdadbad751065bbbb61d17f92c80a0d310a76cc6377194f7cd81c772ca`.
Dodge canonical build:
`feef0286e39eecf9e0061d49053087eafd120028531a6f8ec3a88ede19ff8e65`.
All 12 implementation hashes match the handoff manifest. Preservation comparison
confirmed 137 accepted baseline files outside declared changes byte-unchanged.

The durable probe is `independent-qa/rsf35-qa-probe.py`, SHA-256
`1fa2a8986627a42c2e8ab76b2981e9dbbcc67d329883bdf35e534399d1e0a009`.
Its original output is `independent-qa/rsf35-qa-probe-durable.log`. The reviewer
corrected a field typo while reconstructing this reviewer script before its
successful execution; this was not a product defect. All original logs and their
hashes are retained in `independent-qa/evidence-hashes.json`.

The reviewer independently confirmed RSF-32/33/34 Accepted with checked criteria.
The M7 packet accurately covers the four authoritative requirements. Genetic body
and Dragon Knight shield are distinct job-reference profiles; no Dragon Knight
body is established. The shield pairing retains its actual Novice parent/template
limitation. M7 becomes eligible for the existing FULLY_ACCEPTED verdict only after
coordinator RSF-35 acceptance and final read-back.

Final reviewer gate: **RSF-35 QA_PASS**. Structural/Rust and existing bounded M5
native evidence remain preserved; new custom-action native invocation remains
UNVERIFIED, with no custom gameplay dispatch or artistic approval implied. At the
reviewer's final observation Kaneo remained QA Review / Codex. Evidence preservation,
supported checklist updates and acceptance synchronization are coordinator actions.
No subsequent task was started by the reviewer.
