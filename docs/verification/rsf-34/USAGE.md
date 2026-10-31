# RSF-34 cosmetic compatibility API

The optional `core.appearance` adapter extends `rsf.compatibility-registry/v1` with
`cosmetic_pairings`. Existing registry documents remain valid, retain their bytes,
and are not reinterpreted. No browser controls or binary compiler entry points change.

`build_cosmetic_pairing()` binds exact body/appearance profile IDs, revisions and
canonical hashes; profiles bind ACT/SPR hashes. Declare each supported action, view,
body slot and appearance slot explicitly. The only frame correspondence is
`EXACT_EQUAL_ORDINAL`: actual counts must match the target and both resources.
Additive records also bind the entire existing attachment record hash, anchor rule
and ordered parts. Enrollment through `create_registry()`/`load_registry()` checks
these declarations; `evaluate_appearance()` checks actual hash-bound bytes using the
audited codecs and existing image resolver. Display labels are not pairing inputs.
Profile metadata retains the existing RSF-32 canonical identity rules.

Four bounded representations are available:

| Representation | Execution and limits |
|---|---|
| `COMPLETE_VISUAL_BODY` | Preview the appearance body instead of drawing the original body beneath it. Retain underlying body identity. Separate heads/equipment require explicit new host bindings. |
| `ATTACHED_OVERLAY` | Existing accessory anchor-delta rule only; not arbitrary garment fitting. Preserve both resources and ordered layers. |
| `HEAD_ACCESSORY` | Existing head/accessory anchor-delta rules only. Require exactly one source anchor in each selected motion. |
| `EQUIPMENT_VISUAL` | Existing shield/body-relative rule only, with no child anchor. Technical compatibility says nothing about gameplay eligibility. |

Pass `requirements`, immutable `resources={profile_id: (act_bytes, spr_bytes)}`,
`character_id`, and optional external `gameplay_job` to `evaluate_appearance()`.
Neither character nor gameplay context is derived from the selected appearance.
The report distinguishes requested scope, full-profile scope, action/view mapping,
frame correspondence, layer topology and anchor execution. Missing scopes and precise
diagnostics remain visible. A scoped `SUPPORTED` result is not full actor acceptance.
Supplied additional head/equipment identities remain separate; their composition is
`UNVERIFIED` until explicitly bound, and the two-resource preview rejects them.

`preview_appearance(..., action='Walk', view=0, frame=0)` uses actual decoded resources
and the existing attachment/compositor functions. Anchor deltas are applied once.
The returned proof retains original clips, bounds, anchors, sound event and source
slot delay, effective ordered clips, and rendered PNG hash. This is a static selected
resource composition with the accepted compositor's partial fidelity limitations;
it is not runtime timing, full native fidelity, artwork approval or export authority.
No source bytes or canonical body/head resources are altered or flattened.

Call `bind_appearance_requirements()` before assigning/reviewing supplied new art.
This binds appearance dependencies through existing RSF-18 frame constraints.
Explicitly pass `dependent_frame_ids` for aggregate composition frames that depend
on that appearance. Rebinding X to Y invalidates those and appearance-part reviews;
independent body/unrelated frame reviews and all historical decisions remain intact.
This explicit dependency declaration does not automatically infer arbitrary aggregates.

`prepare_clothing_composition()` is an optional adapter plan, separate from the generic
compiler. It requires bound current requirements, exact valid ledger assignments,
validated authored PNG bytes, executed transformations, and applicable current
operator approval for every selected occurrence. Retained `CLASSIC_REFERENCE` art is
rejected as new clothing, even if reviewed. It returns assignment/review/source/basis
identities; it does not publish binaries or authorize production. Existing coverage,
compilation and export gates remain authoritative. No approval events are created.

New pairing native, independent-Rust composition and compilation statuses remain
`UNVERIFIED`; `export_ready` is false. Independent Rust parity can separately verify
the ACT/SPR source structures and pixels. Prior M5 native evidence does not transfer
to a newly selected cosmetic composition.

Reproduce synthetic reports and real PNG previews with:

```sh
PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/verification/rsf-34/reproduce.py /tmp/rsf34-reproduction
PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest test_appearance test_profile_registry test_attachment_compatibility -v
```

Compare `determinism.json` and all referenced artifacts against `synthetic/`.
The two independent runs must match byte-for-byte. Private fixtures are optional,
read-only and excluded from source/wheel distributions; no private captures are saved.
