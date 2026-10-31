"""Versioned requirements coverage evaluation and missing-art work orders (RSF-10).

Combines resolved structural requirements with artwork assignment ledgers to produce
deterministic, actionable work orders. No image generation or artistic evaluation.
Preserves orthogonal status dimensions: structural, assignment, validation, review,
preview, and native evidence.
"""

from importlib.resources import files
import json
from typing import Mapping

from ro_sprite_forge.core.canonical import canonical_bytes, check_seal, digest, sealed
from ro_sprite_forge.core.contracts import TargetContract, require, _shape
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ledger import (
    AssignmentLedger,
    load_ledger,
    resolve_ledger,
    _requirements,
    _validate_resolved_report,
)

MAX_RECORDS = 100000


def coverage_schema() -> dict:
    return json.loads(
        files('ro_sprite_forge')
        .joinpath('schemas/coverage-report-v1.json')
        .read_text()
    )


def _validate_coverage_report(report: dict) -> None:
    """Validate external coverage report shape and canonical seal."""
    check_seal(report, 'rsf.coverage-report/v1')
    _shape(report, coverage_schema())


def evaluate_coverage(
    requirements: dict,
    ledger: AssignmentLedger | dict | None = None,
    *,
    source_bytes: Mapping[str, bytes | None] | None = None,
    target: TargetContract | dict | None = None,
) -> dict:
    """Evaluate requirements coverage and produce missing-art work order.

    Consumes rsf.resolved-requirements/v1 and either rsf.assignment-ledger/v1 declaration,
    AssignmentLedger, rsf.resolved-ledger/v1 report, or None (evaluated as unassigned).
    """
    check_seal(requirements, 'rsf.resolved-requirements/v1')
    req_layers = _requirements(requirements)

    excluded_actions = []
    if target is not None:
        t_dict = target.to_dict() if isinstance(target, TargetContract) else target
        require(
            t_dict.get('id') == requirements['target']['id']
            and t_dict.get('revision') == requirements['target']['revision'],
            '/target',
            'Target contract reference mismatch.',
        )
        for act in t_dict.get('actions', []):
            if act.get('requirement') == 'OUT_OF_SCOPE':
                excluded_actions.append(act['id'])

    resolved_ledger: dict
    if ledger is None:
        empty_decl = {
            'schema': 'rsf.assignment-ledger/v1',
            'id': f"{requirements['target']['id']}-ledger",
            'revision': 1,
            'previous_sha256': None,
            'target': requirements['target'],
            'requirements_sha256': requirements['canonical_sha256'],
            'sources': [],
            'assignments': [],
            'attachments': [],
        }
        loaded = load_ledger(empty_decl, requirements=requirements)
        resolved_ledger = resolve_ledger(loaded, requirements=requirements)
    elif isinstance(ledger, AssignmentLedger):
        resolved_ledger = resolve_ledger(
            ledger, requirements=requirements, source_bytes=source_bytes
        )
    elif isinstance(ledger, dict):
        if ledger.get('schema') == 'rsf.resolved-ledger/v1':
            _validate_resolved_report(ledger)
            require(
                ledger['requirements_sha256'] == requirements['canonical_sha256'],
                '/requirements_sha256',
                'CHANGED_REQUIREMENTS: ledger resolved against different requirements.',
            )
            require(
                ledger['target'] == requirements['target'],
                '/target',
                'STALE_TARGET_REVISION_OR_IDENTITY.',
            )
            resolved_ledger = ledger
        elif ledger.get('schema') == 'rsf.assignment-ledger/v1':
            loaded = load_ledger(ledger, requirements=requirements)
            resolved_ledger = resolve_ledger(
                loaded, requirements=requirements, source_bytes=source_bytes
            )
        else:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                'Unsupported ledger schema.',
                path='/schema',
            )
    else:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            'Expected AssignmentLedger, dict or None.',
            path='/ledger',
        )

    slots_map = {s['id']: s for s in requirements['slots']}
    by_req = {a['requirement_id']: a for a in resolved_ledger['assignments']}
    child_attachments = {
        link['child_assignment']: link for link in resolved_ledger.get('attachments', [])
    }
    assignments_by_id = {a['id']: a for a in resolved_ledger['assignments']}

    occurrences = []
    unresolved_items = []

    cat_counts = {
        'supply_artwork': 0,
        'restore_or_locate_source': 0,
        'correct_invalid_source_or_assignment': 0,
        'resolve_requirements': 0,
        'verify_source_content': 0,
        'verify_transformation': 0,
        'review_artwork': 0,
        'review_stale': 0,
        'resolve_runtime_support': 0,
    }

    # Evaluate each layer occurrence in requirements
    for layer in requirements['layers']:
        rid = layer['id']
        a = by_req.get(rid)
        slot_id = layer['frame_id'].rsplit('/frame', 1)[0]
        slot = slots_map.get(slot_id, {})
        runtime_support = (
            a['runtime_support'] if a else slot.get('runtime_mapping', 'UNVERIFIED')
        )
        req_type = layer.get('requirement', 'REQUIRED')

        category = None
        reason = None
        action_needed = None
        issues = []
        is_resolved = True

        if a is None or a['kind'] == 'UNASSIGNED':
            category = 'SUPPLY_ARTWORK'
            reason = 'UNASSIGNED_OCCURRENCE'
            action_needed = (
                'Assign a direct source or explicit reuse dependency to this required layer.'
            )
            issues.append('UNASSIGNED_OCCURRENCE')
            if runtime_support == 'UNSUPPORTED':
                issues.append('RUNTIME_ACTION_UNSUPPORTED')
            kind = 'UNASSIGNED'
            aid = None
            sid = None
            chain = []
            avail = 'MISSING'
            valid = 'UNVERIFIED'
            review = 'UNVERIFIED'
            review_b = 'UNRECORDED'
            is_resolved = False
        else:
            kind = a['kind']
            aid = a['id']
            sid = (
                a['effective_source']['id']
                if a.get('effective_source')
                else None
            )
            chain = [ref['id'] for ref in a.get('lineage', [])]
            avail = a['availability']
            valid = a['validation']
            review = a['visual_review']
            review_b = a['review_binding']

            if avail == 'MISSING':
                category = 'RESTORE_OR_LOCATE_SOURCE'
                reason = (
                    'SOURCE_UNAVAILABLE'
                    if kind == 'DIRECT_SOURCE'
                    else 'DEPENDENCY_SOURCE_MISSING'
                )
                action_needed = f"Provide source content bytes for source '{sid}'."
                issues.append(reason)
                is_resolved = False
            elif valid == 'INVALID':
                category = 'CORRECT_INVALID_SOURCE_OR_ASSIGNMENT'
                reason = (
                    'SOURCE_HASH_MISMATCH'
                    if kind == 'DIRECT_SOURCE'
                    else 'DEPENDENCY_INVALID'
                )
                action_needed = (
                    f"Correct invalid source content or declared hash for '{sid or aid}'."
                )
                issues.append(reason)
                is_resolved = False
            elif avail == 'UNVERIFIED' or valid == 'UNVERIFIED':
                category = 'VERIFY_SOURCE_CONTENT'
                reason = 'SOURCE_UNVERIFIED'
                action_needed = (
                    f"Verify source content bytes and declare expected SHA-256 for '{sid}'."
                )
                issues.append('SOURCE_UNVERIFIED')
                is_resolved = False
            elif review_b == 'STALE':
                category = 'REVIEW_STALE'
                reason = 'REVIEW_STALE'
                action_needed = 'Composition revision changed; operator re-review required.'
                issues.append('REVIEW_STALE')
                is_resolved = False
            elif review == 'REJECTED':
                category = 'CORRECT_INVALID_SOURCE_OR_ASSIGNMENT'
                reason = 'REVIEW_REJECTED'
                action_needed = (
                    'Artwork was rejected by operator; provide replacement artwork or update assignment.'
                )
                issues.append('REVIEW_REJECTED')
                is_resolved = False
            elif review == 'UNVERIFIED':
                category = 'REVIEW_ARTWORK'
                reason = 'VISUAL_REVIEW_PENDING'
                action_needed = 'Operator visual review required for composition revision.'
                issues.append('VISUAL_REVIEW_PENDING')
                is_resolved = False
            elif a.get('source_origin') == 'CLASSIC_REFERENCE' and not a.get('replacement_artwork'):
                category = 'SUPPLY_ARTWORK'
                reason = 'CLASSIC_REFERENCE_FALLBACK'
                action_needed = (
                    'Authored replacement artwork required to achieve replacement coverage (currently classic reference fallback).'
                )
                issues.append('CLASSIC_REFERENCE_FALLBACK')
                is_resolved = False
            elif runtime_support == 'UNSUPPORTED':
                category = 'RESOLVE_RUNTIME_SUPPORT'
                reason = 'RUNTIME_ACTION_UNSUPPORTED'
                action_needed = 'Action is unsupported by pinned Korangar runtime profile.'
                issues.append('RUNTIME_ACTION_UNSUPPORTED')
                is_resolved = False

            if a.get('transform_chain') and not a.get('transforms_executed'):
                issues.append('TRANSFORMS_UNEXECUTED')
            if (
                a.get('source_origin') == 'CLASSIC_REFERENCE'
                and not a.get('replacement_artwork')
                and 'CLASSIC_REFERENCE_FALLBACK' not in issues
            ):
                issues.append('CLASSIC_REFERENCE_FALLBACK')
            if (
                runtime_support == 'UNSUPPORTED'
                and 'RUNTIME_ACTION_UNSUPPORTED' not in issues
            ):
                issues.append('RUNTIME_ACTION_UNSUPPORTED')
            if aid in child_attachments:
                parent_aid = child_attachments[aid]['parent_assignment']
                parent_row = assignments_by_id.get(parent_aid)
                if (
                    parent_row is None
                    or parent_row['validation'] != 'VALID'
                    or parent_row['availability'] not in ('AVAILABLE', 'REUSED')
                    or parent_row['visual_review'] not in ('APPROVED', 'NOT_REQUIRED')
                ):
                    issues.append('UNVERIFIED_ATTACHMENT_PARENT')

        item = {
            'requirement_id': rid,
            'part': layer['part'],
            'action': layer['action'],
            'numeric_slot': layer.get('runtime_slot'),
            'view': layer['view'],
            'frame': layer['frame'],
            'layer': layer['ordinal'],
            'role': layer.get('role'),
            'requirement': req_type,
            'authority': layer.get('authority'),
            'assignment_id': aid,
            'source_id': sid,
            'dependency_chain': chain,
            'category': category,
            'reason': reason,
            'issues': issues,
            'action_needed': action_needed,
            'availability': avail,
            'validation': valid,
            'visual_review': review,
            'review_binding': review_b,
            'runtime_support': runtime_support,
        }
        occurrences.append(item)
        if not is_resolved:
            unresolved_items.append(item)
            if category:
                cat_counts[category.lower()] += 1

    # Underspecified slots
    for slot in requirements['slots']:
        if slot['resolution'] == 'UNDERSPECIFIED':
            reason = (
                'UNDERSPECIFIED_FRAME_COUNT'
                if slot['frame_count'] is None
                else 'UNDERSPECIFIED_LAYER_TOPOLOGY'
            )
            action_needed = 'Declare frame count and layer topology for slot.'
            slot_item = {
                'requirement_id': slot['id'],
                'part': slot['part'],
                'action': slot['action'],
                'numeric_slot': slot.get('runtime_slot'),
                'view': slot['view'],
                'frame': None,
                'layer': None,
                'role': None,
                'requirement': slot['requirement'],
                'authority': slot.get('authority'),
                'assignment_id': None,
                'source_id': None,
                'dependency_chain': [],
                'category': 'RESOLVE_REQUIREMENTS',
                'reason': reason,
                'issues': [reason],
                'action_needed': action_needed,
                'availability': 'UNVERIFIED',
                'validation': 'UNVERIFIED',
                'visual_review': 'UNVERIFIED',
                'review_binding': 'UNRECORDED',
                'runtime_support': slot.get('runtime_mapping', 'UNVERIFIED'),
            }
            unresolved_items.append(slot_item)
            cat_counts['resolve_requirements'] += 1

    # Calculate counts for required items
    req_occurrences = [o for o in occurrences if o['requirement'] == 'REQUIRED']

    required_slots = sum(
        s['requirement'] == 'REQUIRED' for s in requirements['slots']
    )
    optional_slots = sum(
        s['requirement'] == 'OPTIONAL' for s in requirements['slots']
    )
    underspecified_slots = sum(
        s['resolution'] == 'UNDERSPECIFIED' for s in requirements['slots']
    )
    unknown_fc_slots = sum(
        s['frame_count'] is None for s in requirements['slots']
    )

    required_frames = sum(
        f['requirement'] == 'REQUIRED' for f in requirements['frames']
    )
    optional_frames = sum(
        f['requirement'] == 'OPTIONAL' for f in requirements['frames']
    )
    underspecified_frames = sum(
        f['resolution'] == 'UNDERSPECIFIED' for f in requirements['frames']
    )

    required_layers = len(req_occurrences)
    optional_layers = len(occurrences) - required_layers

    direct_count = sum(
        1
        for o in req_occurrences
        if o['assignment_id'] and by_req[o['requirement_id']]['kind'] == 'DIRECT_SOURCE'
    )
    reuse_count = sum(
        1
        for o in req_occurrences
        if o['assignment_id'] and by_req[o['requirement_id']]['kind'] == 'EXPLICIT_REUSE'
    )
    unassigned_count = sum(o['assignment_id'] is None for o in req_occurrences)

    assigned_reqs = [
        by_req[o['requirement_id']] for o in req_occurrences if o['assignment_id']
    ]

    unique_sources = len(
        {a['effective_source']['id'] for a in assigned_reqs if a.get('effective_source')}
    )
    distinct_contents = len(
        {
            a['effective_source']['sha256']
            for a in assigned_reqs
            if a.get('effective_source') and a['effective_source'].get('sha256')
        }
    )
    approved_roots = len(
        {a['root_assignment'] for a in assigned_reqs if a.get('replacement_artwork')}
    )
    accepted_reuse_count = sum(
        1
        for a in assigned_reqs
        if a['kind'] == 'EXPLICIT_REUSE' and a.get('reuse_accepted')
    )
    validated_replacement = sum(
        1 for a in assigned_reqs if a.get('replacement_artwork')
    )

    assigned_req_occurrences = [
        o for o in req_occurrences if o['assignment_id'] is not None
    ]

    avail_sources = sum(o['availability'] == 'AVAILABLE' for o in assigned_req_occurrences)
    reused_sources = sum(o['availability'] == 'REUSED' for o in assigned_req_occurrences)
    missing_sources = sum(o['availability'] == 'MISSING' for o in assigned_req_occurrences)
    unverified_sources = sum(
        o['availability'] == 'UNVERIFIED' for o in assigned_req_occurrences
    )

    valid_assignments = sum(o['validation'] == 'VALID' for o in assigned_req_occurrences)
    invalid_assignments = sum(o['validation'] == 'INVALID' for o in assigned_req_occurrences)
    unverified_assignments = sum(
        o['validation'] == 'UNVERIFIED' for o in assigned_req_occurrences
    )

    approved_reviews = sum(
        o['visual_review'] == 'APPROVED' for o in assigned_req_occurrences
    )
    rejected_reviews = sum(
        o['visual_review'] == 'REJECTED' for o in assigned_req_occurrences
    )
    unverified_reviews = sum(
        o['visual_review'] == 'UNVERIFIED' for o in assigned_req_occurrences
    )
    not_required_reviews = sum(
        o['visual_review'] == 'NOT_REQUIRED' for o in assigned_req_occurrences
    )
    stale_reviews = sum(
        o['review_binding'] == 'STALE' for o in assigned_req_occurrences
    )

    image_decode_pending = len(assigned_reqs)
    transform_exec_pending = sum(
        1 for a in assigned_reqs if a.get('transform_chain')
    )

    # Status determination
    specified = (
        requirements['status']['specification'] == 'COMPLETE_FOR_DECLARED_SCOPE'
        and underspecified_slots == 0
    )
    full_profile_specified = specified and bool(
        requirements['status'].get('full_profile_specified', False)
    )

    all_required_assigned = required_layers > 0 and unassigned_count == 0
    all_required_approved_replacement = (
        required_layers > 0 and validated_replacement == required_layers
    )

    if full_profile_specified:
        structural_specification = 'COMPLETE_FOR_FULL_PROFILE'
    elif specified:
        structural_specification = 'COMPLETE_FOR_DECLARED_SCOPE'
    else:
        structural_specification = 'UNDERSPECIFIED'

    if all_required_assigned:
        if full_profile_specified:
            assignment_coverage = 'COMPLETE_FOR_FULL_PROFILE'
        else:
            assignment_coverage = 'COMPLETE_FOR_DECLARED_SCOPE'
    elif direct_count > 0 or reuse_count > 0:
        assignment_coverage = 'PARTIAL'
    else:
        assignment_coverage = 'UNASSIGNED'

    if specified and all_required_approved_replacement:
        if full_profile_specified:
            accepted_artwork_coverage = 'COMPLETE_FOR_FULL_PROFILE'
        else:
            accepted_artwork_coverage = 'COMPLETE_FOR_DECLARED_SCOPE'
    else:
        accepted_artwork_coverage = 'INCOMPLETE'

    if specified and all_required_approved_replacement:
        if full_profile_specified:
            completeness = 'COMPLETE_FOR_FULL_PROFILE'
        else:
            completeness = 'COMPLETE_FOR_DECLARED_SCOPE'
    elif not specified:
        completeness = 'UNDERSPECIFIED'
    else:
        completeness = 'INCOMPLETE'

    counts_payload = {
        'structural': {
            'required_slots': required_slots,
            'optional_slots': optional_slots,
            'required_frames': required_frames,
            'optional_frames': optional_frames,
            'required_layers': required_layers,
            'optional_layers': optional_layers,
            'underspecified_slots': underspecified_slots,
            'underspecified_frames': underspecified_frames,
            'unknown_frame_count_slots': unknown_fc_slots,
        },
        'assignments': {
            'direct': direct_count,
            'explicit_reuse': reuse_count,
            'unassigned': unassigned_count,
            'unique_selected_sources': unique_sources,
            'distinct_source_contents': distinct_contents,
            'approved_source_art_roots': approved_roots,
            'accepted_reuse': accepted_reuse_count,
            'validated_replacement_occurrences': validated_replacement,
        },
        'validation': {
            'available_sources': avail_sources,
            'reused_sources': reused_sources,
            'missing_sources': missing_sources,
            'unverified_sources': unverified_sources,
            'valid_assignments': valid_assignments,
            'invalid_assignments': invalid_assignments,
            'unverified_assignments': unverified_assignments,
        },
        'review': {
            'approved': approved_reviews,
            'rejected': rejected_reviews,
            'unverified': unverified_reviews,
            'not_required': not_required_reviews,
            'stale': stale_reviews,
        },
        'pending_technical_checks': {
            'image_decoding': image_decode_pending,
            'transformation_execution': transform_exec_pending,
        },
        'work_order_categories': cat_counts,
    }

    status_payload = {
        'completeness': completeness,
        'structural_specification': structural_specification,
        'full_profile_specified': full_profile_specified,
        'assignment_coverage': assignment_coverage,
        'accepted_artwork_coverage': accepted_artwork_coverage,
        'technical_validation': 'NOT_RUN',
        'preview_fidelity': 'UNVERIFIED',
        'native_evidence': 'UNVERIFIED',
        'export_ready': False,
    }

    result = {
        'schema': 'rsf.coverage-report/v1',
        'target': requirements['target'],
        'actor': requirements['actor'],
        'runtime_profile': requirements['runtime_profile'],
        'requirements_sha256': requirements['canonical_sha256'],
        'ledger_sha256': resolved_ledger.get('ledger_sha256'),
        'scope': requirements['scope'],
        'counts': counts_payload,
        'status': status_payload,
        'unresolved_items': unresolved_items,
        'occurrences': occurrences,
        'excluded_actions': sorted(set(excluded_actions)),
        'diagnostics': list(requirements.get('diagnostics', [])),
    }

    sealed_report = sealed(result)
    _shape(sealed_report, coverage_schema())
    return json.loads(canonical_bytes(sealed_report))


def format_work_order(
    report: dict,
    *,
    filter_category: str | None = None,
    filter_status: str | None = None,
) -> str:
    """Format human-readable actionable missing-art work order."""
    _validate_coverage_report(report)
    lines = [
        "=" * 80,
        "RO Sprite Forge — Missing-Art Work Order & Coverage Evaluation",
        "=" * 80,
        f"Target: {report['target']['id']} (revision {report['target']['revision']})",
        f"Target SHA-256: {report['target']['canonical_sha256']}",
        f"Scope: {report['scope']}",
        f"Actor: {report['actor']['id']} (revision {report['actor']['revision']})",
        f"Runtime Profile: {report['runtime_profile']['id']} (version {report['runtime_profile']['profile_version']})",
        f"Requirements SHA-256: {report['requirements_sha256']}",
        f"Ledger SHA-256: {report['ledger_sha256'] or 'NONE (unassigned)'}",
        "",
        "STATUS",
        "-" * 80,
        f"Overall Completeness:      {report['status']['completeness']}",
        f"Structural Specification:  {report['status']['structural_specification']}",
        f"Full Profile Specified:    {report['status']['full_profile_specified']}",
        f"Assignment Coverage:       {report['status']['assignment_coverage']}",
        f"Accepted Artwork Coverage: {report['status']['accepted_artwork_coverage']}",
        f"Technical Validation:      {report['status']['technical_validation']}",
        f"Preview Fidelity:          {report['status']['preview_fidelity']}",
        f"Native Evidence:           {report['status']['native_evidence']}",
        f"Export Ready:              {report['status']['export_ready']}",
        "",
        "REQUIREMENT & ASSIGNMENT COUNTS",
        "-" * 80,
        f"Action/View Slots:         {report['counts']['structural']['required_slots']} required "
        f"({report['counts']['structural']['optional_slots']} optional, "
        f"{report['counts']['structural']['underspecified_slots']} underspecified)",
        f"Frame Occurrences:         {report['counts']['structural']['required_frames']} required "
        f"({report['counts']['structural']['optional_frames']} optional, "
        f"{report['counts']['structural']['underspecified_frames']} underspecified)",
        f"Layer Occurrences:         {report['counts']['structural']['required_layers']} required "
        f"({report['counts']['structural']['optional_layers']} optional)",
        f"Direct Assignments:        {report['counts']['assignments']['direct']}",
        f"Explicit Reuse:            {report['counts']['assignments']['explicit_reuse']} "
        f"({report['counts']['assignments']['accepted_reuse']} accepted)",
        f"Unassigned Occurrences:    {report['counts']['assignments']['unassigned']}",
        f"Unique Selected Sources:   {report['counts']['assignments']['unique_selected_sources']}",
        f"Distinct Source Contents:  {report['counts']['assignments']['distinct_source_contents']}",
        f"Approved Source Roots:     {report['counts']['assignments']['approved_source_art_roots']}",
        f"Validated Replacement:     {report['counts']['assignments']['validated_replacement_occurrences']}",
        "",
        "VALIDATION & REVIEW COUNTS",
        "-" * 80,
        f"Sources:                   {report['counts']['validation']['available_sources']} available, "
        f"{report['counts']['validation']['reused_sources']} reused, "
        f"{report['counts']['validation']['missing_sources']} missing, "
        f"{report['counts']['validation']['unverified_sources']} unverified",
        f"Assignments Valid:         {report['counts']['validation']['valid_assignments']} valid, "
        f"{report['counts']['validation']['invalid_assignments']} invalid, "
        f"{report['counts']['validation']['unverified_assignments']} unverified",
        f"Visual Reviews:            {report['counts']['review']['approved']} approved, "
        f"{report['counts']['review']['rejected']} rejected, "
        f"{report['counts']['review']['unverified']} unverified, "
        f"{report['counts']['review']['not_required']} not_required, "
        f"{report['counts']['review']['stale']} stale",
        f"Pending Technical Checks:  {report['counts']['pending_technical_checks']['image_decoding']} image decoding (NOT_RUN), "
        f"{report['counts']['pending_technical_checks']['transformation_execution']} transform execution (NOT_RUN)",
        "",
        "WORK ORDER SUMMARY BY CATEGORY",
        "-" * 80,
    ]

    for cat, count in report['counts']['work_order_categories'].items():
        lines.append(f"{cat.upper():<38} {count:>5}")
    lines.append(f"{'TOTAL UNRESOLVED ITEMS:':<38} {len(report['unresolved_items']):>5}")
    lines.append("")

    # Filter items
    items = (
        report['occurrences']
        if filter_status == 'all'
        else report['unresolved_items']
    )
    if filter_category:
        norm_cat = filter_category.upper()
        items = [i for i in items if i.get('category') == norm_cat]

    label = f"ACTIONABLE WORK ORDER ITEMS ({len(items)} items)"
    if filter_category:
        label += f" [Filter: {filter_category.upper()}]"
    lines.extend([label, "-" * 80])

    if not items:
        lines.append("No items matching current filter.")
    else:
        for item in items:
            cat_str = f"[{item['category'] or 'RESOLVED'}]"
            lines.append(f"{cat_str} {item['requirement_id']}")
            pos = (
                f"  Part: {item['part']} | Action: {item['action']} | "
                f"Slot: {item['numeric_slot'] if item['numeric_slot'] is not None else 'None'} | "
                f"View: {item['view']}"
            )
            if item['frame'] is not None:
                pos += f" | Frame: {item['frame']}"
            if item['layer'] is not None:
                pos += f" | Layer: {item['layer']}"
            if item['role']:
                pos += f" (role: {item['role']})"
            pos += f" [{item['requirement']}]"
            lines.append(pos)

            asgn = (
                f"  Assignment: {item['assignment_id'] or 'UNASSIGNED'} | "
                f"Source: {item['source_id'] or 'None'}"
            )
            if item['dependency_chain']:
                asgn += f" | Lineage: {' -> '.join(item['dependency_chain'])}"
            lines.append(asgn)

            status_line = (
                f"  Validation: {item['validation']} | "
                f"Review: {item['visual_review']} (binding: {item['review_binding']}) | "
                f"Runtime: {item['runtime_support']}"
            )
            lines.append(status_line)

            if item['reason']:
                lines.append(f"  Issue: {item['reason']}")
            if item['issues'] and len(item['issues']) > 1:
                lines.append(f"  All Issues: {', '.join(item['issues'])}")
            if item['action_needed']:
                lines.append(f"  Action Needed: {item['action_needed']}")
            lines.append("")

    return "\n".join(lines) + "\n"
