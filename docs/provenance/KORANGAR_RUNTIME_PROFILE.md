# Frozen Korangar runtime profile provenance

RSF-3 records independently described source semantics, not copied client code or
native verification. Normative revision: `3f3d88a583203f09d079712f43343c1041258ffd`.
The local checkout HEAD and `git show REVISION:path` were inspected; runtime use
requires no checkout. File identities are embedded in every verified profile.

| Source at the revision | SHA-256 | Evidence |
| --- | --- | --- |
| `korangar/src/world/animation/mod.rs` | `72a49aa2069306499e2fe76200a9388c8c69b97ec19ed76ade84c2297d1ccaa1` | `action_base_offset` (35–69), state setters (86–156), completion (245–267), `get_frame` (269–303) |
| `korangar/src/loaders/animation/mod.rs` | `318e40783be1ee0a280b341967a69f3bcf247456fb72d0d099aead5551ab06b9` | Ordered parts, sentinel image omission, transforms, registration (95–165) |
| `korangar/src/loaders/action/mod.rs` | `31e10e0f8fbf8129028620819e609557f41f5ecc9124777988ece941f9116ac7` | Events and raw delays (99–105) |
| `korangar/src/world/entity/mod.rs` | `5383bfc574e8a65b8a53ab0a55d8ca2929cc25c474339cdcb632a26b9b744fe0` | Body then head resource paths (338–373) |

Player groups are Idle, Walk, Sit, Pickup, ReadyFight, Attack1, Hurt, Freeze1,
Die, Freeze2, Attack2, Attack3, Skill. NPC/monster groups are Idle, Walk, Attack1,
Hurt, Die. Hidden shares the player's mapping in source but is not a selectable
profile here; Warp is not supported here. Other requested actions fall back to group
zero for NPC/monster, including critical Attack3. This fallback is not requested-action support.

Idle, Walk, Pickup, Attack1/Attack3, Hurt and Die have state-selection paths.
Other player actions have a source group mapping but selection remains UNVERIFIED.
An enum or file slot alone is not evidence of gameplay selection.

View resolution adds camera and entity direction modulo eight. Requested slot is
group*8+view; prepared animation and delay arrays are independently indexed modulo
their lengths. Player Idle is frozen to frame zero. Default delay multiplier is 50;
Walk uses movement speed*100/150/5, Pickup 25. Attack/Hurt use server duration.
Nonlooping animation clamps to the final frame; completion tests use view zero and
a strict greater-than frame count check. Empty-clip motions can be skipped by the
loader, so the inventory does not label raw ACT motion counts as runtime frame counts.

Player body/head preparation has ordered parts and conditional Player head registration
using body minus head first-anchor offsets. Other attachments and named compass
directions remain unverified. NPC and monster select one body resource each;
the player head relationship does not apply to them. No ACT/SPR or client source was modified, no native
client was launched and no action/view/slot playback proof is claimed.

Cross-check: local `RO_SPRITE_FORGE_LWR_REUSE_AUDIT_E1.md` §§4–6 agrees on the
13/5 mapping and audited fixture distinctions. Source hashes above are the normative
profile identity; the local audit is corroborating evidence. Game fixtures stay private.
