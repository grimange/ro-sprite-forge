# M7 compatibility gate evaluation

Overall milestone verdict: **FULLY_ACCEPTED** after RSF-35 independent QA_PASS
and final Accepted read-back under Codex ownership. This packet evaluates the existing four plan requirements;
it does not create a new milestone or new scope. The final tracker snapshot will
be retained in `kaneo-final-readback.json`.

Authority: Implementation Plan v1.1 §6/M7, SHA-256
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.
The repository's verification template defines the overall verdict vocabulary
`FULLY_ACCEPTED / PARTIAL / FAILED / UNVERIFIED`. Kaneo represents the milestone
through the four existing tasks; no separate milestone-status API was discovered.

| Existing task | Live state at evaluation | Evidence |
|---|---|---|
| RSF-32, additional job/body profiles and compatibility registry | Accepted, four criteria checked, independent QA_PASS | `../rsf-32/independent/QA_REPORT.md`; live task `wbh6jvha6imo9jeub9zmhovj` |
| RSF-33, equipment and attachment compatibility | Accepted, four criteria checked, independent QA_PASS | `../rsf-33/`; live task `ohmigbqn0escc46dkopt2h0c` |
| RSF-34, costume and visual-outfit compatibility | Accepted, four criteria checked, independent QA_PASS | `../rsf-34/QA_REPORT.md`; live task `o5jlgmryf188c7lr43saqz7c` |
| RSF-35, offline custom actions and runtime reporting | Accepted, four criteria checked, independent QA_PASS | This packet and `REPORT.md`; live task `ly1cfaohrp6e00qxg4g1tfcj` |

The first plan requirement is supported by the accepted RSF-32 inventory and
planning evidence for distinct job-reference profiles, including Genetic Female
Costume 1 body and Dragon Knight male shield, plus the public synthetic Swordsman
body and Falcon companion. These have different motion, image, layer and anchor
properties. This does not assert that a Dragon Knight body was found. RSF-34
reconciled the old shield pairing: its enrolled parent is `novice-male-body-v1`,
and the old relationship remains partial/template evidence. Exact source-bound
Genetic/shield comparison preserves the Pickup mismatch (96/104 compatible slots).

The second requirement is supported by RSF-33/34 exact action/view/frame and
attachment checks, separate gameplay/body/appearance identities, and partial
compatibility reporting. Valid individual resources do not imply a valid pairing.
No filename substitution or automatic fitting repairs incompatibilities. Separate
head sources remain independent and require an applicable declared host binding.

The third requirement is exercised here by Guard and Dodge, each with explicitly
inherited four-frame/view/layer storage topology. Existing writers compile the
selected occurrence into a bounded diagnostic pair without adding ACT slots.
The output records `runtime_slot: null`, diagnostic storage slot 8, runtime
`UNSUPPORTED`, native `UNVERIFIED`, and no production authorization. Full original
40-slot inventory, unaffected effective images and metadata remain preserved.
Repeated binaries/build manifests match, and independent Rust verifies the
supported decoded structure. Known Walk remains source-backed slot 8; using that
storage does not establish custom-action dispatch. Standalone Wave demonstrates
four exact offline assigned frames and explicit diagnostic timing without a native
slot. Production requests and slot-spoofing claims fail with typed diagnostics.

The fourth requirement is supported by RSF-34's separate optional adapter over
approved, provenance-bound supplied artwork. Retained classic artwork and invisible
fallback do not count as newly authored coverage. Relevant composition changes
stale dependent reviews without invalidating independent body/component decisions.
RSF-35 preserves that review authority and does not generate or approve artwork.

Existing M5-S/M5-I and bounded M5-N evidence remain limited to their accepted
resource scopes. New costumes/custom actions gain no native authority from this
milestone. No Korangar/rAthena code, gameplay dispatch, garment generation or
arbitrary slot allocation is part of M7 acceptance. Browser and GPU execution are
NOT_RUN for RSF-35 because neither is changed or claimed. Python 3.12/3.13 remain
NOT_RUN in this environment; Python 3.14.4 and the installed distribution passed.

The next task is RSF-36, `[M8] Portable packaging, CI and reproducible release
artifacts`, internal ID `zhk7olqfex25j8tewzoragi0`. Its live blocking dependencies
are RSF-26, RSF-31 and RSF-35. It remains Backlog, unassigned, and is not started by
this evaluation. Final MCP relation read-back confirms all three blockers Accepted; RSF-36 is
dependency-eligible and remains Backlog/unassigned. No next-task implementation
was started.

Independent reviewer `/root/rsf35_qa` assessed this four-criterion evaluation and
confirmed closure eligibility after RSF-35 Accepted read-back. Actual final task
read-backs fulfill that condition. The verdict uses the existing repository
verification vocabulary and is recorded with evidence on RSF-35, without inventing
a separate Kaneo milestone object or altering prior accepted task evidence.
