# RSF-34 implementation and verification

Outcome: **RSF-34_IMPLEMENTED_AND_QA_PASSED**. Kaneo task `o5jlgmryf188c7lr43saqz7c`, implementer Codex
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. Authenticated workspace/project/member/task/dependency
lookups preceded source changes. RSF-33 was Accepted. Assignment was written and read
back; Ready then In Progress were each written/read back. No ownership transfer.
Ready → In Progress → QA Review → Accepted transitions were written/read back.
Final status `done`, Accepted column `vnkxm3fyt0tmewq1rdokfops`, same Codex owner,
all four live criteria checked and QA_PASS comment `ww1u7xe6w8204olfqbavgh0i` were
verified through MCP. See `kaneo-final-readback.json`; no pending tracker writes.

## Scope and identity

The optional `core.appearance` adapter extends registry v1, outside the compiler.
Character identity, external gameplay context, canonical underlying body, selected
visual appearance and additional head/equipment identities are distinct. Exact
source hashes/profile revisions/attachment record digest and explicit action/view
slots govern compatibility. No filenames, slot-count guesses, modulo fallback,
art adaptation, gameplay mutation or automatic approval determine the result.

Complete visual bodies replace the visible body in static preview while retaining
underlying identity. Attached overlays are restricted to supported accessory rules;
head/accessory cosmetics reuse anchor delta; equipment-derived visuals use the
shield/body-relative rule. This is not arbitrary clothing fitting. Source hashes
are checked before audited ACT 2.4 / SPR 2.1 decoding, topology/image counts and
visible pool references. New metadata and compatibility records are schema-validated.

Reports distinguish source validity, pairing, action/view mapping, frame correspondence,
layer topology, anchors, scoped/full compatibility, preview, compilation, independent
Rust, native verification, human review and gameplay eligibility. New compositions
have no export authority. Existing RSF-10 remains the coverage authority.

## Preview and review boundary

Preview calls existing attachment coordinate/order functions and compositor, applies
anchor delta once, retains original metadata/delay beside effective ordered clips,
and hashes actual PNG output. No body/head flattening or source writes occur.
Separate head/equipment dependencies block two-resource preview until explicitly
rebound to the selected host. Static preview is not native timing/fidelity proof.

The clothing adapter plan requires current bound requirements, exact valid ledger
assignments, authored PNG hashes, executed processing and current RSF-18 approval.
Retained classic reference art is not new authored clothing. Unexecuted transforms
and stale/unapproved composition bases fail closed. No compiler/export gate changes.

Appearance dependencies are declared through existing frame constraints, including
explicit aggregate frame IDs. The scoped regression changes X to Y: four dependent
appearance/aggregate reviews become STALE; four independent body/unrelated reviews
remain APPROVED; history, target and runtime identity remain unchanged. These are
isolated synthetic operator-decision fixtures; no real artwork approval is created.

## Real fixture findings and Dragon Knight reconciliation

| Exact source pairing | Scope/result |
|---|---|
| Genetic Female Costume 1 body + Jack Head Male accessory | 104 requested action/view slots supported; decoded 456-frame correspondence, anchors and selected Walk geometry checked. This is a two-resource composition, not a verified full body/head/accessory runtime chain. |
| Genetic Female Costume 1 body + Dragon Knight Male shield | 96/104 slots supported; Pickup slots 24–31 fail exact frame counts (body 3 versus shield 2). Walk static preview succeeds; Pickup preview is rejected. Gameplay eligibility and native execution remain UNVERIFIED. |
| Male Novice underlying body → Genetic Female visual body | 104 slots structurally match for declared synthetic target. Separate Novice head remains unchanged; preview with that head is blocked pending new host binding. |

The existing shield pairing's actual parent is `novice-male-body-v1`, not a Dragon
Knight body profile. No enrolled Dragon Knight body exists. RSF-33 private tests
supplied Genetic body bytes while passing the Novice profile; their descriptive
Novice/Dragon Knight parent labels are not hash-bound parent evidence. RSF-34 rejects
that substitution as `SOURCE_HASH_MISMATCH` and explicitly binds the real Genetic
pair. The old pairing remains a PARTIAL structural template; no new Dragon Knight
body compatibility/native claim is made. Accepted source and earlier evidence are
preserved; this report reconciles the labels against actual source identity.

Exact fixture ACT/SPR/profile hashes are in `source-identities.json`. Private hooks
read external sources; no private artwork, ACT/SPR files or captures are copied into
public evidence. New source structure/pixel parity and byte-exact ACT/SPR round trips
are independently checked for Genetic, Jack and shield (three actual Rust executions).
Canonical Python/Rust report hashes are retained in `private-summary.json`; parity
checks structure/pixels, not cosmetic eligibility, attachment rendering or native play.

## Determinism and correction

`reproduce.py` independently constructs all four synthetic representation cases twice.
Registry bytes, compatibility reports, preview proofs and actual PNG bytes are identical:
zero mismatches. `synthetic/determinism.json` SHA-256 is
`68ae25c64b6a6894245d7bb3916777bbb856497a46481d12fc7d01327e856be9`.
Focused tests also vary input order and PYTHONHASHSEED (1, 734); changed actual
costume bytes/profile/mapping or attachment revision changes relevant identities.
Noncanonical external labels/temporary directories never enter pairing construction.
Existing profile metadata retains accepted registry identity semantics.

One demonstrated integration defect was corrected narrowly: `load_registry()` resealed
an already sealed validated document, including its previous digest in the hash input.
Loading changed the canonical registry identity. It now preserves validated canonical
bytes. The reopen regression requires exact bytes/digest, including old registry v1
records with no cosmetic extension. No compiler/codec refactoring was performed.

## Executed verification

Commands, argv, exit statuses and log paths are in `commands.json`; environment/tool
versions and unavailable interpreters are in `environment.json`.

- Focused appearance/registry/attachment: 79 tests PASS, including 35 new appearance tests.
- Public: 618 tests PASS, exit 0, using local socket access for existing HTTP tests.
- Private: 52 run, 51 PASS, one documented legacy native-report skip; exit 0.
- Rust parity: 11 PASS, exit 0; additionally three real pair comparisons in the new private test.
- All 12 schema checkers PASS; registry Draft 2020-12: 2 valid / 18 invalid cases.
- Isolated wheel distribution: 618 run, 606 PASS / 12 optional Rust-tool skips; exit 0.
  Repeated clean wheels match, stdlib-only core smoke PASS and private resource exclusion PASS.
- Synthetic evidence reproduction: exit 0, four representations repeated twice.
- Browser/native GPU: NOT_RUN, no operator-facing/renderer/compiler changes.
- Python 3.14.4 tested; Python 3.12/3.13 unavailable, NOT_RUN. Existing Rust executable
  hash is recorded; Rust/Cargo compilation tools are unavailable on current PATH.

The initial sandbox public/distribution attempts failed on existing local socket
permissions, not implementation assertions. Those failed commands/logs remain retained;
successful runs with local socket access supersede them. An exploratory command used
the nonexistent test module `test_registry`; the corrected `test_profile_registry`
command passed. The first evidence-script attempt compared a bound method instead of
calling `canonical_bytes()`; correcting the invocation produced the retained repeated
byte comparisons. Neither exploratory invocation changed implementation behavior.

## Gate scope

The configured read-only reviewer `/root/rsf34_qa` independently executed focused,
public, private, Rust, schema, deterministic reproduction, fresh semantic probes and
installed-distribution checks. All passed; no reproducible findings or correction
cycle. Exact independent commands/results are in `QA_REPORT.md`, original reviewer
logs and probe in `independent-qa/`. No reviewer source or Kaneo writes occurred.

RSF-32, RSF-33 and RSF-34 are Accepted; RSF-34 has independent QA_PASS. M7 remains open for
RSF-35. M0–M6 accepted engineering evidence is preserved; relevant public/private/
package regressions protect it. New costume compilation/native Korangar execution
are UNVERIFIED, artistic suitability is operator-owned, and production export is false.
No new native PASS or universal GPU parity is claimed.

Source preservation comparison against the 143-file pre-task snapshot found 139
unchanged files, the three declared existing implementation/schema/checker changes,
and generated `src/ro_sprite_forge.egg-info/SOURCES.txt` packaging metadata. The three
new implementation/test files are listed separately in `implementation-manifest.json`.
No unexpected accepted-source changes were found; details are in `source-preservation.json`.

Next live dependency-eligible task: RSF-35, `[M7] Offline custom actions and explicit
runtime-support reporting`, ID `ly1cfaohrp6e00qxg4g1tfcj`, Backlog/unassigned.
Live incoming blockers RSF-32 and RSF-25 are both Accepted. Recommended implementer:
Codex/GPT-6 High, Python contracts/compiler/oracle and forge-kaneo/forge-codec/
forge-verification/forge-qa skills. It has not been started or assigned.
