# RSF-32 Implementation and Verification Report

## 1. Executive Summary

- **Ticket:** RSF-32 — `[M7] Additional job/body profiles and compatibility registry`
- **Internal ID:** `wbh6jvha6imo9jeub9zmhovj`
- **Milestone:** M7
- **Assignee:** `AGY` (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)
- **Status:** Verified and Ready for Independent Review (`in-review`)

RSF-32 establishes the versioned, data-driven compatibility registry (`rsf.compatibility-registry/v1`) for Ragnarok sprite assets. It audits and integrates multiple real non-Novice job and equipment resources from lawful local archives, preserves distinct action and slot topologies without forcing Novice assumptions, connects seamlessly to the RSF-8 requirements resolver and RSF-10 coverage engine, and provides complete independent verification via Python and the Rust oracle.

---

## 2. Acceptance Criteria Checklist

| Acceptance Criterion | Status | Evidence / Verification |
|---|---|---|
| **1. Inspect/plan at least two non-Novice job reference profiles with different asset/action/equipment properties without schema redesign** | **MET (`[x]`)** | Audited `genetic-female-body-v1` (122 indexed sprites), `dragon-knight-male-shield-v1` (448 motions, 0 anchors), `falcon-companion-v1` (16 slots, 72 motions), and `synthetic-swordsman-v1` (multilayer). |
| **2. Separate gameplay job, body/sex/style/variant identity, action family and compatibility; do not force Novice counts/mapping onto other jobs** | **MET (`[x]`)** | Data-driven separation of `gameplay_job`, `visual` (`body_family`, `sex`, `body_variant`, `costume`), `actions`, `topology`, and `compatibility`. Falcon has 16 slots; shield has 448 motions. |
| **3. Reference pairs remain external and hash-pinned; unknown semantics and locally unavailable lawful fixtures are explicit** | **MET (`[x]`)** | Source hashes pinned to exact SHA-256; private fixtures stay in external `data.grf`; unmapped actions explicitly classified as `UNSUPPORTED` / `PARTIAL`; native Korangar remains `UNVERIFIED`. |
| **4. Profile revisions preserve inventory and target/ledger provenance and extend existing structural/oracle regressions** | **MET (`[x]`)** | Full compatibility with `resolve_topology` and `evaluate_coverage`; 25-point verification matrix passed; Rust oracle verified with returncode 0 on all audited pairs; 564 public tests PASS. |

---

## 3. Evidence and Test Results

| Suite | Command | Result | Evidence File |
|---|---|---|---|
| **Focused Matrix (25 points)** | `PYTHONPATH=src .venv/bin/python -m unittest tests/test_profile_registry.py -v` | **25 PASS, 0 FAIL** | `docs/verification/rsf-32/focused.log` |
| **Public Regressions** | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | **564 PASS, 0 FAIL** | `docs/verification/rsf-32/public.log` |
| **Private Fixtures** | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | **43 PASS, 1 SKIP, 0 FAIL** | `docs/verification/rsf-32/private.log` |
| **All Schema Checkers** | 12 `scripts/check_*schema*.py` scripts via `.venv/bin/python` | **12 PASS, 0 FAIL** | `docs/verification/rsf-32/schemas.log` |
| **Isolated Distribution** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | **564 PASS, 12 SKIP, 0 FAIL** | `docs/verification/rsf-32/distribution.log` |

---

## 4. Audited Reference Profiles

### 4.1 Genetic Female Costume 1 (`genetic-female-body-v1`)
- **Category:** Player Body (`body`)
- **Gameplay Job:** `genetic`
- **Sex / Costume:** `female` / `costume_1`
- **ACT Version / Size:** 2.4 / 44,628 bytes
- **ACT SHA-256:** `27744afbed3b1fbca5a6cc3d012ced93b11559c45936465312c1cad67c931d34`
- **SPR Version / Size:** 2.1 / 18,348 bytes
- **SPR SHA-256:** `8130fe1646f0284f40b32c9118959334d480d75f70ace581d17f0e3b1300982c`
- **Topology:** 13 action groups, 104 slots, 456 motion occurrences, 1 layer per frame, 1 head anchor point per frame.
- **Image Pool:** 122 indexed images, 0 RGBA images, 122 distinct contents (distinct from Novice 110 pool).
- **Rust Oracle:** Verified (`returncode=0`).
- **ACT Preservation:** Byte-exact round trip confirmed.

### 4.2 Dragon Knight Male Shield (`dragon-knight-male-shield-v1`)
- **Category:** Player Shield Equipment (`shield`)
- **Gameplay Job:** `dragon_knight`
- **Sex:** `male`
- **ACT Version / Size:** 2.4 / 36,692 bytes
- **ACT SHA-256:** `c2175126b1357374b148f7da24eecb12de0a4ba5fb21e2330cb90e877fe176c9`
- **SPR Version / Size:** 2.1 / 892 bytes
- **SPR SHA-256:** `0b78157535438592c0572c55b5f870bd7b4a762ac344d7cf01703cb0a89558f4`
- **Topology:** 13 action groups, 104 slots, 448 motion occurrences (distinct from 456 body motions), 1 layer per frame, 0 anchor points.
- **Image Pool:** 2 indexed images, 0 RGBA images, 2 distinct contents.
- **Rust Oracle:** Verified (`returncode=0`).
- **ACT Preservation:** Byte-exact round trip confirmed.

### 4.3 Falcon Companion (`falcon-companion-v1`)
- **Category:** Companion (`companion`)
- **Gameplay Job:** None (`null`)
- **Body Family:** `falcon`
- **ACT Version / Size:** 2.4 / 5,908 bytes
- **ACT SHA-256:** `ac258085c313b566aa004a5a536a73578bd6a32033b7fb99331b2057dd83ad87`
- **SPR Version / Size:** 2.1 / 18,976 bytes
- **SPR SHA-256:** `dce42bfa285251f17b7bd05ad824cb5f9f329ebf62ac1f0eb7f082f2e788dfae`
- **Topology:** 2 action groups, 16 slots, 72 motion occurrences, 1 layer per frame, 0 anchor points.
- **Image Pool:** 45 indexed images, 0 RGBA images, 45 distinct contents.
- **Rust Oracle:** Verified (`returncode=0`).
- **ACT Preservation:** Byte-exact round trip confirmed.

---

## 5. Compatibility Matrix

| Profile ID | Decoding | Inventory | Runtime Mapping | Requirements | Assignment | Preview | Compilation | Rust Oracle | Native Korangar |
|---|---|---|---|---|---|---|---|---|---|
| `novice-male-body-v1` | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** |
| `novice-male-head-v1` | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** |
| `orc-skeleton-v1` | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** |
| `genetic-female-body-v1` | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **UNVERIFIED** |
| `dragon-knight-male-shield-v1` | **VERIFIED** | **VERIFIED** | **PARTIAL** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **UNVERIFIED** |
| `falcon-companion-v1` | **VERIFIED** | **VERIFIED** | **PARTIAL** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **UNVERIFIED** |
| `synthetic-swordsman-v1` | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **VERIFIED** | **UNVERIFIED** |

---

## 6. RSF-8 and RSF-10 Integration

The profile registry provides translation methods `to_runtime_profile_contract(profile)` and `to_actor_contract(profile)` that produce valid, immutable `rsf.runtime-profile/v2` and `rsf.actor/v1` instances.

When consumed by `resolve_topology(...)` (RSF-8):
- Non-Novice profiles resolve exact slot counts (e.g. 16 for Falcon, 104 for Swordsman/Shield).
- Custom frame and layer counts are preserved (e.g. 5 frames, 2 layers per frame).
- Unmapped actions produce clean diagnostics without crashing or inventing defaults.

When evaluated by `evaluate_coverage(...)` (RSF-10):
- Exact missing artwork work orders are generated with requirement IDs incorporating topology digests.
- Accounting invariant holds: `required occurrences = assigned + unassigned + other`.
