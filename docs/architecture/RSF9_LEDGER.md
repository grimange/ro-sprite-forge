# RSF-9 assignment and dependency contracts

The `rsf.assignment-ledger/v1` declaration binds exact RSF-8 layer IDs to operator-selected sources or explicit assignment dependencies. `load_ledger(document, requirements=resolved)` returns an immutable `AssignmentLedger`. `resolve_ledger(ledger, requirements=resolved, source_bytes={id: bytes_or_none})` emits sealed `rsf.resolved-ledger/v1`. `compare_ledgers(before, after, current_requirements=optional)` emits sealed `rsf.ledger-impact/v1`. Core APIs do not open files, decode images or execute transformations.

The packaged closed Draft 2020-12 JSON Schema describes declarations; core checks add exact requirement bindings, references, graph constraints and revisions. Existing actor, profile, target, inventory and topology versions/identities are unchanged. Unsupported ledger or operation versions are rejected; there is no implicit migration.

## Sources and assignments

Each source declares a stable ID, revision, nullable declared SHA-256, IMAGE/VIDEO_FRAME/IMPORTED_IMAGE kind, AUTHORED/CLASSIC_REFERENCE/UNVERIFIED origin, a non-path external reference, nullable pool/index and nullable inventory/ACT/SPR provenance hashes. Imported images require pool/index and resource provenance. IMAGE and VIDEO_FRAME identify supplied content; there is no PNG ingestion or video extraction. These origins and provenance are operator declarations, not aesthetic judgments or authenticated claims.

Source observations are separate from declarations. Unprovided source bytes mean UNVERIFIED; explicit `None` means observed MISSING. Nonempty bytes with matching declared SHA-256 mean AVAILABLE + VALID **only for content identity**. Hash mismatch means AVAILABLE + INVALID. Missing declared hash remains UNVERIFIED. Image dimensions, decoder validity, visual suitability and transformed output are NOT_RUN. No bytes, absolute paths or timestamps enter manifests.

Assignments have explicit stable IDs/revisions and exact target/hash and requirement bindings (part, action, view, frame, layer). DIRECT_SOURCE references a source ID/revision; EXPLICIT_REUSE references an assignment ID/revision; UNASSIGNED references neither and has no recipe or review. Omitted assignments also remain UNASSIGNED. Duplicate IDs, duplicate requirement bindings, stale references and incompatible binding coordinates are rejected. Optional and required occurrences retain their topology identities; this task does not implement RSF-10 completeness evaluation.

## Recipes, graph and attachments

Recipes are ordered arrays with unique operation IDs, operation version 1 and closed parameters: `mirror_x` (none), `translate` (integer x/y), `scale` (positive rational x_num/x_den/y_num/y_den), `rotate` (integer millidegrees, ±360000), `crop` (nonnegative x/y, positive width/height). Parameters and counts are bounded. No malformed operation is normalized; rational values are kept as declared. These are recipes, not executed pixels. Crop coordinates are not validated against undecoded image dimensions.

Reuse traversal is iterative and deterministic. Missing/stale dependencies and self/indirect cycles are rejected. Reports retain every assignment in the lineage and every operation's owner, with ancestor operations before dependent operations. A declared reuse of an unassigned dependency remains unresolved, never valid art. No content deduplication implies reuse. The expansion budget rejects excessive chains.

Explicit attachment links name parent/child assignments and resource parts, plus anchor ID/index/coordinates. They require matching action/view/frame and distinct parts. Missing references, conflicting parents and cycles (including mixed attachment/reuse cycles) are rejected. Links are declarations; this task does not verify native anchor suitability. Parent composition changes affect child review bases and impact closure.

## Review boundaries and accounting

Review is nullable. A recorded decision must explicitly say OPERATOR, operator identity, evidence SHA-256, basis SHA-256, decision and policy. This is a local operator assertion supplied by the caller; no identity authentication service or approval UI is implemented. The engine never generates such records. Synthetic test operator records are test data, not approval of game art.

The basis binds exact target/profile, layer record, assignment revision/recipe/source, dependency composition, and attachment/parent composition. Decision/evidence metadata is excluded from the basis to avoid self-reference. Stale bases yield UNVERIFIED + STALE, not silent approval. NOT_REQUIRED requires explicit UNCHANGED_REFERENCE policy, CLASSIC_REFERENCE origin and an empty effective transform chain. It never establishes replacement-art coverage.

An accepted reuse path requires valid observed source bytes and applicable bound operator review for every root/edge. Even a VALID + REUSED assignment remains visually UNVERIFIED without that evidence. Reported source-art roots count only explicitly approved AUTHORED roots reached through accepted paths, using root assignment IDs rather than pixel/source-hash deduplication. Two independent direct assignments of identical bytes remain two roots. Partial root/occurrence counts do not claim exact remaining authoring effort, complete coverage, visual suitability, native compatibility or export readiness.

## Revisions and impact

With `previous=old_ledger`, changed ledger declarations require a higher ledger revision linked to the old hash; changed source/assignment records require higher record revisions. Exact replay is accepted. A stored higher revision may be loaded standalone, but predecessor authenticity cannot be verified without supplying it. Reports preserve declared revisions and actual observed byte hashes separately.

Impact compares composition, observed hashes/availability/validation and graph membership, then follows old and new reuse/attachment edges. It reports affected, unaffected and orphaned assignment IDs deterministically. Current requirements can identify stale target revisions or changed layer records even when a layer ID survives. No orphan is discarded or remapped. Review evidence alone does not change composition; affected review bindings are never reapproved. Display metadata is intentionally outside the contract; changing an external source reference is a canonical source change.

Externally supplied resolved reports undergo bounded shape, enum, unique-identity and source/occurrence/dependency/attachment reference validation before impact comparison. A valid content seal proves byte identity, not structural validity. Malformed reports return typed input diagnostics rather than tracebacks; missing graph edges, duplicate records and cycles are rejected.

## CLI

```
ro-sprite-forge ledger --requirements requirements.json --ledger ledger.json \
  --source art-a=/local/source --output resolved-ledger.json
ro-sprite-forge ledger-impact --before old.json --after new.json \
  --requirements current-requirements.json --output impact.json
```

`--source` repeats; `--missing-source ID` records observed absence. Inputs use existing bounded readers; outputs use atomic no-overwrite publication. Invalid declarations/graphs publish nothing. Source verification failures publish an explicitly diagnostic report and return the established INVALID_INPUT/exit 3; no approved resource is produced. All selected assignments need observed valid source identity for CLI exit 0. A zero-assignment ledger can report its unassigned work successfully. Source paths remain outside canonical records. The pure core permits explicit UNVERIFIED source observations for offline planning.

Limits: 100000 assignments/requirements, 10000 sources/attachments, 64 operations per assignment, 64 MiB total observed source bytes, 1000000 expanded lineage/operation records. Python/Rust codecs, normal native runtime, and original resources are unchanged.
