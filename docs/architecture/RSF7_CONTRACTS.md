# RSF-7 versioned declarations

RSF-7 adds a Python contract API in `ro_sprite_forge.core.contracts` and three
packaged, closed Draft 2020-12 JSON Schemas. The schemas require no network
resolution. Normal application operation still has no third-party runtime
dependencies. `scripts/check_contract_schemas.py` uses optional, locally installed
`jsonschema` only to independently check schema conformance.

| Record | Schema | Revision authority |
| --- | --- | --- |
| Actor | `rsf.actor/v1` | Integer `revision`, predecessor digest |
| Runtime profile | `rsf.runtime-profile/v2` | Semantic `profile_version` (`major.minor.patch`) |
| Declared target | `rsf.target/v2` | Integer `revision`, predecessor digest |
| Imported inventory | Existing `rsf.inventory/v1`, unchanged | Original source hashes and canonical digest |
| Artwork assignments | Separate future ledger; not implemented here | No assignment or approval inferred |

`load_actor`, `load_runtime_profile` and `load_target` validate JSON shape and
semantic constraints and return immutable typed `ActorContract`,
`RuntimeProfileContract` and `TargetContract` snapshots. `to_dict()` returns a
fresh copy; `canonical_bytes()` returns sorted-key, compact ASCII JSON with a
final LF. Ordered arrays retain their declared order, particularly layers,
parts, actions and views. Identical input produces identical bytes and hashes.
`canonical_sha256` hashes the canonical payload without the digest itself.
A supplied digest must match; raw declarations may omit it.

Actor identity separates category, arbitrary gameplay job ID, visual body family,
sex, body variant, costume, resource parts, action-profile ID and runtime-profile
reference. Job/body/action-profile identifiers are namespace strings, not a list
of recognized jobs. Nullable values explicitly mean unknown. Equipment/attachment
compatibility has its own `SUPPORTED | UNSUPPORTED | UNVERIFIED` declarations;
a non-unknown decision requires evidence hashes. Schema validity checks the
shape and consistency of evidence references, not the authenticity or truth of
an operator-supplied claim. It does not establish M7 equipment compatibility.

A profile pins repository/revision/file evidence, category, numeric groups and
ACT slots, semantic mappings, direction/selection rules, timing, part relations,
attachment declarations and separate gameplay reachability. Slot lists must
agree with `group * 8 + view`. Unknown semantic groups can retain numeric slots
with `id:null` and `UNVERIFIED` mapping/reachability. Custom action IDs without a
supported, evidenced mapping produce no resolved target slots. Unsupported
mappings have no group/slots. Evidence-backed support is a profile declaration,
never a native test result. No runtime rule interpreter or renderer is added.

`frozen_runtime_profile(category)` explicitly exports the accepted M0 frozen
profile to the new schema, retaining its source evidence and legacy digest.
It preserves raw resolution/timing descriptions and never upgrades a selectable
source path to verified gameplay reachability. Player has the evidenced
body/head anchor-delta relation; NPC and monster have body only, with no Player
head registration. Unclassified profiles have no invented semantics. Unknown
attachments stay unknown. The old frozen profiles, CLI `inspect`/`plan`, inventory
namespaces/hashes and occurrence IDs remain unchanged.

The legacy timing lists describe global client branches, including Pickup and
Attack3 fallback paths absent from NPC/monster action tables. The v2 exporter
narrows only the looping/nonlooping name lists to actions actually declared by
that category; the legacy digest retains the full original record. New profiles
reject undefined timing action names and overlapping looping/nonlooping lists.

Targets pin an actor revision and runtime profile by ID, version and digest.
They declare parts, full/scoped intent and ordered actions with `REQUIRED`,
`OPTIONAL` or `OUT_OF_SCOPE` requirements. In-scope actions have per-part views,
nullable frame counts and nullable topology. Excluded actions cannot declare
work. Explicit uniform layers and per-frame ordered roles are valid, including
explicit empty layer lists. Inherited topology pins a particular associated
inventory and numeric slot; it never infers a frame count. Reference-derived
frame counts must be copied deliberately into the target declaration.

`assess_target(target, actor=actor, profile=profile, inventories=(...))` verifies
resolved inheritance against the actor's inventory/ACT/SPR identities, part,
slot mapping, frame count and visible ordered source layer records. Missing
sources yield `INHERITANCE_SOURCE_UNAVAILABLE`. Missing counts or topology yield
`UNDERSPECIFIED_FRAME_COUNT` and `UNDERSPECIFIED_LAYER_TOPOLOGY`, at precise JSON
pointer locations. A structurally explicit custom part may remain
`UNVERIFIED_RESOURCE_PART` without destroying structural completeness.
The supplied inventories are never edited. RSF-8 owns generalized topology
expansion and production checklist/work-order integration.
Inheritance validates the namespace, source hashes, numeric slots, ordered
motions/layers and explicit visibility fields it consumes, even for a correctly
sealed input. A digest alone does not prove structural validity. Malformed
observation fields produce typed errors at `/inventories/<index>/...`.

A full-profile claim additionally needs every evidenced profile action/view for
every actor part as REQUIRED. Optional/excluded/missing pairs cannot satisfy it.
Unknown runtime profile coverage yields `UNVERIFIED_FULL_PROFILE`. A scoped
Walk-only target can be fully specified for its scope while full-profile status
remains false. Contract completeness is independent of runtime compatibility:
assessment always retains artwork `UNASSIGNED`, visual/native `UNVERIFIED` and
runtime compatibility `UNVERIFIED`. No uploaded artwork is required or credited.

## Validation and compatibility

Closed fields, duplicate identities, numeric ranges, schema versions, hashes,
references, conflicting parts/views/slots, topology lengths and allocation
budgets are validated. Errors use the existing `ForgeError(INVALID_INPUT)`
contract, with a precise JSON pointer in `path`. Schema validation enforces wire
shape; Python loaders add cross-field and cross-record rules. Contract bounds:
32 parts, 128 target actions, eight views, 4096 frames per view, 1024 unique roles
per frame, 65,536 total declared frames and 262,144 total resolved layers.

Actor/target revision 1 requires `previous_sha256:null`; later revisions require
a predecessor digest. Passing `previous=` additionally verifies same schema/ID,
exact +1 revision and matching predecessor hash. Without the prior record, a
hash link is a declaration, not a verified history. Runtime-profile `previous=`
requires the same ID and an advancing semantic version. Every reference pins
both version and digest, so replacing a profile under an existing name/version
cannot silently reinterpret a target or old evidence: loading with the new
profile rejects the old reference.

Unsupported schema versions fail with `UNSUPPORTED_SCHEMA_VERSION`; no implicit
migration or permissive normalization occurs. Existing M0 v1 targets remain valid
through their original API. There is no automatic target migration: a new v2
target must explicitly choose its actor revision, parts, compatibility and pinned
profile. The frozen-profile exporter is the only provided schema conversion.
Changing any declaration requires rebuilding dependent references explicitly;
it never changes an imported inventory, old snapshot or accepted native packet.
The future assignment ledger/reuse/approval invalidation mechanisms are outside
this task.
