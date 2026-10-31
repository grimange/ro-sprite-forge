# Independent QA — RSF-8

**QA_PASS** — configured `forge_qa_reviewer`, separate review context
`/root/rsf8_independent_qa`. The reviewer did not edit source/evidence or Kaneo.
This record is the coordinator's transcription of the returned independent verdict.

Reviewed live five-criterion RSF-8 acceptance, relevant plan/instructions, source
baseline/archive, bounded diff, contracts/schema/resolver/CLI, tests and evidence.
Final implementation-manifest SHA256:
f9a08a6bd65e637044af2f3b0f44576b42861c4f3ac2bb9c245d0a19e00fc3dc.
All eight implementation entries match their hashes. The baseline archive and
143-file manifest match; only four accepted files changed. Plan SHA matches the
synchronized normative identity. Accepted codecs, inventories, profiles, Rust
oracle and native harness are unchanged.

## Independently executed checks

CPython 3.14.4, PYTHONDONTWRITEBYTECODE=1; all exit statuses 0.

| Command | Observed result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q` | 119 PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 14 PASS, no skips |
| `.venv/bin/python scripts/check_contract_schemas.py` | 3 schemas, 13 valid and 55 invalid cases PASS |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | Installed119 PASS, repeated wheel hashes equal, package isolation PASS |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/test_parity.py` | 11 PASS |
| `PYTHONPATH=src .venv/bin/python tools/rust-oracle/private_parity.py` | All3 audited pairs AGREEMENT; no mismatches |
| `PYTHONPATH=src .venv/bin/python tools/korangar-native/test_verifier.py` | 9 unit tests PASS |

The reviewer imported the example generator and called generate() twice without
writing evidence. Both results equal examples.json, SHA256
65f37331f83ddc840fcb26c94072d80831c209d90093784c70e4c997387e35f1.
Independently computed: single48/48, multipart48/96, mixed48/56, template48/48,
missing topology48/unknown, Novice body/head912/912, Orc512/1776.

## Findings and correction

No unresolved mandatory defect. During review the implementer corrected empty
parts/views accounting: a missing required action dimension no longer contributes
an exact zero layer total. The reviewer independently tested 48 known layers
plus an unexpanded required action: PROVISIONAL, exact slot/layer totals null,
missing declaration counted. Excessive layer workload fails with typed
ForgeError. All relevant regressions were repeated after the correction.

## Acceptance evidence

1. Exact ordered explicit/per-frame frame/layer lists, roles and applicable
   inherited source constraints are retained. Source anchors/events/transforms/
   timing are observations; no undeclared registration/reuse is invented.
2. Inheritance pins inventory/ACT/SPR identities, part, numeric slot/frame,
   original layer ordinal and completeness. Invalid hash/version/part/slot/count
   fails; unknown semantic mapping stays unknown. Named template version/hash/
   exact-scope confirmation is checked.
3. Missing count/topology retain precise diagnostics, unavailable reference
   retains both cause and missing-topology state; no default single layer.
4. Provisional requirements cannot be exact/COMPLETE_FOR_DECLARED_SCOPE or
   export-ready. Full-profile and scoped specification remain separate.
5. Correct distinct single/multipart/mixed work totals exist without artwork.
   Artwork UNASSIGNED, reuse UNDECLARED, visual/native UNVERIFIED, unique effort
   unknown until assignments.

Private ordered source-layer records match the inventories. Returned-data
mutation does not affect inputs. Novice body retains456 motions/110 referenced
identities/108 content classes, separate head. Orc retains512 motions/1776 visible
references/55 of57 images/unused36,39. Preservation tests retain original hashes.
Distribution excludes private hooks and ACT/SPR/GRF assets.

Python3.12/3.13, other platforms and full native playback NOT_RUN. Unit tests do
not create a new native gate. Existing M0-S/I/N PASS and M0_VERIFIED remain within
the original accepted scope. No artistic approval, artwork assignment, gameplay
reachability or overall M1 acceptance is issued.

Fresh reviewer MCP read-back confirmed RSF-8 QA Review with final manifest and
example hashes and RSF-7 Accepted. Coordinator owns the subsequent five-checkbox
completion, Accepted transition and final read-back in kaneo-readback.json.
