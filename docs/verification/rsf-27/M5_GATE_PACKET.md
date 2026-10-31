# M5 acceptance evaluation

Authority: implementation plan v1.1 §6/M5, SHA-256
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`;
live RSF-23–27 task criteria. Live accepted predecessors are preserved in
M5_LIVE_TASKS.json. The project has no separate live milestone object returned by its
task/project tools; the plan's five M5 acceptance bullets are the milestone authority.
The existing verification-report template's overall verdict vocabulary is
`FULLY_ACCEPTED / PARTIAL / FAILED / UNVERIFIED`; no new M5 gate token is introduced.

| Authoritative M5 requirement | Evidence and evaluated result |
|---|---|
| Declare topology before PNG assignment; composition-bound review; deterministic compile; independent decode; actual requested Walk/view/slot, reachable views exact | RSF-26 requirements/ledger/review snapshots and fresh RSF-27 walk_fixture reproduction; two CLI builds; Rust whole-pair comparison; native 176-case report, actual loaded hashes and captures. All eight Walk views resolve exactly. PASS within the declared diagnostic scope. |
| Two clean canonical builds match; changing one approved source invalidates affected scope | Accepted RSF-25 canonical-build and RSF-18 review invalidation contracts, accepted RSF-26 clean-build/gate regressions; fresh 452-test public suite and two clean RSF-27 CLI compilations preserve matching ACT/SPR/build manifests. PASS. |
| Bounded Novice replacement preserves unrelated slots and separate head resources | Accepted RSF-26 novice-regression.json and private replacement test; fresh 40 private passes verify replacement and other 103 slots/head isolation. RSF-27 additionally executes all eight original Novice native Walk views/body-head anchors. PASS; native modified-Novice playback is not claimed. |
| Orc multilayer package reconstruction preserves 12-layer Death and transformed placement | Accepted RSF-23–26 writer/whole-ACT comparison, fresh private fixture tests; RSF-27 native Orc Walk/Die all eight views, including slot-32 12-layer Death frames. Native preparation, selected layers, transforms and captures checked. PASS. |
| Invalid, underspecified or unapproved targets cannot be production; hashes recorded; asset-loaded insufficient | Accepted RSF-25 production binding correction; fresh gate/cache/public regressions and RSF-27 17 native/checker controls. Diagnostic bundle stays PARTIAL_DIAGNOSTIC, production false. Wrong pair can render yet fails canonical-pair identity checking. PASS. |

The RSF-27 native proof is fresh evidence for changed artifacts; RSF-6/M0-N is only its
verified corridor foundation. Fallback/modulo/direction-mask observations are negative
controls and never count as requested-action verification. No required codec/slot defect
was found. Final QA and Kaneo acceptance are recorded in QA_REVIEW.md and KANEO_FINAL.json.

| Gate | Technical evaluation |
|---|---|
| M5-S — structural/preservation | PASS, supported ACT 2.4 / SPR 2.1, accepted RSF-23–26 plus fresh regressions |
| M5-I — independent verification | PASS, independent Rust decode and whole-pair effective-image/metadata comparison within its supported scope |
| M5-N — pinned Korangar | PASS for exact compiled synthetic Walk load, all reachable views, selected images and actual software-Vulkan rendering in the isolated native presentation corridor |
| Overall M5 | Eligible for FULLY_ACCEPTED after RSF-27 QA_PASS and accepted read-back; scoped engineering milestone, not a production-artwork or universal-rendering claim |

Native technical decision: accept the tested loading, selection and rendering boundaries
on independently reproduced evidence. Operator artistic decision: no real creative
artwork approval requested, created or granted; synthetic review fixtures only. The user
explicitly authorized objective acceptance after independent QA, including diagnostic
native engineering proof. Repository workflow reserves additional human approval only
for decisions explicitly assigned to the operator; no new artistic decision is needed
to accept this technical task. Product adoption and real-art approval remain human.

Level D pixel/reference parity, hardware GPUs, ordinary gameplay and audible sound are
UNVERIFIED/NOT_TESTED. Wider artwork remains incomplete; no full-profile asset readiness
is asserted. These are outside the bounded native acceptance contract, rather than failed
mandatory criteria. Python 3.12/3.13 and rustfmt are unavailable, as recorded explicitly.
M6/RSF-28 is identified through live dependencies only; no next task is started.
