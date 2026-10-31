# RO Sprite Forge — Compatibility and Actions Guide

This document explains actor profiles, action slot conventions, head/body separation, equipment attachment compatibility, and the boundary between native runtime support and offline diagnostic animations.

---

## 1. Pinned Actor & Resource Profiles

RO Sprite Forge uses versioned actor profiles to define the finite action and view expectations for characters and monsters.

### Audited Reference Profiles

#### Male Novice (`male_novice`)
- **Actor Category:** Player Character (`player`)
- **Action Groups:** 13 canonical action groups
- **Total Action/View Slots:** 104 slots (13 actions × 8 views)
- **Total Motion Occurrences:** 456 motion occurrences
- **Referenced SPR Identities:** 110
- **Distinct Decoded Contents:** 108

#### Orc Skeleton (`orc_skeleton`)
- **Actor Category:** Monster (`monster`)
- **Action Groups:** 5 canonical action groups (Stand, Walk, Attack, Hurt, Die)
- **Total Action/View Slots:** 40 slots (5 actions × 8 views)
- **Total Motion Occurrences:** 512 motion occurrences
- **Visible Layer References:** 1,776
- **Stored SPR Images:** 57 (55 actively referenced)

> [!NOTE]
> These counts are fixture-specific verification assertions for the audited private fixtures, **not** universal quotas for all custom sprites.

---

## 2. Action Groups & Runtime Slot Mappings

Ragnarok ACT files index actions sequentially in groups of 8 directions (views). Pinned Korangar runtime resolves actions via numerical slot indices:

$$\text{Slot Index} = (\text{Action Group Index} \times 8) + \text{View Index}$$

### Canonical Player Action Groups

| Group Index | Base Slot | Action Name | Timing Model | Typical Frame Count |
|---|---|---|---|---|
| `0` | `0` | **Stand / Idle** | Loop (fixed 432ms) | 4 frames (8 views) |
| `1` | `8` | **Walk** | Movement speed dependent | 8 frames (8 views) |
| `2` | `16` | **Sit** | Static hold | 1 frame (8 views) |
| `3` | `24` | **PickUp** | One-shot sequence | 3 frames (8 views) |
| `4` | `32` | **ReadyFight** | Loop | 4 frames (8 views) |
| `5` | `40` | **Attack 1** | Attack speed (ASPD) duration | Variable (8 views) |
| `6` | `48` | **Hurt / Flinch** | Hit delay duration | 1–2 frames (8 views) |
| `7` | `56` | **Freeze 1** | Status hold | 1 frame (8 views) |
| `8` | `64` | **Die** | Terminal hold (final frame) | 3–5 frames (8 views) |
| `9` | `72` | **Freeze 2** | Status hold | 1 frame (8 views) |
| `10` | `80` | **Attack 2** | Attack speed (ASPD) duration | Variable (8 views) |
| `11` | `88` | **Attack 3** | Attack speed (ASPD) duration | Variable (8 views) |
| `12` | `96` | **Skill / Cast** | Cast timing duration | Variable (8 views) |

### Canonical 8-Direction View Angles

Ragnarok sprites use clockwise view indices starting from South:

```
         4 (North)
    3 (NW)       5 (NE)
 2 (West)         6 (East)
    1 (SW)       7 (SE)
         0 (South)
```

- **Primary Authored Views:** View `0` (South), `1` (South-West), `2` (West), `3` (North-West), `4` (North).
- **Mirrored Views:** View `5` (North-East, mirrors `3`), `6` (East, mirrors `2`), `7` (South-East, mirrors `1`).
> In RO Sprite Forge, mirrored views require an explicit `EXPLICIT_REUSE` ledger entry with a `mirror_x` transform; they are never assumed automatically.

---

## 3. Head and Body Separation

Player characters in Ragnarok are composed of separate, dynamically paired sprite pairs:
- **Body Resource:** Base character class clothing and posture (`body`).
- **Head Resource:** Hair style, hair color, and facial expression (`head`).

### Anchor Points in ACT 2.4
ACT version 2.4 defines coordinate anchor points per motion occurrence:
- **Attach Point 0 (Head Anchor):** Located in the body ACT frame. Specifies the exact `(x, y)` coordinate offset where the head sprite's origin must be rendered.
- **Attach Point 1 (Weapon/Hand Anchor):** Specifies the attachment offset for handheld weapons or effects.

### Preview Compositing
When an operator inspects a character with both body and head resources selected in the workbench:
1. The body frame is rendered at the coordinate center.
2. The head anchor point is extracted from the body motion frame.
3. The corresponding head frame is offset by the anchor coordinates and rendered directly on top.
4. If anchor data is missing, the workbench emits an `ANCHOR_MISSING` diagnostic.

---

## 4. Equipment and Attachment Compatibility

Equipment attachments (helmets, top/mid/bottom headgears, shields, wings, and robes) require strict structural compatibility with the parent body.

### Frame Topology Validation
- An attachment resource must contain the exact same frame count per action/view slot as the base actor resource.
- If an equipment piece has 6 frames for Walk South while the body has 8 frames, the workbench flags `MISMATCHED_FRAME_COUNT`.
- Missing frame topologies cannot be interpolated or skipped; the operator must supply matching frame assets or adjust the slot definition.

### Layer Ordering Invariants
During compositing, layers must follow strict draw order:
1. **Layer 0:** Ground Shadow
2. **Layer 1:** Back Attachment (e.g. Wings, Cape, Shield when facing North)
3. **Layer 2:** Base Body
4. **Layer 3:** Head / Hair
5. **Layer 4:** Headgear (Bottom / Mid / Top)
6. **Layer 5:** Forehand Weapon / Shield (when facing South)

---

## 5. Offline Custom Actions & `PARTIAL_DIAGNOSTIC` Boundaries

Operators often design custom animation cycles for projects (e.g. unique emotes, celebration dances, cinematic sequences, or specialized crafting animations).

### Native Support vs Diagnostic Status

RO Sprite Forge enforces a strict distinction between **runtime-supported slots** and **diagnostic-only animations**:

- **Native Korangar Slots:** Slots 0 through 103 for player characters conform to pinned Korangar client actions. These can achieve full `READY` status and pass Gate M0-N.
- **Offline / Custom Actions:** Actions outside the canonical 13-action Korangar slot range (e.g. Action Group 14+) are classified as `PARTIAL_DIAGNOSTIC`.

### What `PARTIAL_DIAGNOSTIC` Means
- **Fully Supported in Forge:** You can assign artwork, define layer topology, preview animations, scrub timelines, and record visual approvals.
- **Explicit Runtime Limitation:** The compiled asset will document that these slots cannot be invoked by standard Korangar game network packets without client engine modifications.
- **No Conflation:** The workbench status badge will display `[PARTIAL]` to ensure operators never assume an offline custom animation has native game client proof.
