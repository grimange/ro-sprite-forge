# Independent QA Review Report — RSF-32: Additional Job/Body Profiles and Compatibility Registry

- **Task Ticket:** RSF-32
- **Internal ID:** `wbh6jvha6imo9jeub9zmhovj`
- **Milestone:** M7
- **Reviewer:** Independent QA Reviewer (Read-Only Session)
- **Implementer:** `AGY` (`ICJQmirJliEFAZN3jBl3ZitHCandT0FG`)
- **Review Date:** 2026-10-31
- **Verdict:** **QA_PASS**

---

## 1. Executive Summary

This independent quality assurance review evaluates task **RSF-32** ([M7] Additional job/body profiles and compatibility registry). The implementation introduces a versioned, data-driven compatibility registry (`rsf.compatibility-registry/v1`) that captures job, body, equipment, and companion ACT/SPR resource definitions without forcing Male Novice topology or monster assumptions.

All 4 acceptance criteria have been independently validated. All recommended inspection commands and verification suites have been executed with zero failures:
- **Focused Matrix (25 points):** 25 passed, 0 failed.
- **Public Test Suite:** 564 passed, 0 failed.
- **Private Fixture Hooks:** 43 passed, 1 skipped (native corridor), 0 failed.
- **Schema Validation Scripts:** 12 of 12 passed.
- **Isolated Package Distribution:** Wheel build and isolated test execution passed (564 passed, 12 skipped, 0 failed).
- **Manifest Integrity:** All 6 implementation files and all 11 evidence files match declared SHA-256 hashes and byte lengths.

---

## 2. Independent Command Execution and Results

| Suite / Check | Command | Exit Code | Tests / Checks | Result |
|---|---|---|---|---|
| **Focused Matrix (25 points)** | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest tests/test_profile_registry.py -v` | `0` | 25 run, 0 failed, 0 skipped | **PASS** |
| **All 12 Schema Checkers** | `PYTHONDONTWRITEBYTECODE=1 bash -c 'for s in scripts/check_*schema*.py; do .venv/bin/python "$s" || exit 1; done'` | `0` | 12 scripts executed | **PASS** |
| **Private Fixtures** | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | `0` | 44 run, 43 passed, 1 skipped, 0 failed | **PASS** |
| **Distribution Check** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | 564 passed, 12 skipped, 0 failed | **PASS** |
| **Public Regressions** | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | `0` | 564 run, 564 passed, 0 failed | **PASS** |
| **Manifest Integrity** | Python SHA-256 and byte-size verification against manifests | `0` | 6 impl files, 11 evidence files | **PASS** |

*Note on Skipped Tests:*
1. `test_native_rsf6_structural_parity`: Skipped because `/tmp/rsf6-native-run-final-1` native corridor evidence is an environment-specific M0 artifact not part of this task.
2. In distribution check, 12 tests are skipped because the Rust oracle binary and local GRF are not bundled into the isolated public distribution wheel (correct behavior).

---

## 3. Evaluation of Acceptance Criteria

### Acceptance Criterion 1: Inspect/plan at least two non-Novice job reference profiles with different asset/action/equipment properties without schema redesign
- **Status:** **MET**
- **Evidence:**
  - Audited and integrated profiles across distinct archetypes:
    1. `genetic-female-body-v1`: Female Genetic costume 1 player body, 104 slots, 456 motions, 122 indexed images (distinct from Novice 110 pool), 1 head anchor point per frame.
    2. `dragon-knight-male-shield-v1`: Male Dragon Knight shield equipment, 104 slots, 448 motion occurrences (distinct motion count from standard 456 body motions), 2 indexed images, 0 anchor points.
    3. `falcon-companion-v1`: Falcon companion, non-standard 16 slots (2 action groups x 8 views), 72 motion occurrences, 45 indexed images, 0 anchor points.
    4. `synthetic-swordsman-v1`: Public synthetic Swordsman body profile, 104 slots, 456 motions, multi-layer topology (`[1, 2]`), 64 images.
  - All profiles validate under `rsf.compatibility-registry/v1` and translate directly to standard `rsf.runtime-profile/v2` and `rsf.actor/v1` contracts without any schema alterations.

### Acceptance Criterion 2: Separate gameplay job, body/sex/style/variant identity, action family and compatibility; do not force Novice counts/mapping onto other jobs
- **Status:** **MET**
- **Evidence:**
  - `gameplay_job` is decoupled from visual geometry: `'genetic'`, `'dragon_knight'`, `'swordsman'`, and `null` (for Falcon companion and Orc skeleton monster).
  - `visual` captures identity orthogonally: `body_family` (`human_standard`, `falcon`, `monster_orc`), `sex` (`male`, `female`, `null`), `body_variant`, and `costume` (`costume_1`, `null`).
  - No quota imposition: Falcon companion preserves its actual 16-slot topology rather than being forced into 104 slots. Dragon Knight shield preserves its actual 448 motions rather than being padded to 456 motions. Orc Skeleton preserves 40 slots and multi-layer frame topology (up to 12 layers on death).
  - Compatibility dimensions are strictly orthogonal: `format_decoding`, `inventory`, `runtime_mapping`, `requirements`, `assignment`, `preview`, `compilation`, `independent_rust`, `native_korangar`.

### Acceptance Criterion 3: Reference pairs remain external and hash-pinned; unknown semantics and locally unavailable lawful fixtures are explicit
- **Status:** **MET**
- **Evidence:**
  - Exact source SHA-256 hashes are pinned for all ACT and SPR binaries:
    - Genetic female body: ACT `27744afbed3b1fbca5a6cc3d012ced93b11559c45936465312c1cad67c931d34`, SPR `8130fe1646f0284f40b32c9118959334d480d75f70ace581d17f0e3b1300982c`
    - Dragon Knight shield: ACT `c2175126b1357374b148f7da24eecb12de0a4ba5fb21e2330cb90e877fe176c9`, SPR `0b78157535438592c0572c55b5f870bd7b4a762ac344d7cf01703cb0a89558f4`
    - Falcon companion: ACT `ac258085c313b566aa004a5a536a73578bd6a32033b7fb99331b2057dd83ad87`, SPR `dce42bfa285251f17b7bd05ad824cb5f9f329ebf62ac1f0eb7f082f2e788dfae`
  - Proprietary artwork remains external in lawful local GRF archives (`data.grf`). No raw assets or machine paths are published in public artifacts or repository code.
  - `verify_source_hashes` enforces cryptographic hash equality and fails closed (`SOURCE_HASH_MISMATCH`, `ErrorCode.INVALID_INPUT`) when byte discrepancies occur.
  - If local GRF is absent, private fixture tests skip gracefully without false claims.
  - Partial runtime support is explicitly recorded: Falcon companion records `runtime_mapping: PARTIAL` because only Idle and Walk are mapped.
  - Native Korangar support for all non-Novice profiles is truthfully recorded as `UNVERIFIED` without claiming unperformed native execution.

### Acceptance Criterion 4: Profile revisions preserve inventory and target/ledger provenance and extend existing structural/oracle regressions
- **Status:** **MET**
- **Evidence:**
  - Translation functions `to_runtime_profile_contract()` and `to_actor_contract()` produce canonical, sealed contract instances compatible with RSF-8 requirements resolution (`resolve_topology`) and RSF-10 coverage auditing (`evaluate_coverage`).
  - Byte-exact preservation confirmed on real fixtures: `write_act(read_act(act_b)) == act_b` produces identical bytes for Genetic female body, Dragon Knight shield, and Falcon companion.
  - The independent Rust oracle (`tools/rust-oracle/target/debug/rsf-rust-oracle`) was executed on all three discovered real ACT/SPR pairs, passing with exit code 0 and verifying structural format parity.
  - Existing regressions (564 public tests, 43 private fixture tests) remain green with zero regressions.

---

## 4. Manifest and Checksum Verification

### Implementation Files
| Path | Expected SHA-256 | Actual SHA-256 | Status |
|---|---|---|---|
| `src/ro_sprite_forge/schemas/compatibility-registry-v1.json` | `4c0e062bc19d39f7f74bb513aacdd0d119d03232accba0a4737d836154b364f7` | `4c0e062bc19d39f7f74bb513aacdd0d119d03232accba0a4737d836154b364f7` | **MATCH** |
| `src/ro_sprite_forge/core/registry.py` | `e8ac89d40c3fc63369686a54452759be874a5bab6a8a096a4d9ffa960a3f7a19` | `e8ac89d40c3fc63369686a54452759be874a5bab6a8a096a4d9ffa960a3f7a19` | **MATCH** |
| `src/ro_sprite_forge/core/contracts.py` | `735e1138948065804f81260b270786d479f41f3b0d3f612193b85edf6973fc33` | `735e1138948065804f81260b270786d479f41f3b0d3f612193b85edf6973fc33` | **MATCH** |
| `scripts/check_registry_schema.py` | `5fb90f956185733f8e3fd49d7f0f1489920dc742751cb2251102c50d9bd62718` | `5fb90f956185733f8e3fd49d7f0f1489920dc742751cb2251102c50d9bd62718` | **MATCH** |
| `tests/test_profile_registry.py` | `96514211b0d9f865427e705eb4301558917e98d1cd3dff279ff88d7722b68fab` | `96514211b0d9f865427e705eb4301558917e98d1cd3dff279ff88d7722b68fab` | **MATCH** |
| `tests/private_fixture_hooks/test_registry_fixtures.py` | `c420b6ab63e10c3a70e1f5c90d82920bedde213432061a285539d017b60c39ce` | `c420b6ab63e10c3a70e1f5c90d82920bedde213432061a285539d017b60c39ce` | **MATCH** |

### Evidence Files
| Evidence Name | Expected SHA-256 | Actual SHA-256 | Expected Size | Actual Size | Status |
|---|---|---|---|---|---|
| `PLAN.md` | `1ee6ee36b0510da521355fce8617a2fa5fbb0316d471d3a3e682d2a0e8743a8c` | `1ee6ee36...` | 4,666 | 4,666 | **MATCH** |
| `REPORT.md` | `04501d401ec25139b080369b4f825cd9b1cf68f6af87cdc7b0de8e6d764b8c1a` | `04501d40...` | 7,774 | 7,774 | **MATCH** |
| `commands.json` | `ab64933c805ca69229331c0296e024cbad529228bb902e105450038468194dc0` | `ab64933c...` | 1,449 | 1,449 | **MATCH** |
| `distribution.log` | `6fa38f763d632726429ebbc7e054b1607111abbb1b5b8a1569afc673b826cf69` | `6fa38f76...` | 155,124 | 155,124 | **MATCH** |
| `environment.json` | `c38f29ad2933b926034b3439e59b5dde3cfb3223a010f27f04fc754a1e58880b` | `c38f29ad...` | 559 | 559 | **MATCH** |
| `focused.log` | `86f564f35b1ca8c57a0f4c8250b06c1ce6bbc65e1a73cf29210a5fed6e4ada45` | `86f564f3...` | 5,243 | 5,243 | **MATCH** |
| `implementation-manifest.json` | `19854fe719b9c7c8302a523ae5de720aa1838825e48a62569baf0f2b9de3f9ca` | `19854fe7...` | 1,208 | 1,208 | **MATCH** |
| `kaneo-start.json` | `1bba62c0225cad72297db260a01d24bcd23983f5543a6cc93c39b93a7412aeb6` | `1bba62c0...` | 516 | 516 | **MATCH** |
| `private.log` | `c709e12d1f986d4738be940b9b0918cc3494f9a57f71a485015b5840ff3d8936` | `c709e12d...` | 13,243 | 13,243 | **MATCH** |
| `public.log` | `580725c89663a411f9dc5370febfce91c6217797ef993eca185819ff603c1877` | `580725c8...` | 83,493 | 83,493 | **MATCH** |
| `schemas.log` | `355862cdce568c0478056bc3b744c5b1cd64609ef530de893f8e9b048a8e9cc6` | `355862cd...` | 1,215 | 1,215 | **MATCH** |

---

## 5. Negative Scenarios and Robustness Checks

The following negative and boundary scenarios were independently confirmed:
1. **Schema Non-Conformance:** Invalid registry schemas, missing required properties (`id`, `canonical_sha256`), out-of-range action groups, and unknown compatibility enum values are strictly rejected by `scripts/check_registry_schema.py` and `validate_registry()`.
2. **Duplicate Profile IDs:** Duplicate profile identities in registry containers trigger `ForgeError(ErrorCode.INVALID_INPUT, 'Duplicate profile ID...')`.
3. **Source Hash Discrepancies:** Modifying either ACT or SPR bytes triggers `SOURCE_HASH_MISMATCH` with `ErrorCode.INVALID_INPUT`.
4. **Unsupported Format Versions:** Attempting to register unsupported format revisions (e.g. ACT 2.5) fails closed.
5. **Sanitization:** Public test asserts that no raw artwork, GRF binary bytes, or local workstation paths (`/home/ra/...`) leak into the serialized registry payloads or public test distributions.

---

## 6. QA Recommendation and Final Verdict

The implementation of RSF-32 meets all architectural invariants, contract requirements, and acceptance criteria of Milestone M7. It cleanly decouples actor identities, equipment attachments, and runtime mappings, supports non-standard topologies, verifies byte-exact preservation and Rust oracle parity, and maintains strict separation between verified structure and native runtime execution.

**Final Verdict: QA_PASS**
