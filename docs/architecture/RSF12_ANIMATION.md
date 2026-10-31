# RSF-12 animation inspection

`core.timeline.AnimationTimeline` operates on a snapshot of decoded ACT motions.
`core.animation.AnimationInspector` reads original ACT/SPR bytes, computes their hashes,
uses the timeline, and calls the accepted `formats.preview.composite_frame` renderer.
There is no second renderer, clock, image ingestion, artwork assignment or approval path.

## Selection and timing

Select a verified semantic action under an explicit frozen Player/NPC/Monster profile,
or an exact numeric ACT slot with its view. Unknown mappings remain numeric. Missing
slots, mismatched numeric views and unsupported semantic actions fail; resource modulo
fallback is rejected. Requested direction and camera direction resolve as `(direction +
camera_direction) & 7` and remain in the report through stepping and seeks.
Manual selection/stepping uses existing raw ACT motions and explicit clamp or wrap policy.
Timed evaluation is separate and accepts nonnegative u32 elapsed milliseconds and an
explicit positive preview speed. The scaled time is truncated to an integer simulation
tick; preview speed is not claimed as a Korangar gameplay parameter.

Pinned source: Korangar `3f3d88a583203f09d079712f43343c1041258ffd`:

- `world/animation/mod.rs`: SHA-256
  `72a49aa2069306499e2fe76200a9388c8c69b97ec19ed76ade84c2297d1ccaa1`.
  Idle/Die use ACT delay × 50, Pickup × 25. Walk requires explicit movement speed and
  uses ACT delay × `(movement_speed * 100 / 150 / 5)`. Each floating operation follows
  f32 rounding. Attack1/Attack3/Hurt require an explicit positive external duration;
  frame time is `elapsed * frame_count / duration` using integer arithmetic. Potential
  u32 overflow is rejected rather than reproducing a native panic/release wrap.
- Idle/Walk loop, Player Idle selects frame zero. Other supported setters clamp to the
  last frame. `terminal_hold` means frame time has passed the frame-count boundary;
  selecting the last frame during its ordinary interval alone is not terminal hold.
  The separate native completion predicate uses **view zero** and `frame_time > count`.
- Mapped actions without evidenced state setters (Sit, Skill, etc.) have unresolved
  runtime timing. Missing Walk/Attack/Hurt context is also UNVERIFIED. A caller may
  explicitly select a diagnostic interval, always labeled DIAGNOSTIC; it does not
  establish native semantics or gameplay reachability. Diagnostic frame time is u32-bounded.
- Empty raw motions are retained. Native prepared-frame compaction of zero-clip
  motions is explicitly UNVERIFIED; no source motions are synthesized or silently omitted.

## Spatial and multipart inspection

The compositor returns additional geometry alongside its unchanged preview-result/v1
shape. Stage rectangles come from the actual source, mirrored, scaled and rotated images.
Alpha bounds use the alpha channel, including transparent RGB pixels correctly. Final
placement uses the same integer center `(size - 1) // 2`, origin, offset and clipping
coordinates as composition. Half-open rectangles distinguish full extent, unclipped
alpha extent, visible alpha extent, canvas intersection and disjoint clipped regions.
Combined frame rectangles union individual layers; transparent layers and empty frames
remain distinct from missing images. Source layer ordinals include gaps from negative
sprite sentinel records. Invalid visible image references fail.

Player body/head use the same raw slot and motion ordinal, body-controlled playback,
and separate resource hashes/raw delays. A head with exactly one anchor receives the
body-first-anchor minus head-anchor offset, as the pinned executable loader specifies.
Missing exact head frames fail. A missing parent anchor is reported as unsupported;
non-Player attachment is rejected. No generic NPC/monster attachment mapping is inferred.

The pinned loader source `loaders/animation/mod.rs` hashes to
`318e40783be1ee0a280b341967a69f3bcf247456fb72d0d099aead5551ab06b9`;
Player part order is established by `world/entity/mod.rs`, hash
`5383bfc574e8a65b8a53ab0a55d8ca2929cc25c474339cdcb632a26b9b744fe0`.
RSF-12 corrects the compositor's prior unconditional first-head-anchor adjustment:
the native condition is exactly one child anchor. Renderer semantics advance to **1.1.0**;
geometry and timing semantics are **1.0.0**. Prior preview schema remains v1. Old reports
are retained; relevant new inspection identities change with versions, source/profile
hashes, selection and canvas policy. No approval ledger is modified or reapproved.

Preview allocation is bounded to 8192 pixels per axis and 16 Mi pixels per image/canvas
and aggregate retained transformed layers. Arbitrary-angle rotation additionally bounds
its enclosing square before allocation. Nonfinite transforms and invalid dimensions fail.
The compositor's historical minimum-one-pixel handling of zero scale remains diagnostic;
nonpositive scales and nonboolean mirror values explicitly lack native parity.

## Contracts and API

`rsf.timeline-selection/v1` and `rsf.animation-inspection/v1` are closed, packaged
Draft 2020-12 JSON contracts. Reports use canonical JSON with a SHA-256 excluding its
own digest field. Selection records are reconstructed from source/profile and declared timing inputs before
use, including all derived fields; a re-hashed inconsistent record is rejected. Inspection
outputs detach mutable anchors/events/selection data from internal source snapshots.
Auto-fit uses actual extents even for large signed ACT offsets.
Source bytes, decoded ACT snapshot, profile hash, renderer/timing/
geometry versions, raw facts and computed diagnostics are distinct. No paths, timestamps
or wall-clock state enter canonical identity.

Example (explicitly selected local resources, new output paths):

```sh
ro-sprite-forge animation --act body.act --spr body.spr --category player \
  --head-act head.act --head-spr head.spr --action Walk --view 0 \
  --time-ms 480 --movement-speed 150 --speed 1 \
  --json inspection.json --output frame.png
ro-sprite-forge animation --act monster.act --spr monster.spr --category monster \
  --action Die --frame 21 --step -1 --auto-fit
```

Without `--json`, canonical diagnostics go to stdout. `--step` is signed, `--loop`
explicitly wraps manual stepping. `--time-ms` uses runtime loop/terminal rules. There is
no implicit wall-clock play loop; a future UI can repeatedly evaluate explicit time.
JSON and optional PNG are staged together with the existing no-overwrite publication
helper, rolled back on an exception and read back before success. Separate file paths
are not a crash-atomic filesystem transaction.

## Fidelity and limits

Geometry is verified for the declared CPU rasterizer. Overall diagnostics remain PARTIAL:
GPU WBOIT, action-wide native billboard registration and cross-GPU pixel parity are not
proved by Pillow rectangles. Native rotation stays a GPU transform; Pillow expands the
rotated raster. Raw motion bounds/anchors remain source facts, not replacements for the
computed viewport. Gameplay reachability remains UNVERIFIED in frozen profiles.
Artwork coverage is NOT_EVALUATED and visual review UNVERIFIED. Existing M0 native
acceptance remains scoped to its original reference artifacts and pinned configuration.
Contact sheets, sequence exports and reference/candidate comparison belong to live RSF-13;
no candidate is invented and no contact-sheet subsystem is added in RSF-12.
