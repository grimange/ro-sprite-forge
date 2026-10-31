# RSF-32 Verification Plan — Additional Job/Body Profiles and Compatibility Registry

## 1. Context and Objective

**Task:** RSF-32 — `[M7] Additional job/body profiles and compatibility registry`  
**Internal ID:** `wbh6jvha6imo9jeub9zmhovj`  
**Milestone:** M7 (Initial Task)  
**Parent Project:** RO Sprite Forge (`oq6fp33cmdnwl5h0v48zcr3u`, `RSF`)  
**Workspace:** Personal Projects (`30VyoMQZ4LROnW3UUeAYGg8bIF9mj1il`)  
**Assignee:** `AGY` (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)  
**Dependencies:** RSF-26 (Accepted), RSF-10 (Accepted)

The objective of RSF-32 is to implement a data-driven, versioned compatibility registry for Ragnarok job/body ACT/SPR profiles, demonstrating generality beyond Male Novice and monster archetypes without schema redesign, without hardcoded class assumptions, and without claiming visual or native completion that has not been performed.

---

## 2. Invariants and Constraints

1. **Separation of Authorities:**
   - **Observed resource inventory:** Exact counts of action groups, numeric slots, frame occurrences, layers per frame, and image pools.
   - **Pinned runtime semantics:** Korangar engine mapping (e.g. 13 player actions, 8 views, anchor offsets).
   - **Operator-declared target:** Finite scope and requested work orders.
   - **Artwork assignment ledger:** Explicit source-to-layer bindings with no automatic infill.
2. **No Novice Quota Imposition:** Non-Novice jobs (e.g. companion with 16 slots, shield with 448 motions, multi-layer frames) retain their actual resource topology.
3. **Truthful Compatibility Dimensions:**
   - `format_decoding`, `inventory`, `runtime_mapping`, `requirements`, `assignment`, `preview`, `compilation`, `independent_rust`, `native_korangar`.
   - Distinct statuses: `VERIFIED`, `PARTIAL`, `UNSUPPORTED`, `UNVERIFIED`.
   - No automatic native verification claim for newly registered resources.
4. **Deterministic Serialization:** Stable canonical JSON hashes, sorted profile IDs, no machine paths or timestamps.
5. **Private Resource Protection:** Proprietary artwork remains external; public tests rely on synthetic fixtures or pinned metadata.

---

## 3. Discovered Reference Profiles

1. **Genetic Female Costume 1 Body (`genetic-female-body-v1`):**
   - Source: `data\sprite\인간족\몸통\여\costume_1\제네릭_여_1` in local `data.grf`
   - ACT 2.4 SHA-256: `27744afbed3b1fbca5a6cc3d012ced93b11559c45936465312c1cad67c931d34`
   - SPR 2.1 SHA-256: `8130fe1646f0284f40b32c9118959334d480d75f70ace581d17f0e3b1300982c`
   - 104 action slots, 456 motion occurrences, 122 indexed images (distinct from Novice 110 pool), 1 head anchor.
2. **Dragon Knight Male Shield (`dragon-knight-male-shield-v1`):**
   - Source: `data\sprite\방패\dragon_knight\dragon_knight_남_쉴드` in local `data.grf`
   - ACT 2.4 SHA-256: `c2175126b1357374b148f7da24eecb12de0a4ba5fb21e2330cb90e877fe176c9`
   - SPR 2.1 SHA-256: `0b78157535438592c0572c55b5f870bd7b4a762ac344d7cf01703cb0a89558f4`
   - 104 action slots, 448 motion occurrences (distinct from 456 standard body motions), 2 indexed images, 0 anchors.
3. **Falcon Companion (`falcon-companion-v1`):**
   - Source: `data\sprite\몬스터\매` in local `data.grf`
   - ACT 2.4 SHA-256: `ac258085c313b566aa004a5a536a73578bd6a32033b7fb99331b2057dd83ad87`
   - SPR 2.1 SHA-256: `dce42bfa285251f17b7bd05ad824cb5f9f329ebf62ac1f0eb7f082f2e788dfae`
   - Non-standard 16 slots (2 action groups x 8 views), 72 motion occurrences, 45 indexed images, 0 anchors.
4. **Synthetic Swordsman (`synthetic-swordsman-v1`):**
   - Public synthetic redistributable profile with 13 groups, 104 slots, 456 motions, multi-layer topology (`['torso', 'pauldrons']`).

---

## 4. Verification Matrix (25 Points)

Covering all items from Section 19 of the brief:
- Existing Novice profile unchanged
- Existing Orc Skeleton profile unchanged
- Additional real reference discovery
- Source-hash validation
- ACT/SPR version recognition
- Canonical resource inventory
- Action-slot count correctness
- Frame occurrence correctness
- Ordered layer topology
- Referenced vs stored images
- Indexed/truecolor image inventory
- Body/head relationship handling
- Runtime mapping correctness
- Unknown mapping classification
- Compatibility-registry schema validation
- Duplicate registry ID rejection
- Registry source-revision mismatch
- Deterministic registry serialization
- Requirements resolution from a registered profile
- Coverage and missing-work generation
- Unsupported capability classification
- No false compilation claim
- No false native verification claim
- Independent Rust verification where supported
- Private-source exclusion from public artifacts
