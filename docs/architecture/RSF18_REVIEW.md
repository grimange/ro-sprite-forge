# RSF-18 canonical operator review

The single-operator workbench records explicit decisions; it makes no artistic decision.
`core/review.py` extends the existing ledger composition basis with the exact target,
profile, requirement, full frame/slot constraints, ordered frame layers and their
assignment bases, renderer/geometry/timing versions, and a versioned inspection policy.
Project display metadata, project save revision, timestamps, paths and future output
build hashes are excluded. Source/assignment revisions, source bytes, reuse lineage,
recipes, attachments and offsets remain covered by the accepted ledger basis.

`rsf.review-event/v1` is a closed packaged JSON Schema. Sealed immutable events record
project/target, exact sorted occurrence scope, per-occurrence composition and displayed
preview evidence hashes, decision, local operator-action provenance, limitations and
history revision. The HTTP CSRF boundary establishes a local explicit action, without
claiming authenticated human identity. Legacy ledger reviews are not silently migrated.

## Proposal and publication

`POST /api/projects/{id}/review-proposal` accepts the displayed project revision and
1–256 explicit requirement IDs. It reconstructs source evidence and returns a sealed
proposal plus every selected layer's image, source/reuse lineage, frame and slot facts.
The workbench expands frame/view/action selection into visible explicit IDs. The review
dialog shows all members and their exact basis before approve/reject confirmation.

`POST /api/projects/{id}/review` takes the entire proposal and explicit decision. The
backend reconstructs it from persisted current bytes and mappings, rejects any mismatch,
and uses the existing optimistic atomic project store. Batch validation precedes
publication; no partial decision is published. Generic project PUT cannot inject or
alter review history, ledger or target. Save/reopen preserves the immutable events.

## Currentness and coverage

Every read evaluates the latest event per occurrence against the current composition
and executable preview evidence. A changed basis or unavailable evidence produces
STALE with the prior decision retained. Orphaned requirement IDs remain historical.
The existing ledger graph propagates mapping revision changes to dependent assignments;
existing ledger acceptance and coverage rules consume an ephemeral review projection.
Reviews never change persisted assignment revisions. Unrelated metadata saves preserve
applicable reviews. Source A changes invalidate dependent B/C while independent D stays
applicable. No review automatically rebinds to revised inputs.

APPROVED, REJECTED, STALE and UNVERIFIED remain distinct. Explicit NOT_REQUIRED requires
unchanged classic-reference origin, no transforms/reuse and an explicit structural-only
policy selection. This exemption does not qualify as authored replacement coverage.
Visual decisions do not execute recipes, compile resources or establish native evidence;
export readiness remains false under the existing M3 coverage policy.

## Declared inspection limits

The current assignment-source path renders only supported mirror recipes. The review
policy is **provisional ordered source-layer inspection**, and the dialog shows this
limitation with timing/placement/attachment facts. It does not claim a compiled animation
or faithful native rendering approval. An unexecuted transform has no fabricated final
image and cannot be APPROVED or exempted; an explicit rejection may still be recorded.
Full assigned-frame compilation and additional recipe execution belong to later slices.

Public browser fixtures and decisions are synthetic. No private artwork receives an
automated visual decision. Native M0 acceptance and M2 fidelity evidence remain separate.
