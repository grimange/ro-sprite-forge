# RO Sprite Forge — Comprehensive Implementation Plan v1.1

**Status:** Revised implementation baseline for operator adoption; not an authorization to modify LWR or create Forge code.  
**Prepared:** 2026-10-29  
**Revision:** v1.1 — targeted corrections to requirements, verification, approval, determinism and milestone gates.  
**Product:** `ro-sprite-forge` — standalone, local, human-operated Ragnarok animation production workbench  
**Primary runtime target:** Korangar first; traditional RO client compatibility is a later, separately tested target  
**Primary implementation language:** Python 3.12+ (verify supported versions in CI); Rust as an independent verification oracle, not a second application core  
**Starting evidence:** `RO_SPRITE_FORGE_LWR_REUSE_AUDIT_E1.md` (2026-10-29), LWR E1–E3 character-production experiments and their bounded native evidence.

---

## Revision record — v1.0 → v1.1

**Change policy:** Preserve the v1.0 product architecture, operator-only visual authority, standalone Python core, Rust independent oracle, Korangar-first scope, and M0–M8 roadmap. These changes are **engineering requirements proposed after review**, not newly audited evidence about LWR or the native client.

| ID | v1.1 correction | Primary sections |
|---|---|---|
| R1 | Require operator-declared or explicitly inherited **layer topology** before claiming an exact new-art work order | 3.1, 3.4, M1 |
| R2 | Separate M0 **structural**, **independent decoder** and **native** gates; allow bounded downstream planning with transparently unresolved native proof | 6, M0, 7 |
| R3 | Prove **requested action/view/ACT-slot resolution**, not merely successful resource loading or fallback animation | 4.7, M0, M5, 7 |
| R4 | Bind visual approval to a canonical **visual composition revision** that exists before compilation; keep native evidence separate | 2.3, 4.3–4.4, M3–M5 |
| R5 | Define canonical serialization and separately test **byte preservation** versus **parse/serialize correctness** | 4.5–4.6, M0, M5 |
| R6 | Make a bounded **Walk** workflow the first external-art-to-native vertical slice at M4–M5; leave video ingestion in M6 | M4–M6, 14 |

**Terminology:** A *milestone may be implemented with an unresolved gate*, but only fully accepted when its own stated gates pass. A scoped prototype may be `COMPLETE_FOR_DECLARED_SCOPE` without being `COMPLETE_FOR_FULL_PROFILE` or `NATIVE_VERIFIED`. The precise states are not interchangeable.

---

## 1. Decision summary

**Build RO Sprite Forge as a requirements-driven, human-operated animation asset compiler and inspection workbench.** Before artwork production, it enumerates a declared actor's required actions, views, frame occurrences, layer occurrences, image identities and attachments. The operator supplies or selects artwork, approves its appearance and its assignment, and Forge deterministically validates and compiles the approved inputs into SPR/ACT assets.

The product is **not** an AI artist, automatic pose generator, automatic anatomy repairer, visual quality judge or new Korangar renderer. Video/image tools supply candidate frames; the operator decides which frames are appropriate. Forge makes missing or invalid inputs obvious rather than disguising them with fallbacks.

**Release success test:** An operator chooses or defines a monster/player profile, obtains an actionable requirements and missing-art report *before producing art*, imports suitable artwork from images/video, maps it to requirements, reviews animation playback, approves the exact source revisions, and exports a verified SPR/ACT pair. The resulting asset is tested in a pinned Korangar build. This should also work for imported Novice and Orc Skeleton references without presuming identical layouts.

**First implementation milestone (M0):** Standalone resource inventory, preservation/round-trip evidence, and known-good SPR/ACT inspection for the audited male Novice and Orc Skeleton, with independent Rust decoding and a separately reported bounded native test. **No GUI or video input is required in M0.** An unresolved native gate does not erase structural evidence or automatically block M1 requirements planning; it does block any claim that overall M0 is fully accepted or that an artifact has native proof. The operator workbench comes online in M3, before external-art ingestion in M4.

### 1.1 Facts established by the audit versus planned features

| Audited fact / limitation | Consequence for design |
|---|---|
| Original male Novice: 13 groups, 104 action/view slots, 456 motion occurrences, **110 referenced SPR identities** and **108 distinct decoded image contents** | Track slots, occurrences, image identities and deduplicated content as different quantities. Do not promise only 108 authored files are needed for arbitrary replacement art. |
| Orc Skeleton: 5 groups, 40 action/view slots, 512 motion occurrences, **1,776 visible layer references**, 55 referenced images out of 57 stored | Support ordered multilayer frames, mixed transforms and unused images. Do not model every frame as one flat drawing. |
| Audited Korangar players use 13-group mapping; NPCs/monsters use 5-group mapping; runtime reachability does not equal mapped enum membership | Version semantic runtime profiles and validate real action selection separately from file structure. |
| LWR Python tools passed 22 existing tests and can read/write ACT 2.4, decode SPR 2.1 and write SPR RGBA 2.1 | Extract tested codecs and validations; do not recreate them. **Current SPR indexed decode → RGBA write is not indexed byte-preserving.** |
| Experiment assets/working code are untracked or isolated in local checkouts | Extract by explicit source snapshot/hash and provenance; never assume an LWR HEAD commit fully identifies them. |
| Rust independent decoder and fresh native playback were **not** run in the audit | Both are explicit implementation/acceptance work, not existing guarantees. |

**Source of evidence:** `RO_SPRITE_FORGE_LWR_REUSE_AUDIT_E1.md` §§2–7, 11–14. New milestone details below are **design proposals**, not audit findings.

---

## 2. Product boundaries and human visual authority

### 2.1 Responsibility contract

| Activity | Operator | Forge |
|---|---|---|
| Choose actor, body/job/monster profile and intended animation scope | Owns decision | Displays choices and requirements |
| Choose visual design, choreography and suitable actions | Owns decision | Records declared contract |
| Generate/draw artwork or supply video/images | Owns source and rights | Imports, hashes and previews |
| Choose frames, assign to slots, approve mirroring or transformations | Owns decisions | Validates assignments, persists provenance |
| Approve appearance, continuity, readability, style and animation aesthetics | **Sole visual authority** | Provides faithful previews and review states |
| Enumerate finite required slots, frames, layers and image references | Reviews scope | **Deterministically computes** |
| Detect missing, duplicate, mismatched, corrupted or unmapped inputs | Resolves missing art | **Reports exact requirement IDs** |
| Encode, compile and verify SPR/ACT format/coverage | May request export | **Deterministically implements** |
| Declare gameplay support / native animation acceptance | Reviews observed playback | Records runtime profile and verifiable evidence; cannot invent support |

**Non-negotiable:** Forge does not generate missing imagery, infer hidden anatomy, fix an ugly pose, automatically accept an AI video, silently alter body proportions, or describe artwork as visually good. No machine visual-quality score is required. Operator-approved transformations are explicit, reproducible and inspectable; mismatches are surfaced, not repaired without instruction.

### 2.2 Explicit non-goals for initial release

No embedded generative AI, mandatory cloud account, pixel drawing program, auto rigging, synthetic animation generation, LWR gameplay/server modifications, GRF patching by default, multi-user project management, distributed processing, task-tracker integration or database server. Do not rebuild Korangar's renderer inside Forge. Do not call a placeholder or unchanged original outfit a completed new outfit.

### 2.3 Trust and approval semantics

- **Input presence** is not **technical validity**; validity is not **coverage**; coverage is not **visual approval**; visual approval is not **native runtime proof**.
- An operator approves a **canonical visual composition revision** *before* compilation: exact source-content hashes; requirement/pose assignments; ordered layers; crops, transforms and processing recipes; relevant timing, offsets and anchors; applicable target/runtime-profile revision; and the preview renderer's semantic version/behavior identity. A change affecting the reviewed result invalidates only the impacted approval scope; unrelated rebuilds must not spuriously invalidate approvals.
- The compiler consumes the approved composition revision and records its digest in the build manifest. **Approval must not depend on an output build hash that does not exist yet.** Build identity, structural verification and native-runtime evidence are attached afterward and do not retroactively create aesthetic approval.
- If preview fidelity for a required behavior is unverified or partial, mark `PREVIEW_PARTIAL`/`PREVIEW_UNVERIFIED`. Operator inspection may be recorded as provisional, but must not be mislabeled a fully faithful visual-runtime review. Native visual acceptance is a distinct subsequent decision.
- Allow batch approval of a reviewed action/view or selected group of frames. The operator must see the precise scope before confirming.
- An unchanged, imported reference may be marked `visual_review=NOT_REQUIRED` for a structural-only round-trip. All newly supplied/replacement art requires an explicit review policy and normally operator approval before a production export.
- Diagnostic/partial exports may be allowed for testing, but carry a conspicuous `PARTIAL_DIAGNOSTIC` label and cannot be represented as a complete or approved release.

---

## 3. Actor profiles, jobs and finite requirements

### 3.1 Four separate authorities

1. **Resource inventory:** What the actual SPR/ACT files contain. Actions are numeric; frame/layer/image references and raw metadata come from the file.
2. **Runtime profile:** What a *specific pinned Korangar build* maps to Idle, Walk, Attack, Hurt, Die, etc.; how views, timing and attachments are selected. This does not supply an artist's intended count for new actions.
3. **Declared target:** What this project intends to produce or replace: required/optional actions, views, frames per view, **layer topology and layer roles**, supported variants, and exclusions. For a new actor, missing choreography, frame counts or layer topology are *design inputs* to request, not values Forge guesses.
4. **Artwork assignment ledger:** Which exact input image/video frame or source image (with transformations) satisfies each target requirement, plus human approval and validation state.

The inventory and target need not have matching cardinalities. An original resource can be fully valid while a proposed *replacement* has zero assigned art. Retaining original fallback artwork must not count as having authored replacement clothing.

### 3.2 Supporting job classes without hardcoding them

The planner supports any class or job through **profiles**, not hardwired `Novice` logic. Separate:

- **Gameplay job identity** (Korangar/rAthena behavior; outside Forge's authority).
- **Visual body family** (Novice, Swordsman, Mage, etc.; sex/body variant, costume, potential baby/mount variants).
- **Action/motion profile** (action groups, direction mapping, counts and timing rules; imported or explicitly declared).
- **Equipment/attachment compatibility** (head, weapon, shield, garment, anchors and weapon action family; profile-specific, and may be unknown).

In M0, test male Novice and Orc Skeleton. In M1, an unfamiliar job can already be **imported and inventoried** without code changes; unknown semantic mapping remains `UNVERIFIED`. In M7, exercise selected additional classes and specific weapon/attachment cases using local reference art without distributing it. Do not assume every new job has the Novice's frame counts or that a Novice outfit works with all weapon actions.

### 3.3 Counts required in every inventory

- Action groups and numeric action/view slots.
- Frame/motion occurrences per slot and aggregate totals.
- Total visible layer references (a frame may contain 1, 2 or 12 layers).
- Total stored images, referenced image identities, unused image identities.
- Distinct decoded-content equivalence classes, separately from image identities.
- Reuse relationships (shared indices, content duplicates, declared mirror/transform reuse), not inferred artistic equivalence.
- Timing/delay, events, transforms, offsets, registration, anchors, loop/action mapping and reachability by runtime profile.
- Artwork assignment coverage by **target**, not by mere existence of original resources.

For a target contract with specified actions A, views V and per-view frame count F, compute required frame occurrences as `sum(F(a,v))`; layer work is separately `sum(layer_count(a,v,f))`, **only when the target layer topology is declared or explicitly inherited**. The unique artwork workload is determined only after explicit reuse assignments and allowed transformations are resolved. Never equate these three measures.

### 3.4 Declared layer topology and finite work orders (v1.1)

**Mandatory target contract for an exact work order:** For every in-scope action/view, specify the frame count; for every required frame, specify an ordered set of layer requirements (which may contain one layer), optionally with role/part identifiers, registration/anchor expectations and constraints on reuse. A target may provide these by:

1. **Explicit per-frame declaration:** The operator defines layer counts/roles directly (including the legitimate one-layer case).
2. **Explicit reference inheritance:** The operator selects a known resource/profile revision whose observed layer topology is copied into the declared target; record the reference hash and whether all action/view/frame mappings exist.
3. **Explicit named template:** The operator selects a versioned single-layer or other topology template and confirms its application to the exact action/view scope. **No silent global single-layer default.**

A resource inventory reports *observed* layer counts; those observations do not automatically become the *new actor's intended* topology. Missing frame counts produce `UNDERSPECIFIED_FRAME_COUNT`; missing or partly unmapped layer declarations produce `UNDERSPECIFIED_LAYER_TOPOLOGY`. Unverified attachment requirements remain separately unresolved. Forge may show a provisional frame-only checklist, but cannot label it an **exact frame-and-layer work order**, `COMPLETE_FOR_DECLARED_SCOPE`, or export-ready.

**Illustrative contract, not an audited fixture:** 8 directions × 6 Walk frames = 48 frame occurrences. If the operator explicitly selects one layer per frame, that is 48 layer occurrences; if the operator declares two ordered layers per frame, that is 96. Forge does not infer either count from the word `Walk`.

**Checklist output:** Include actor/resource part, semantic action and numeric runtime slot where known, view, frame, layer ordinal/role, required/optional status, specified vs inherited topology source, assignment/reuse state, and unknowns. Compute unique source-art effort only from declared, approved reuse relationships, not inferred visual similarity.

---

## 4. Architecture and module boundaries

### 4.1 Reference architecture

```text
Operator UI (local browser)       CLI (automation/scripting)
              \                  /
               Application API / use cases
                        |
       +----------------+------------------+
       |                |                  |
 Resource inventory   Requirements      Artwork ledger
 SPR/ACT codecs       Profiles/targets  approvals/provenance
       |                |                  |
       +----------------+------------------+
                        |
           Preview / timeline / diagnostics
                        |
          Explicit image/video transformations
                        |
           Compiler + build manifest + hashes
                        |
       Python structural & coverage verification
                        |
        Independent Rust decoder comparison
                        |
        Pinned Korangar native test (external)
```

Core Python modules must not depend on HTTP/UI, LWR repository paths, local GRF archives, a live server, or FFmpeg. UI and video are adapters calling the same use-case API as the CLI. The Rust harness is an independent **test oracle**, not production code invoked for every operator action.

### 4.2 Recommended stack

| Layer | Initial choice | Rationale |
|---|---|---|
| Core application/CLI | Python 3.12+; `argparse` or Typer, selected once in M0 | Direct reuse of tested LWR code; reproducible scripts. |
| Binary/image | Existing audited Python codecs, stdlib + Pillow | Preserve exact ACT fields; inspect/compose pixels without needless new deps. |
| Contracts | Versioned JSON, JSON Schema; typed in-memory models | Deterministic, inspectable, portable. |
| Local projects | Filesystem directories + atomic JSON manifests/content-addressed blobs | No DB necessary; easy backup and diff. |
| Video import | FFmpeg/FFprobe as optional subprocess adapters | Decode streams with actual source PTS, explicit reviewed selections. |
| Independent oracle | Small Rust decoder using pinned Korangar `ragnarok-formats` | Reduces same-codec shared-bug risk; never silently trust it as a renderer. |
| Human UI (M3+) | Lightweight local Python HTTP API + compact TypeScript/JS canvas frontend | Timeline, comparison, requirements/missing-art workspace; no full drawing editor. |
| End-to-end test | Pinned Korangar binary/build profile and explicit artifact hashes | Real runtime evidence, action/view coverage and asset loading. |

Version-pin dependencies and compiler behavior for reproducibility. No runtime package should require a Rust build merely to inspect an asset. The project's internal API must be UI-agnostic.

### 4.3 Data records and stable IDs

Use related, versioned records rather than one oversized magical `character.json`:

| Record | Owns | Essential fields |
|---|---|---|
| `resource-inventory` | Observed source bytes, never assumptions | Format versions, bytes/hash, raw ACT records, clip/layer references, SPR pools/images, event/delay/anchors, counted summaries |
| `runtime-profile` | Semantics for a pinned runtime | Runtime/binary revision, actor category, group/view mapping, action reachability, timing, attachment rules, supported output profiles |
| `target` | Operator's finite intended deliverable | Actor/visual family, required actions/views/frame counts, declared/inherited ordered layer topology and origin, optional/excluded actions, output compatibility, full vs scoped target |
| `assignment-ledger` | Operator-selected artwork sources/reuse | Requirement ID, source hash, image crop or video PTS, ordered layers, transforms, reuse references, assignment revision, validation and review status |
| `visual-composition-revision` | Pre-build human review subject | Canonical digest of source identities, exact assignments, ordered layers, transforms, timing/anchors, target/profile versions and preview semantics; review scope/state |
| `build-manifest` | Reproducible compiled artifact | Input/contract/profile/composition hashes, tool/dependency versions, output hashes, raw preservation/conversion policy, verification references (external evidence may be nondeterministic) |

**Stable occurrence ID** example: `body:action=walk:view=7:frame=3:layer=0`. IDs should be independent of filenames and include the resource part and intended actor/profile namespace; an imported numeric ACT slot is preserved alongside a semantic action ID. For attachments, identify parent resource, child resource and anchor relationships.

**Versioning:** schema, runtime-semantic profile, target contract, composition, preview behavior and compiler versions are distinct. Target edits, new custom actions and different runtime mappings do not rewrite original inventories. Migrations preserve old source hashes and invalidate only affected assignments/reviews, with explicit dependency links from every approval to its composition revision.

### 4.4 Orthogonal status fields

```text
requirement:      REQUIRED | OPTIONAL | OUT_OF_SCOPE
availability:     AVAILABLE | REUSED | MISSING | UNVERIFIED
validation:       VALID | INVALID | UNVERIFIED
runtime_support:  SUPPORTED | UNSUPPORTED | UNVERIFIED
visual_review:    APPROVED | REJECTED | UNVERIFIED | NOT_REQUIRED
native_evidence:  VERIFIED | FAILED | UNVERIFIED
preview_fidelity: VERIFIED | PARTIAL | UNVERIFIED
action_resolution: VERIFIED_EXACT | FALLBACK_OBSERVED | UNVERIFIED
```

Do not compress them into one `PASS` enum. `COMPLETE_FOR_DECLARED_SCOPE` requires a fully specified frame-and-layer contract, valid assignments and applicable approvals for every in-scope required occurrence. `COMPLETE_FOR_FULL_PROFILE` additionally requires all full-profile requirements. Neither status implies runtime verification. Preview-fidelity and exact-action native evidence are separately reported. An operator-reviewed partial preview is never silently upgraded to verified visual-runtime parity. `AVAILABLE+INVALID` is not `MISSING`. `UNSUPPORTED` gameplay mapping is not a missing PNG. Source-art reuse must identify which reference remains classic.

### 4.5 Compilation policies

- **Preserve mode (default for unchanged assets):** Preserve ACT/SPR bytes and source identity where possible. Unchanged indexed resources must not be silently reencoded to RGBA.
- **Explicit conversion mode:** Allow a supported RGBA SPR 2.1 path only when requested, recording palette/index-information loss; verify remapped ACT image pool/index references and decoded pixels.
- **Changed animation build:** Rebuild necessary resources from validated ordered layers/images, retaining raw ACT metadata where applicable; do not silently coerce unknown versions or drop event/anchor/opaque fields.
- **Fail-closed completeness:** Production export refuses unresolved required assignments, invalid references or missing required approvals; optional diagnostic build is unmistakably partial.
- **Determinism:** Same source content, contract, canonical visual composition, compiler/dependency versions and output policy produce identical SPR/ACT bytes and hashes under the specified build environment. Apply §4.6 canonical serialization rules. Atomic build publication, no in-place modification of original assets.
- **Two distinct round-trip tests:** (a) unchanged resource pass-through must prove byte-for-byte preservation; (b) independent parse → serialize → parse tests must prove all supported ACT fields, sprite references and decoded behavior are retained and identify exactly where byte equivalence is or is not promised. A file copy is not proof of serializer correctness.
- **Invalid assets:** Meaningful error IDs and remediation directions; never hide an invalid required resource behind Korangar's runtime fallback and declare a complete Forge build.

### 4.6 Canonical build and preservation contract (v1.1)

1. **Canonical models/ordering:** Stable sort/ordering for schema keys, action/view/frame records, ordered visible layers, reused SPR image identities and pool indices; keep semantically meaningful layer order intact. Specify numerical serialization/rounding and binary field representation. Preserve opaque known-supported bytes where promised; reject unknown versions or impossible lossless modifications.
2. **Deterministic transformations:** Version pin image decoders, resampling algorithms, palette/color-space policy and build settings. Explicitly distinguish source raw bytes, staged pixels, preview RGBA and final encoded SPR pixels; do not let preview conversion silently rewrite source representation.
3. **Canonical build identity:** Hash source inputs, target, runtime profile, composition revision, build policy and relevant toolchain versions using a documented stable representation. No timestamps, hostnames, absolute operator paths, random UUIDs, filesystem iteration order or ephemeral native-test data in deterministic SPR/ACT bytes.
4. **Evidence separation:** Binary artifact hashes and a deterministic build manifest are immutable; record machine-specific test commands, capture timestamps, logs and native captures in a linked *verification evidence record* outside the reproducibility hash. Rebuilds with identical canonical inputs must match output hashes even when run at different times or paths.
5. **Proofs:** Test unchanged indexed SPR/ACT raw pass-through byte equality; ACT encode/decode semantic round-trip with complete supported-field comparison; modified compilation using two clean builds with identical output hashes; explicit conversion mode with transparent representational-loss report.

### 4.7 Native action-resolution evidence contract (v1.1)

A Korangar resource loading or any animation rendering is **not** proof that the requested action/view was selected. Record, per tested actor/scenario: pinned binary/source build identity; installed SPR/ACT hashes and resource path; requested semantic action and direction; resolved numeric ACT action/view slot; observed selected frame/layer sequence; and whether fallback/modulo/substitution occurred. A trace, instrumented isolated presentation harness or other independently inspectable evidence must support the slot mapping. Screenshots alone are insufficient if they cannot distinguish fallback from an exact match.

Use separate conclusions: `ASSET_LOADED`, `REQUESTED_ACTION_VERIFIED`, `FALLBACK_OBSERVED`, `NATIVE_UNVERIFIED`, and `NATIVE_FAILED`. Where the runtime cannot select a custom or short-profile action, keep the result diagnostic/offline; **do not** call it runtime verified because an animation happened to play. A full-profile native pass is evaluated against its pinned reachable action/view scope; a deliberately narrow prototype is labeled as such.

---

## 5. Operator experience and UI specification

### 5.1 UX principle

**One workspace, not a maze of administrative screens.** The operator should immediately see *what to create next*, be able to assign or reuse art, inspect actual motion, approve it and export it. Put administrative metadata in contextual drawers, not separate primary navigation.

Default layout (desktop):

```text
+----------------------------------------------------------------------------------+
| RO Sprite Forge   [Project: Orc Skeleton Variant] [Profile: Korangar Monster]    |
| [Import] [Requirements] [Preview] [Build]                         [Project menu] |
+------------------------+--------------------------------+------------------------+
| REQUIREMENTS TREE      | PREVIEW / COMPARE              | SELECTED REQUIREMENT   |
| Idle      120/120      | [Reference] [Candidate]        | Attack > View 3 > F04 |
| Walk       48/48       | fixed canvas / checkerboard   | Source: unassigned     |
| Attack     56/96 !     | zoom, overlays, origin/anchor | Required layers: 2     |
| Hurt        0/72 !     | step, play, loop, speed       | Import / Assign / Reuse |
| Die         0/176 !    | [action view picker]            | transform / review     |
|                        +--------------------------------+------------------------+
| Missing assets (filter): [Required] [Unassigned] [Invalid] [Review pending]      |
| [Select multiple] [Assign sources] [Approve reviewed scope] [Export checklist]  |
+----------------------------------------------------------------------------------+
| Build readiness: STRUCTURAL PASS | COVERAGE INCOMPLETE | VISUAL REVIEW PENDING  |
+----------------------------------------------------------------------------------+
```

*Wireframe counts are illustrative; not a live coverage claim.*

### 5.2 Operator journeys (all required for usable first release)

**Journey A — Existing actor:** Create project → choose pinned profile → import SPR/ACT resources → see exact resource inventory and required/missing assignments → preview imported actions and layers → retain/import replacement art → review → compile → verify.

**Journey B — New monster:** Choose `monster` template / reference → operator declares actions, directions, per-direction frame counts **and explicit or inherited layer topology** → Forge produces a finite frame/layer checklist **before** artwork → assign PNG/video-derived poses → preview and approve → build. Missing frame counts or layer topology yield explicit `UNDERSPECIFIED` diagnostics; Forge does not guess.

**Journey C — Another job class:** Select/import Swordsman/Mage/etc. body reference and compatible action/weapon profile → inventory real file structure → distinguish job identity from visual outfit and animation compatibility → record unsupported actions; do not force Novice's profile onto the new class.

**Journey D — Partial prototype:** Operator defines `idle-only-prototype` → export may be declared complete *for that scope only* while full-profile requirements remain visibly incomplete. The UI must not present this as production-ready full character.

**Journey E — Visual review:** Operator previews selected frames, original vs candidate side by side, actual action/view/delay and anchors; explicitly approves or rejects a **canonical pre-build composition revision**. Changed art or rendering-relevant processing invalidates affected approval; identical binary rebuilds do not. Unverified preview semantics are labeled, not presented as native fidelity. No auto aesthetic judgment.

### 5.3 UI controls required, not merely decoration

- **Requirements list/tree:** group by action → view → frame → layer. Filters: unassigned, invalid, unreviewed, unsupported, reused, ready and underspecified topology. Surface exact IDs, counts and declaration/inheritance provenance.
- **Coverage counters:** show action/view slots, motion occurrences, layer references, referenced identities and content duplicates separately; avoid single misleading percentage.
- **Import tray:** inspect PNG sequences/sheets/video frame selections, source hashes, dimensions and transparency; batch assignment is essential.
- **Preview:** actual layered transformed frames (including rotation, tint, mirror, alpha and anchor where supported), player body/head synchronization; onion skin and source-vs-candidate compare. Mark a preview as `PARTIAL` when some rendering behavior cannot yet be reproduced.
- **Timeline:** frame scrub, step, loop, speed, action/view switch; display source PTS separately from runtime playback timing.
- **Assignment editor:** drag/batch map selected art to exact requirements, declare reuse/mirror/transform, visualize before/after, explicit operator confirmation.
- **Approval:** approve the displayed pre-build visual composition revision at frame, view, action or selected batch scope; show its digest, preview fidelity, and stale-approval warning on relevant changes.
- **Build panel:** one-click `Validate` then `Build`, readable error list with exact missing/invalid IDs; production/export only when gates pass.
- **Evidence:** export manifest, source/build hashes, validation report, coverage list and optional native verification record.

**Accessibility/ergonomics:** keyboard frame stepping; keyboard shortcuts for assign/review; 1x and integer nearest-neighbor zoom; transparent/checkerboard grid; avoid color-only error indicators; autosave manifests atomically with backups; large import sets should not force hundreds of manual clicks.

### 5.4 UI scope discipline

M3 builds an *operator-facing minimum viable workspace* on existing imported assets; M4 adds assigning PNG/sheets, M5 adds modified compilation, M6 adds video selection. Do **not** start with a full drawing editor, node-based workflow builder or elaborate dashboard. The CLI remains the scriptable source of correctness, while the UI exposes those same operations for humans.

---

## 6. Staged implementation roadmap

Milestones are delivery slices, not arbitrary bureaucracy. Each has a direct observable acceptance gate. **A missing critical gate prevents that milestone's full-acceptance claim, not automatically all independent downstream development.** M1 requirements planning may proceed when M0 structural evidence and independent decoder results are verified while M0 native evidence remains explicitly unresolved. Modified builds and release claims still require their native gates; M2 preview limitations remain visible until parity is demonstrated. Do not use unrelated scope expansion to conceal a failed test. Previous working versions remain usable and reversible. Milestone IDs below are local to the new standalone project; do not infer or create Kaneo tasks without operator request.

### M0 — Standalone core, requirements inventory and known-good round-trip

**Purpose:** Prove we can correctly enumerate and reproduce both real actor types without hidden LWR paths or future artwork assumptions.

**Scope:**
1. Create installable Python package and CLI (`inspect`, `plan`, `verify`, `roundtrip`) with typed error handling and pinned dependencies. M0 `plan`/`verify` implement bounded inventory/full-vs-scoped semantics; generalized editable targets and the full missing-art workflow arrive in M1.
2. Extract/adapt audited `ro_reference.py` codec (ACT 2.4, SPR 2.1) and provenance checks; save exact upstream local hashes and attribution. No runtime imports from the LWR checkout.
3. Define the foundational inventory and frozen Korangar runtime-profile records. Target audited Korangar primary revision `3f3d88a583203f09d079712f43343c1041258ffd` unless the operator identifies a new normative executable; record exact hash/revision selected.
4. Enumerate every action/view/frame/layer, image pool, transform, bounds, anchors, events and raw delay. Distinguish referenced identities from decoded content classes and unused entries.
5. Emit deterministic manifests and basic full-vs-scoped requirements/coverage output. For an authored target missing a declared frame count or layer topology, report precise `UNDERSPECIFIED_FRAME_COUNT` or `UNDERSPECIFIED_LAYER_TOPOLOGY` rather than fabricating an exact art workload.
6. Implement byte-preserving unchanged ACT/SPR pass-through **and separately** test ACT parse → serialize → parse field equivalence; report any unavoidable representational differences. Explicit RGBA conversion, if included, must be marked lossy for indexed representation and separately verified.
7. Build independently maintained Rust decoder harness and compare Novice and Orc Skeleton inventories (not same-codec-only checks).
8. Perform bounded native Korangar verification of resulting unchanged resources in a pinned build, including player body/head views and representative monster action/view/layer behavior. Record exact requested/resolved action/view/slot and any runtime fallback using §4.7. If necessary, use a labeled isolated presentation harness for states unavailable through normal gameplay.

**Fixtures:** Private local hash-pinned Novice quartet, Orc Skeleton pair, synthetic redistributable malformed/multi-pool/mirror/anchor fixtures. Never ship original art or local GRF archive.

**Acceptance gates (all three required for full M0 acceptance; independently reported):**
- Runs in a clean directory without LWR, GRF, DB, network or server as a package dependency.
- Exact Novice 13/104/456/110 identities/108 contents and Orc 5/40/512/1776 layer refs/55 referenced of 57 stored; report unused image identities.
- **M0-S structural:** ACT/SPR unchanged pass-through remains byte-exact; supported ACT parse/serialize semantic round-trip is tested separately, with complete field/reference checks and documented non-byte-preserving cases. Any explicit SPR conversion reports decoded-pixel comparison and palette representation change separately.
- **M0-I independent:** Rust inventory agrees on all canonical structural fields and rejects synthetic corruption/missing refs; synthetic fixture tests are executable without private game art.
- Production requirements status does not misclassify a one-action scope as complete full profile.
- **M0-N native:** Korangar test records build identity, loaded asset hashes, requested and resolved action/view/slot with fallback status (§4.7), and observed frame/layer scope; no unexplained character rendering regression.

**Gate/dependency rule:** If M0-S and M0-I pass but M0-N cannot run for a documented environment limitation, record `M0_PARTIAL_NATIVE_UNVERIFIED` and **do not** label overall M0 `PASS`. M1's purely structural requirements/ledger implementation may proceed on those verified prerequisites. A **failed** native check that implicates codec output, slot mapping or source integrity requires root-cause correction before depending on the affected path. M2 may implement preview provisionally but must label native-uncompared semantics `PREVIEW_UNVERIFIED`; M5 native-verified release remains blocked until real native proof. No UI/video work solely to bypass a broken gate.

### M1 — General actor profiles, authored targets and artwork ledger

**Purpose:** Given any imported or newly declared actor, provide a finite *work order* before generating art.

**Scope:** Actor/player/NPC/monster templates; runtime mapping/profile revision; editable target required/optional actions, per-view frame counts and **operator-declared or explicitly inherited ordered layer topology**; custom action IDs explicitly marked unmapped until runtime support; reference-to-target comparison; assignment ledger with missing/valid/invalid/reused/unverified; explicit transform-reuse graph with cycle detection and approval needs; full versus scoped coverage calculations.

**Acceptance:**
- A new monster with operator-specified action/view/frame counts **and explicit or inherited layer topology** yields exact required frame/layer lists and an exported production checklist *without any uploaded artwork*. Missing topology yields `UNDERSPECIFIED_LAYER_TOPOLOGY` and only a provisional frame-only list.
- Missing source, invalid hash, present-but-unapproved, excluded action, existing classic fallback, unsupported runtime action and reused reference produce distinct results.
- Player/NPC/monster semantic profile differences remain intact; unknown group names are not fabricated.
- A non-Novice imported actor can be inventoried without writing code, even if action semantics require a new profile declaration.
- A single-layer named template and a multipart topology fixture yield different, correct layer counts; undeclared layer topology never quietly defaults to one layer.

### M2 — Faithful preview and diagnostics core

**Purpose:** Let the operator inspect actual images and playback before approving. No aesthetic scoring.

**Scope:** Portable preview service/API for imported and assigned SPR/ACT actions, order-preserving multilayer compositing, tint/scale/rotation/mirroring, origin/head anchors where declared, actual timing modes or explicitly labeled diagnostic timing; reference-versus-candidate playback; contact sheets, sprite bounds, alpha/occlusion overlays and frame stepping. Keep raw sprite/palette data separate from preview RGBA. Version preview behavior because approvals bind to it; every preview declares fidelity state and unsupported semantics.

**Acceptance:**
- Correctly preview the single-layer Novice and multipart Orc Skeleton death/other actions without flattening away moving layers or alpha variations.
- Preview transforms and timing can be compared with independent native captures or a verified renderer reference; differences are documented, not hidden.
- Export reference filmstrips/diagnostics; report unsupported rendering semantics explicitly. A `PREVIEW_PARTIAL` or `PREVIEW_UNVERIFIED` view cannot be represented as native-parity proof; an operator may still record a provisional art review.

### M3 — Local operator workbench MVP

**Purpose:** Make the requirements engine genuinely usable by a human before adding new ingestion complexity.

**Scope:** Local web app over stable Python service/API; create/open/import project, select target/profile, requirements tree including unspecified topology, missing/invalid/unreviewed filters, action/view/frame/layer inspector, visual preview/timeline and preview-fidelity labeling, manual assignment to existing resource images, scoped pre-build composition approval, export checklist/report, save/reopen projects. Filesystem-first; localhost by default. Enforce safe local-origin requests, unsafe-method protection, upload bounds and path containment from first server implementation (§8).

**Acceptance:**
- Operator imports private Novice or Orc fixture via local UI, sees exact counts, selects a missing target requirement, assigns or reuses existing art, previews and explicitly approves the scope.
- Refresh/reopen preserves project, mappings and reviews; source, layer, transform, timing or preview-semantic edits invalidate **relevant** composition approvals. Approval exists independently of the eventual build hash.
- Every UI state is backed by the same core API/CLI validators; no fake green completion when source art or mapping is missing.

### M4 — PNG sequence/spritesheet ingestion and explicit asset assignment

**Purpose:** Accept new human-supplied artwork and associate it reliably with the already known finite contract.

**Scope:** PNG import with hashes, transparency, image sequence ordering and explicit frame mapping; spritesheet rectangle/cell import; staging repository; optional operator-requested crop, flip, scale, alignment, matte/background removal and palette conversion as versioned reversible processing recipes; batch assignment and review with after-preview; no invented frames or automatic aesthetic correction. Make **one bounded Walk action** (for example eight declared views × six frames, with explicitly declared layer topology) the first operator exercise; PNGs may originate from external tools and video extraction without adding native video ingestion yet.

**Acceptance:**
- Assigned external images occupy exact declared action/view/frame/layer IDs. Missing views remain visibly missing.
- Invalid frame order, wrong file hash, out-of-bounds sheet crop, invalid dimensions or transparent input where opaque is required produce precise errors.
- Reimport same sources/settings produces identical staged hashes; operator sees and approves each transformation class.
- A supplied shirt/monster pose is not labeled aesthetically valid merely because its file parses.
- Bounded **Walk** acceptance: after declaring action/views/frame counts/layers *before image import*, assign a sequence to exact slots, inspect/approve the composition revision, and see precise gaps. If only one view is supplied, complete only its **explicitly declared narrow scope**; other required views remain missing from the full-profile report. No claim of playable compiled output until M5.

### M5 — Modified SPR/ACT compilation and first authoring-to-native vertical slice

**Purpose:** Complete the core product success scenario from operator-supplied images to valid playable assets.

**Scope:** Generic writer for validated artwork assignments and ordered ACT layers; retain original raw metadata when replacing targeted occurrences; safe pool/index remapping, image reuse policies, anchors/timing/events, explicit RGBA conversion and preserved indexed original path; output compatibility profile; deterministic builds and content-addressed cache/atomic publication per §4.6; independent Rust decode; native smoke harness with **exact action/slot resolution evidence** per §4.7. Maintain complete/partial export separation. The compiler consumes the approved visual-composition revision, not a future build hash.

**Acceptance:**
- Complete the **bounded Walk vertical slice** begun in M4: declare action/views/frame counts/layers before artwork, assign PNG sequences and approve their composition revision, compile deterministically, independently decode and verify actual requested Walk/view/ACT slot in the pinned Korangar harness. Use a **synthetic, legally distributable test monster**; standard reachable native action views must resolve exactly. A *smaller-than-runtime-profile* scope may be exported for isolated diagnostic/harness playback, but cannot receive full-profile production or native-verified claims if the runtime selects fallbacks.
- Two clean builds of unchanged canonical composition inputs produce exactly matching SPR/ACT hashes; build metadata/evidence timestamps do not perturb artifact bytes. Recompilation after changing one approved source correctly identifies the affected approval scope.
- Import/replace a bounded Novice action without changing unrelated ACT slots/head resources; classic fallback behavior remains outside Forge's completeness claim.
- Real Orc Skeleton multilayer package can be reconstructed without flattening/losing 12-layer death motion or changing transformed layer placement.
- Invalid, underspecified or unapproved required targets cannot be emitted as approved production resources; output hashes and evidence recorded. `ASSET_LOADED` alone never satisfies native Walk/action acceptance.

### M6 — Video ingestion and operator-reviewed frame selection

**Purpose:** Accept Google Flow or any locally supplied video as **candidate imagery**, without treating video generation as authoritative.

**Scope:** Optional FFprobe/FFmpeg source metadata, input content hash, display-order decoded frames and PTS, source fps/VFR information, timeline, operator keyframe selection, explicit mapping to required action/view/frame IDs, manual placement/crop/alpha choices and preview of converted sequence. Separate video source PTS from selected ACT/runtime playback timing. Reuse existing LWR video hashing/PTS/landmark experiments *selectively*, not as standalone modules.

**Acceptance:**
- Reimport same video decodes/stages identically with pinned decoding settings; selected frame hashes and timestamps preserved.
- Operator selects and approves video-derived frames for one already declared Walk action/view, routes them through the **same image-assignment and M5 compilation path**, and previews/compiles the narrow scope where supported. Missing other views remain missing and cannot be falsely inferred; native proof is separately recorded if performed.
- Variable-frame-rate video retains correct PTS; skipped/dropped/duplicated candidate frames are visible in diagnostics.
- Forge never invents missing pose frames or guarantees anatomy/style consistency; operator remains visual authority.

### M7 — Broader profiles: jobs, attachments, costume/animation variants

**Purpose:** Demonstrate generality beyond Novice/monster without turning the core into a class-specific art generator.

**Scope:** Import representative additional body/job and weapon/attachment reference pairs; profile registry and compatibility matrix; body/head and conventional equipment attachments where the frozen client actually supports them; target-specific action families, alternate body styles and new action declarations with explicit runtime support state. Design a *separate* optional clothing-composition adapter over approved assets; don't force garment segmentation into the base compiler.

**Acceptance:**
- At least two non-Novice job reference profiles with different asset/action/equipment properties can be inspected and planned with no schema redesign; additional job fixtures chosen only from locally available lawful sources.
- A gameplay-job versus visual-outfit mismatch or missing weapon action is reported as a compatibility issue, not automatically solved by filename substitution.
- New Guard/Dodge offline actions can be declared and compiled where format permits, but runtime compatibility remains `UNSUPPORTED` until a separately verified Korangar action mapping exists.
- Any optional clothing work uses operator-approved artwork; no auto redraw or invisible fallback counting as coverage.

### M8 — Release hardening, documentation, packaging and UX refinement

**Purpose:** Make the standalone human tool reliable, maintainable and reasonably secure.

**Scope:** User guide with complete existing/new actor workflow, error catalog, compact example project using synthetic art, project migration/backups, responsive UI, keyboard/batch operations, long-running import/build progress and cancellation, portable CLI releases, CI matrix, fixture/license separation, input safety limits, persistent artifact provenance and reproducible releases. Include an offline-only tutorial path labeled `NATIVE_UNVERIFIED` and a separate runtime-verified acceptance path.

**Acceptance:**
- Clean install plus offline tutorial: synthetic monster requirements → missing checklist → supplied image/video assets → human approval → deterministic compile → independent verify. A tutorial without native proof must say `NATIVE_UNVERIFIED`; **runtime-verified release acceptance** additionally requires the pinned Korangar exact-action test.
- No proprietary Ragnarok assets or GRF archive in public distribution; explicit license/provenance review for extracted source modules and external dependencies.
- Corrupt/untrusted inputs are bounded by limits; errors do not crash/delete source projects or produce mislabeled approved outputs.
- Operator can use the tool without reading JSON or invoking the CLI for ordinary jobs, while CLI scripts remain equivalent.

---

## 7. Cross-milestone engineering acceptance matrix

| Guarantee | M0 | M1 | M2 | M3 | M4 | M5 | M6 | M7–8 |
|---|---|---|---|---|---|---|---|---|
| Source format inventory / hashes | **Required** | Extend | Used | Exposed | Used | Used | Used | Regression |
| Finite action/view/frame/**layer topology** requirements | Baseline, underspecified detectable | **Generalized; exact topology required** | Used | **Operator visible** | Bounded Walk | Gate | Used | Extend |
| Multilayer references / transforms | Inspect | Assign | **Preview** | Display | Assign | **Compile** | Used | Extend |
| Full vs scoped coverage distinction | Baseline | **Complete** | Display | **UI gate** | Gate | **Export gate** | Gate | Regression |
| Pre-build composition approval | Model only | Ledger | Preview semantics | **Workflow** | Walk assignment | **Export gate** | Video reuse | Refine |
| Image/sheet import / Walk vertical slice | Fixture only | Plan | Preview | Original assets | **Walk assignment** | **Walk compile/native** | Reuse | Refine |
| Video import / reviewed PTS | No | Contract only | No | No | No | No | **Supported** | Refine |
| Independent Rust verification | **Required** | Regression | Cross-check | Available | Used | **Required** | Required | Regression |
| Native Korangar verification | **M0-N separate gate** | Not a planner blocker if M0-S/I pass | Fidelity parity or explicit limitation | Optional | Optional | **Exact slot/action Walk proof** | Scoped video evidence | Regression |
| Multi-job expansion | Novice baseline | Schema supports | Preview as available | Select profile | Import | Compile generic | No new rules | **Prove** |

Technical/coverage approval alone never equals artistic or native acceptance. A build with a failed native check stays available for diagnostics but not marked runtime verified.

**Dependency/acceptance matrix for M0:** `M0-S` = structural inventory/preservation, `M0-I` = independent Rust parity, `M0-N` = pinned native exact-action evidence. Full `M0_PASS` requires **S + I + N**. If **S + I** pass and native is environment-blocked (not a demonstrated asset/code defect), M1 requirements planning can proceed with `M0_PARTIAL_NATIVE_UNVERIFIED`. M2 may deliver a visibly limited preview but cannot claim native parity without comparison. M5's runtime-verified acceptance requires its own exact-action native proof. A native failure implicating structural correctness blocks reliance on that affected implementation pending root-cause correction. The implementer fixes failed bounded paths; the reviewer verifies independently.

---

## 8. Security, reproducibility and licensing

1. **Local-first, deliberate network exposure:** Default web UI bound to loopback; any LAN access requires separately implemented authentication/TLS/origin protections. **M3 must still enforce local origin/Host validation, CSRF protection on state-changing HTTP operations, file upload limits and path containment from day one**; localhost is not itself a protection against malicious local-web requests. Do not embed a public network listener by default.
2. **Untrusted input bounds:** Validate SPR/ACT sizes, counts, offsets, dimensions, layer counts, decompression ratios and maximum decode budgets before allocating. FFmpeg import runs with explicit arguments, time/resource limits and isolated staging. Never use shell interpolation or execute project-defined commands.
3. **Path safety:** Store imported files under isolated project paths; reject path traversal, overwrites, symlink escapes, duplicate collisions and intentionally malformed manifests.
4. **File integrity and reproducibility:** SHA-256 source, composition and artifact hashes; dependency/runtime/profile versions, canonical settings, deterministic serialization rules (§4.6), pre-build approval binding and separate non-hashed native evidence; atomic writes to avoid partially published builds.
5. **Source ownership:** Do not publish Gravity Ragnarok original art just because it is locally present; synthetic redistributable fixtures for public CI and demos. Confirm LWR-owned code licensing before copying untracked tools. Preserve notices for permissive code; avoid copying unresolved ActEditor sources or GPL components into an MIT package without deliberate licensing.
6. **Failure handling:** No irreversible mutations to original files, no silent fallback pass, no automatic normalization of unknown ACT fields, and no use of artistic confidence scores as validation.

---

## 9. Risks and decisive experiments

| Risk | Why it matters | Evidence-first response |
|---|---|---|
| **False completeness** via Korangar modulo/fallback | A loadable actor may play wrong action/direction | Verify requested vs resolved numeric ACT slot using §4.7; treat fallback animation as diagnostic, not native proof. |
| **Novice-only modeling** | Multipart Orc death and other actor layouts break flat-frame assumptions | Require M0 Orc inventory, M2 multilayer preview, M5 transformed multilayer compilation. |
| **Indexed palette loss** | Recoloring/custom clients may depend on original indexed pixels | Preserve original raw SPR bytes; explicit conversion opt-in with reported palette loss. |
| **Incorrect image count/effort prediction** | Unique SPR identity ≠ unique content ≠ layer occurrences ≠ reusable garment art | Demand explicit/inherited target layer topology and show each cardinality; count only approved declared reuse as fulfilled requirements. |
| **False confidence from shared codec** | Compiler reader/writer share errors | Independent Rust decoder early; native verification after output. |
| **Preview differs from actual runtime** | Operator approves a misleading result | Version pre-build preview semantics; compare against pinned Korangar behavior, especially Orc transforms/head attachment; label partial review as provisional. |
| **UI complexity overwhelms operator** | Repeats LWR governance/UI maze failure | Requirements-first single workspace, batch assignments and review, no dashboard-first architecture; validate Walk assignment as first bounded operator workflow. |
| **Unstable external video output** | Pose drift, matte errors and unpredictable frame quality | Operator selects/approves actual frames; Forge reports deterministic mapping and never invents replacements. |
| **Uncommitted LWR source provenance** | Reuse may be incomplete or cannot be published | Pin file hashes, independent tests, ownership/license confirmation; no implicit live LWR dependency. |
| **Overexpanding format compatibility** | Original RO clients and alternate format versions multiply validation burden | Pin Korangar + SPR 2.1/ACT 2.4 initially; later profiles added only with fixtures/tests. |

**Stop-and-correct rule:** If a milestone's critical acceptance test fails, correct the affected bounded path before *relying on it* or claiming that gate passed. A documented, environment-blocked native test may coexist with verified independent structural work under the §7 partial-state rule; an actual suspected codec/action-selection defect cannot be bypassed. No generic new subsystem or lengthy audit substitutes for missing artwork, a broken compiler or absent runtime evidence.

---

## 10. Decisions and remaining questions

### 10.1 Recommended defaults for planning (proposed, not yet product code)

- **Scope:** Standalone local human tool; Korangar-first, original-client parity deferred.
- **Code:** Python core; pinned Rust independent decoder for verification; optional FFmpeg adapter for video.
- **Formats:** initial audited SPR 2.1 and ACT 2.4; reject unsupported versions explicitly.
- **Profiles:** player/NPC/monster runtime profiles separate from resource inventory, target and assignments; arbitrary job-family identities supported by data, not hardcoded enumerations.
- **Preservation:** exact unmodified import/export by default; explicit RGBA conversion with provenance, no automatic destructive palette rewrite.
- **Approval:** operator exclusively owns visuals; pre-build approvals bind to canonical composition revisions and preview semantics, not future artifact hashes; no AI generator embedded.
- **Incomplete work:** report/preview allowed; production export blocked for underspecified/missing/invalid/unreviewed required items. Narrow diagnostic builds conspicuously labeled partial and do not imply full runtime compatibility.
- **Projects:** filesystem + versioned JSON; local web UI after core and preview; no database or task tracker.

### 10.2 Material open questions with the earliest decision point

| Question | Default / resolution path | Blocking point |
|---|---|---|
| Which exact Korangar executable/build is normative? | Start audited primary checkout, pin binary/build hash in M0 fixture test; report native result separately from M0 structural and independent gates. | **M0-N native proof; M5 exact-action verification** |
| How much indexed SPR representation must be rewritten? | M0 unchanged pass-through exact; generic indexed *authoring* deferred. | M5 conversion/export policies |
| How to verify visually complex layer transforms? | M2 independent preview/native comparison for Orc Skeleton; accept explicit limitations until proven. | M2 |
| Which runtime actor/event profiles represent individual jobs? | Import first, freeze mapping per actor and build; collect representative extra classes in M7. | M1 semantics / M7 expansion |
| Which local web stack? | Choose small Python API + lean JS canvas client using a time-boxed prototype; enforce loopback-origin/Host/CSRF/path protections at first M3 implementation. | M3 |
| What can be redistributed? | Synthetic fixtures publicly; local real art by operator path and hash; review source-code rights before repository publication. | Before public release; code extraction M0 |
| What video formats and codecs? | Use FFprobe/FFmpeg compatibility set and project-specific decode limits, selected from actual sample inputs. Until M6, external video extraction may supply operator-selected PNGs to M4/M5. | M6 |
| Do new actions require Korangar changes? | Unmapped extension is offline/unsupported until separately integrated and verified. | M7/runtime feature request, not M0 |

No question above justifies another LWR-wide audit before beginning the standalone M0 implementation. **v1.1 settles layer-topology policy, build determinism, and pre-build approval semantics in the specification**; their implementation details should be tested against synthetic fixtures rather than escalated into fresh architecture exercises.

---

## 11. Proposed repository layout

```text
ro-sprite-forge/
├── pyproject.toml
├── README.md
├── LICENSE                  # after source/license review
├── src/ro_sprite_forge/
│   ├── cli.py
│   ├── core/
│   │   ├── models.py
│   │   ├── errors.py
│   │   ├── provenance.py
│   │   └── project_store.py
│   ├── formats/
│   │   ├── act.py
│   │   └── spr.py
│   ├── inventory/
│   ├── profiles/
│   ├── planning/
│   ├── assignments/
│   ├── preview/
│   ├── ingest/
│   │   ├── images.py
│   │   └── video.py            # M6, optional dependency
│   ├── compile/
│   ├── verify/
│   └── web/                    # M3, optional runtime adapter
├── frontend/                 # M3 local operator UI
├── schemas/
├── profiles/                 # versioned runtime profile data
├── tests/
│   ├── synthetic/
│   ├── private_fixture_hooks/
│   ├── unit/
│   └── integration/
├── tools/
│   ├── rust-oracle/           # pinned independent decoding harness
│   └── korangar-smoke/       # separate native proof recipe
├── examples/                 # synthetic assets only
└── docs/
    ├── operator-workflows.md
    ├── format-policies.md
    ├── composition-and-determinism.md  # canonical hash/approval contract
    └── implementation-decisions.md
```

Create directories only as their milestone first uses them; the layout is a target, not an instruction to scaffold all folders immediately.

---

## 12. Proposed CLI and operator outputs

Commands below are **planned interfaces, not implemented commands**:

```bash
# Import a known reference and inspect actual structure
ro-sprite-forge inspect --act body.act --spr body.spr --json inventory.json

# Compare actual resources to a pinned runtime profile and declared target
# M0 basic/structural planning; M1 full frame-and-layer contract
ro-sprite-forge plan --inventory inventory.json \
  --profile korangar-monster-v1.json --target monster-target.json \
  --output requirements.json

# Show exact unresolved requirements (including underspecified topology) before drawing — M1+
ro-sprite-forge missing --project ./monster-project --format table

# Validate operator assignments and review states
ro-sprite-forge verify --project ./monster-project --scope full

# Compile only if specified structural/coverage/pre-build approval gates pass — M5+
ro-sprite-forge build --project ./monster-project --output ./dist

# M6 optional: stage video as candidate source frames; does not auto-assign art
ro-sprite-forge video import --project ./monster-project --source walk.mp4
```

Example **illustrative** response (fake counts for a future target, not audited Orc Skeleton state):

```text
TARGET: custom-monster-v1 / Korangar Monster
ACTION: Walk, VIEW: 3, EXPECTED FRAMES: 6
Declared layer topology: explicit one-layer-per-frame
Required frame occurrences: 6
Required layer occurrences: 6
Assigned valid artwork:   4
Missing:                  2
Needs human visual review: 1
ACT timing policy:        Korangar monster Walk (profile-pinned)
Status:                   INCOMPLETE_FOR_DECLARED_SCOPE
NEXT:
- walk:view3:frame4 -> MISSING
- walk:view3:frame5 -> MISSING
- walk:view3:frame2 -> VISUAL_REVIEW_PENDING
```

A complete output package includes the compiled file pair(s), requirements/assignment snapshot, canonical approved **pre-build visual-composition digest**, source hashes, deterministic build manifest, structural/coverage checks, decoder-oracle result and **separate** native evidence record including exact action-resolution status. `NOT_RUN`, `UNVERIFIED`, `ASSET_LOADED`, and `FALLBACK_OBSERVED` are not `REQUESTED_ACTION_VERIFIED`.

---

## 13. Immediate next engineering assignment: M0 only

**Worker:** Codex CLI implementer; Python game tooling / binary formats engineer. Use a high-capability model at medium reasoning by default and escalate only for concrete binary-format or cross-language debugging, not as a substitute for missing inputs. Reviewer independently tests; implementer corrects failures; operator makes final adoption decision.

**First task boundaries:** Create new standalone repository only when the operator authorizes; inspect/pin selected LWR codec sources, move tests to synthetic and private-fixture hooks, implement inventory/basic requirements CLI and byte preservation vs parse/serialize verification as separate tests, Rust independent decoder, and native exact-slot verification recipe. Do not scaffold M3 UI, M6 video, modular clothing production or job roster until their milestone. No changes to LWR, rAthena or Korangar beyond separate isolated verification fixtures without explicit scope.

**M0 completion packet:**

1. Installable package + version/lock and executable CLI.
2. Inventory reports for exact Novice/Orc fixtures reproducing audited figures.
3. Separate byte-preserving raw import/export evidence and ACT parse/serialize/parse equivalence evidence, plus explicit indexed-to-RGBA limitation.
4. Independently decoded canonical inventory comparison, including negative cases.
5. Pinned Korangar native smoke evidence with exact output hashes, requested/resolved ACT action-view slot and fallback status—or explicit `M0_PARTIAL_NATIVE_UNVERIFIED` result.
6. Clean repository diff, source provenance/license notes, reproducible invocation and concise next-work gap list.

**No automatic M1/M2 start without operator direction.** After M0-S and M0-I pass, M1 may begin even if environment-blocked M0-N remains `UNVERIFIED`, provided no known native failure implicates correctness. Do not label M0 fully accepted until all gates pass; do not commission a redundant architecture review.

---

## 14. Final product acceptance test

The standalone tool is ready for meaningful operator adoption only when a human can complete this exercise without writing a program or manually editing a large JSON file:

1. Create a new monster project and select/define the exact animation/runtime profile and **explicit or inherited ordered layer topology**.
2. See finite required actions/views/frames/layers, their declaration provenance and existing reuse *before* generating artwork; an unspecified topology shows a blocking underspecified diagnostic, not an invented exact workload.
3. Export a concrete missing-artwork work order suitable for external visual production.
4. Import supplied PNGs, spritesheets or video, manually assign selected frames to required slots, and explicitly approve their **pre-build composition revision**; incomplete preview fidelity is visible.
5. Preview actions and directions with faithful transforms, anchors and playback, with missing/unsupported elements visible.
6. Export a complete, deterministic SPR/ACT resource only when objective gates and applicable human approval are satisfied; two clean builds with identical canonical inputs produce identical artifact hashes.
7. Validate the result through independent decoding and record native Korangar **exact requested-action/view/slot resolution** separately from load success and fallback behavior.
8. Reopen the project, replace one source frame and see **only affected** stale approvals, changed canonical composition/build hashes and exact affected requirements; rebuild deterministically after reapproval.
9. Demonstrate the **M4–M5 bounded Walk vertical slice** from a frame/layer checklist through approved external PNGs to compiled output and native exact-action verification. A narrow one-view diagnostic remains explicitly incomplete for the wider profile.

If that succeeds for a synthetic new monster and remains correct for the real audited Novice/Orc Skeleton fixtures, **RO Sprite Forge has solved the specific recurring LWR workflow failure: unknown production requirements discovered only after art creation or integration.** This is the product's main measure of success, not the number of features, passing tests or pages in its UI.
