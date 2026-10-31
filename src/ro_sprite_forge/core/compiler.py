"""Deterministic ACT 2.4 / SPR 2.1 compiler and metadata-preserving replacement writer (RSF-23).

Consumes audited ACT/SPR resources, resolved requirements, and canonical assignment ledgers
to produce modified ACT/SPR pairs while:
1. Preserving all unrelated actions, views, frames, layers, offsets, scales, rotations,
   tint/alpha colors, anchors, delays, sound events, and reserved header bytes.
2. Isolating shared SPR image references via copy-on-write pool appending whenever an
   original SPR image is referenced by any non-targeted ACT layer occurrence.
3. Enforcing single-execution of RSF-21 staged derived-image recipes (never reapplying
   staged transformations during compilation).
4. Enforcing pre-build operator visual review and distinguishing bounded replacement
   compilation from full-profile production export readiness.
5. Performing mandatory decode-after-write and pre/post semantic and pixel verification.
"""

from __future__ import annotations

import copy
from importlib.resources import files
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from typing import Any, Mapping, Sequence

from ro_sprite_forge.core.canonical import canonical_bytes, check, check_seal, digest, sealed
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.inventory import CONTENT_DOMAIN, inventory
from ro_sprite_forge.core.ledger import (
    AssignmentLedger,
    _validate_resolved_report,
    load_ledger,
    resolve_ledger,
)
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import (
    MAX_AGGREGATE_PIXELS,
    MAX_IMAGE_DIMENSION_PIXELS,
    MAX_SPR_IMAGES,
    IndexedImage,
    RgbaImage,
    SprDocument,
    encode_rle,
    read_spr,
    write_spr,
)
from ro_sprite_forge.core.build import BUILD_SCHEMA, canonical_build, cache_bundle, publish_bundle

WRITER_VERSION = "1.2.0"
COMPILATION_MANIFEST_SCHEMA = "rsf.compilation-manifest/v1"
COMPILATION_PLAN_SCHEMA = "rsf.compilation-plan/v1"

VALID_COMPILATION_MODES = ("preserve", "bounded_replacement", "production_export")
VALID_REPLACEMENT_POLICIES = ("preserve_pool", "explicit_rgba", "indexed_exact")
VALID_ISOLATION_STRATEGIES = ("auto", "always_append", "in_place_only")
VALID_PARTS = ("body", "head")
SUPPORTED_PNG_MODES = ("RGBA", "RGB", "LA", "L", "P")

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def compilation_manifest_schema() -> dict[str, Any]:
    """Return parsed Draft 2020-12 JSON Schema for rsf.compilation-manifest/v1."""
    content = files("ro_sprite_forge").joinpath("schemas/compilation-manifest-v1.json").read_text()
    return json.loads(content)


def validate_compilation_manifest(manifest: dict[str, Any]) -> None:
    """Validate canonical seal and required structural invariants of rsf.compilation-manifest/v1."""
    check_seal(manifest, COMPILATION_MANIFEST_SCHEMA)
    check(bool(_ID_RE.match(str(manifest.get("id", "")))), "Invalid compilation manifest id.")
    check(manifest.get("writer_version") in ("1.0.0", "1.1.0", WRITER_VERSION), "Invalid writer_version in manifest.")
    check(manifest.get("compilation_mode") in VALID_COMPILATION_MODES, "Invalid compilation_mode in manifest.")
    check(manifest.get("replacement_policy") in VALID_REPLACEMENT_POLICIES, "Invalid replacement_policy in manifest.")
    check(manifest.get("isolation_strategy") in VALID_ISOLATION_STRATEGIES, "Invalid isolation_strategy in manifest.")
    check(manifest.get("part") in VALID_PARTS, "Invalid part in manifest.")
    if manifest["writer_version"] in ("1.1.0", WRITER_VERSION):
        remapping = manifest.get("remapping")
        check(isinstance(remapping, dict), "INVALID_REMAPPING: writer 1.1.0 requires remapping evidence.")
        required = {"semantics", "ordering", "reuse", "input_counts", "output_counts", "palette_sha256", "before", "after", "unaffected_count", "conversion_loss"}
        check(set(remapping) == required, "INVALID_REMAPPING: incomplete remapping evidence.")
        targets = {(r["slot"], r["frame"], r["clip_ordinal"]): r for r in manifest["replacements"]}
        before, after = remapping["before"], remapping["after"]
        check(isinstance(before, list) and isinstance(after, list) and len(before) == len(after), "INVALID_REMAPPING: occurrence count differs.")
        check(len(before) - len(targets) == remapping["unaffected_count"], "INVALID_REMAPPING: unaffected count differs.")
        for key, resources in (("input_counts", "input_resources"), ("output_counts", "output_resources")):
            counts = remapping[key]
            check(counts == [manifest[resources]["spr"]["indexed_count"], manifest[resources]["spr"]["rgba_count"]], "INVALID_REMAPPING: pool counts differ.")
        previous = None
        for old, new in zip(before, after):
            loc = tuple(old.get(k) for k in ("slot", "frame", "layer"))
            check(all(type(n) is int and n >= 0 for n in loc) and (previous is None or loc > previous), "INVALID_REMAPPING: occurrence ordering differs.")
            previous = loc
            check(loc == tuple(new.get(k) for k in ("slot", "frame", "layer")), "INVALID_REMAPPING: occurrence identities differ.")
            for row, key in ((old, "input_counts"), (new, "output_counts")):
                pool, index = row.get("pool"), row.get("index")
                counts = remapping[key]
                check(pool in (0, 1) and type(index) is int and 0 <= index < counts[pool], "INVALID_REMAPPING: invalid pool/index.")
                check(row.get("texture_index") == index + (counts[0] if pool else 0), "INVALID_REMAPPING: texture index differs.")
                check(row.get("representation") == ("rgba" if pool else "indexed"), "INVALID_REMAPPING: representation differs.")
                check(all(_SHA256_RE.fullmatch(str(row.get(k, ""))) for k in ("decoded_rgba_sha256", "metadata_sha256")), "INVALID_REMAPPING: invalid occurrence hash.")
            check(old["metadata_sha256"] == new["metadata_sha256"], "INVALID_REMAPPING: layer metadata differs.")
            if loc in targets:
                for row, key in ((old, "original_image"), (new, "output_image")):
                    check(all(row[k] == targets[loc][key][k] for k in ("pool", "index", "decoded_rgba_sha256")), "INVALID_REMAPPING: replacement identity differs.")
            else:
                check(all(old[k] == new[k] for k in ("pool", "index", "decoded_rgba_sha256")), "INVALID_REMAPPING: unaffected identity differs.")
    if manifest["writer_version"] == WRITER_VERSION:
        build = manifest.get("build", {})
        check_seal(build, BUILD_SCHEMA)
        check(build["input_sha256"] == digest(canonical_bytes(build["inputs"])), "INVALID_BUILD_IDENTITY")
        check(build["inputs"]["approved_composition_sha256"] == digest(canonical_bytes(build["inputs"]["approved_composition"])), "INVALID_COMPOSITION_IDENTITY")
        check(build["remapping_sha256"] == digest(canonical_bytes(manifest["remapping"])), "INVALID_BUILD_REMAPPING")
        inputs = build["inputs"]
        check(inputs["source_sha256"] == {k: v["sha256"] if v else None for k, v in manifest["input_resources"].items()}, "INVALID_BUILD_RESOURCES")
        check(build["output_sha256"] == {k: v["sha256"] if v else None for k, v in manifest["output_resources"].items()}, "INVALID_BUILD_RESOURCES")
        check(all(inputs[k] == manifest[k] for k in ("target", "runtime_profile", "requirements_sha256", "writer_version")), "INVALID_BUILD_CONTRACT")
        check(inputs["output_policy"] == {k: manifest[k] for k in ("compilation_mode", "part", "replacement_policy", "isolation_strategy")}, "INVALID_BUILD_POLICY")
        composition = inputs["approved_composition"]
        check(all(composition[k] == manifest[k] for k in ("target", "runtime_profile")), "INVALID_BUILD_COMPOSITION")
        members = composition["members"]
        expected = sorted(manifest["replacements"], key=lambda r: r["requirement_id"])
        check(len(members) == len(expected) and all(
            (m["requirement_id"], m["assignment_composition_sha256"], m["source_sha256"], m["review_state"]) ==
            (r["requirement_id"], r["composition_sha256"], r["source_sha256"], r["review_state"])
            for m, r in zip(members, expected)), "INVALID_BUILD_MEMBERS")
        status = manifest["status"]
        production = manifest["compilation_mode"] == "production_export"
        check(status["production_authorized"] == production and status["export_ready"] == production,
              "INVALID_EXPORT_AUTHORIZATION")
        check(status["export_label"] == ("PRODUCTION" if production else "PRESERVED_REFERENCE" if manifest["compilation_mode"] == "preserve" else "PARTIAL_DIAGNOSTIC"), "INVALID_EXPORT_LABEL")
        check(not production or status["full_profile_completeness"] == "COMPLETE_FOR_FULL_PROFILE", "INVALID_EXPORT_COMPLETENESS")
    ver = manifest.get("verification", {})
    check(
        ver.get("decode_after_write") == "PASS"
        and ver.get("metadata_preservation") == "PASS"
        and ver.get("targeted_pixel_verification") == "PASS"
        and ver.get("unaffected_reference_preservation") == "PASS"
        and ver.get("shared_reference_isolation") == "PASS"
        and ver.get("native_korangar") == "UNVERIFIED",
        "Invalid verification block in compilation manifest.",
    )


def _decoded_rgba_digest(width: int, height: int, rgba_bytes: bytes) -> str:
    """Compute canonical decoded RGBA content SHA-256 matching inventory.py."""
    return digest(CONTENT_DOMAIN + struct.pack("<II", width, height) + rgba_bytes)


def _resolve_spr_image_rgba(spr_doc: SprDocument, pool: int, index: int) -> tuple[int, int, bytes]:
    """Resolve (width, height, top_down_rgba_bytes) for a (pool, index) in SprDocument."""
    if pool == 0:
        check(
            0 <= index < len(spr_doc.indexed_images),
            f"SPR_INDEX_OUT_OF_RANGE: indexed sprite {index} out of range [0, {len(spr_doc.indexed_images)})",
        )
        img = spr_doc.indexed_images[index]
        return img.width, img.height, img.to_rgba(spr_doc.palette)
    if pool == 1:
        check(
            0 <= index < len(spr_doc.rgba_images),
            f"SPR_INDEX_OUT_OF_RANGE: truecolor sprite {index} out of range [0, {len(spr_doc.rgba_images)})",
        )
        img = spr_doc.rgba_images[index]
        return img.width, img.height, img.rgba
    raise ForgeError(ErrorCode.INVALID_INPUT, f"UNSUPPORTED_SPR_POOL: invalid pool {pool}; expected 0 or 1.")


def image_reference_inventory(act: dict[str, Any], spr: SprDocument) -> list[dict[str, Any]]:
    """Ordered visible occurrences; ACT indices are pool-local, texture positions are not."""
    rows = []
    for slot, motions in enumerate(act["actions"]):
        for frame, motion in enumerate(motions):
            for layer, clip in enumerate(motion["clips"]):
                if clip["sprite"] == -1:
                    continue
                pool, index = clip["pool"], clip["sprite"]
                try:
                    w, h, rgba = _resolve_spr_image_rgba(spr, pool, index)
                except ForgeError as exc:
                    raise ForgeError(ErrorCode.INVALID_INPUT,
                        f"INVALID_IMAGE_REFERENCE: slot={slot} frame={frame} layer={layer} pool={pool} index={index}: {exc}") from exc
                metadata = {k: v for k, v in clip.items() if k not in ("pool", "sprite")}
                rows.append({"slot": slot, "frame": frame, "layer": layer,
                    "pool": pool, "index": index,
                    "texture_index": index + (spr.indexed_count if pool == 1 else 0),
                    "representation": "indexed" if pool == 0 else "rgba",
                    "decoded_rgba_sha256": _decoded_rgba_digest(w, h, rgba),
                    "metadata_sha256": digest(canonical_bytes(metadata))})
    return rows


def _remapping_evidence(orig_act, orig_spr, out_act, out_spr, replacements):
    before = image_reference_inventory(orig_act, orig_spr)
    after = image_reference_inventory(out_act, out_spr)
    targets = {(r["slot"], r["frame"], r["clip_ordinal"]) for r in replacements}
    return {"semantics": "act-pool-local/v1", "ordering": "original-pools-then-canonical-occurrence-appends/v1",
        "reuse": "exact-encoded-replacement-content-within-pool/v1",
        "input_counts": [orig_spr.indexed_count, orig_spr.rgba_count],
        "output_counts": [out_spr.indexed_count, out_spr.rgba_count],
        "palette_sha256": digest(out_spr.palette),
        "before": before, "after": after,
        "unaffected_count": len(before) - len(targets),
        "conversion_loss": [{"requirement_id": r["requirement_id"],
            "loss": "replacement-does-not-retain-original-palette-indices",
            "original_palette_and_entries_retained": True}
            for r in replacements if r["original_image"]["pool"] == 0 and r["output_image"]["pool"] == 1]}


def _decode_source_image(
    source_id: str,
    declared_sha256: str | None,
    raw_bytes: bytes | None,
) -> dict[str, Any]:
    """Verify staged source bytes and decode supported 8-bit PNG into top-down RGBA."""
    if raw_bytes is None:
        raise ForgeError(
            ErrorCode.INPUT_NOT_FOUND,
            f"MISSING_REPLACEMENT_SOURCE: staged bytes for source '{source_id}' are unavailable.",
        )
    if not isinstance(raw_bytes, bytes) or len(raw_bytes) == 0:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"EMPTY_REPLACEMENT_SOURCE: staged bytes for source '{source_id}' are empty.",
        )
    actual_sha = digest(raw_bytes)
    if not declared_sha256 or not _SHA256_RE.match(declared_sha256):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"SOURCE_HASH_UNDECLARED: source '{source_id}' lacks a valid SHA-256 declaration.",
        )
    if actual_sha != declared_sha256:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"SOURCE_HASH_MISMATCH: source '{source_id}' expected {declared_sha256}, got {actual_sha}.",
        )

    from PIL import Image

    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            fmt = im.format
            mode = im.mode
            width, height = im.size
            if fmt != "PNG":
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"UNSUPPORTED_IMAGE_FORMAT: source '{source_id}' format is {fmt!r}; only PNG is supported.",
                )
            if mode not in SUPPORTED_PNG_MODES:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"UNSUPPORTED_PIXEL_REPRESENTATION: source '{source_id}' mode {mode!r} is unsupported.",
                )
            if width <= 0 or height <= 0 or width > 0xFFFF or height > 0xFFFF:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"INVALID_IMAGE_DIMENSIONS: source '{source_id}' size {width}x{height} out of SPR uint16 bounds.",
                )
            if width * height > MAX_IMAGE_DIMENSION_PIXELS:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"INVALID_IMAGE_DIMENSIONS: source '{source_id}' exceeds {MAX_IMAGE_DIMENSION_PIXELS} pixels.",
                )
            rgba_im = im.convert("RGBA")
            rgba_bytes = rgba_im.tobytes()
    except ForgeError:
        raise
    except Exception as exc:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"UNDECODABLE_REPLACEMENT_SOURCE: source '{source_id}' could not be decoded as a valid PNG: {exc}",
        ) from exc

    alphas = rgba_bytes[3::4]
    has_semitransparent = any(0 < a < 255 for a in alphas)
    return {
        "width": width,
        "height": height,
        "mode": mode,
        "rgba_bytes": rgba_bytes,
        "has_semitransparent": has_semitransparent,
        "actual_sha256": actual_sha,
    }


def _apply_ledger_transform_chain(
    width: int,
    height: int,
    rgba_bytes: bytes,
    transform_chain: list[dict[str, Any]],
    *,
    requirement_id: str,
) -> tuple[int, int, bytes, list[str]]:
    """Execute supported ledger-level operations (mirror_x only); reject unexecuted ops."""
    if not transform_chain:
        return width, height, rgba_bytes, []

    from PIL import Image

    im = Image.frombytes("RGBA", (width, height), rgba_bytes)
    executed_ops: list[str] = []
    for step in transform_chain:
        op_spec = step.get("operation") if isinstance(step, dict) else None
        op_name = op_spec.get("op") if isinstance(op_spec, dict) else None
        if op_name != "mirror_x":
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"UNSUPPORTED_LEDGER_TRANSFORMATION: requirement '{requirement_id}' has unexecuted ledger operation {op_name!r}; "
                "stage a derived image via RSF-21 instead.",
            )
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        executed_ops.append("mirror_x")

    return im.width, im.height, im.tobytes(), executed_ops


def _encode_image_for_pool(
    width: int,
    height: int,
    rgba_bytes: bytes,
    target_pool: int,
    palette: bytes,
    *,
    requirement_id: str,
    orig_pool: int,
) -> tuple[IndexedImage | RgbaImage, list[str]]:
    """Encode RGBA pixels into target SPR pool (0=indexed, 1=truecolor) without silent quantization."""
    notes: list[str] = []
    if target_pool == 1:
        if orig_pool == 0:
            notes.append("INDEXED_CLIP_REMAPPED_TO_RGBA_POOL")
            notes.append("REPLACEMENT_PALETTE_INDEX_INFORMATION_LOST_ORIGINAL_RETAINED")
        notes.append("ENCODED_TRUECOLOR_RGBA")
        return RgbaImage(width=width, height=height, rgba=rgba_bytes), notes

    if target_pool == 0:
        check(len(palette) == 1024, "Invalid SPR 2.1 palette length.")
        palette_lookup: dict[tuple[int, int, int], int] = {}
        for idx in range(1, 256):
            rgb = (palette[idx * 4], palette[idx * 4 + 1], palette[idx * 4 + 2])
            if rgb not in palette_lookup:
                palette_lookup[rgb] = idx

        indices = bytearray(width * height)
        for p_idx in range(width * height):
            base = p_idx * 4
            r = rgba_bytes[base]
            g = rgba_bytes[base + 1]
            b = rgba_bytes[base + 2]
            a = rgba_bytes[base + 3]
            if a == 0:
                check((r, g, b) == (0, 0, 0),
                    f"UNSUPPORTED_INDEXED_CONVERSION: requirement '{requirement_id}' has nonzero RGB beneath transparent alpha; exact indexed conversion would lose pixel information.")
                indices[p_idx] = 0
            elif a < 255:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"UNSUPPORTED_INDEXED_CONVERSION: requirement '{requirement_id}' contains semitransparent alpha ({a}); "
                    "SPR 2.1 indexed pool only supports binary transparency (index 0). Use explicit_rgba policy.",
                )
            else:
                pal_idx = palette_lookup.get((r, g, b))
                if pal_idx is None:
                    raise ForgeError(
                        ErrorCode.INVALID_INPUT,
                        f"UNSUPPORTED_INDEXED_CONVERSION: requirement '{requirement_id}' contains opaque RGB color ({r}, {g}, {b}) "
                        "absent from the SPR 2.1 palette; silent palette quantization is forbidden.",
                    )
                indices[p_idx] = pal_idx

        idx_bytes = bytes(indices)
        rle_bytes = encode_rle(idx_bytes)
        if orig_pool == 1:
            notes.append("RGBA_CLIP_REMAPPED_TO_INDEXED_POOL")
        notes.append("ENCODED_LOSSLESS_INDEXED_RLE")
        return (
            IndexedImage(
                width=width,
                height=height,
                pixels=idx_bytes,
                rle_length=len(rle_bytes),
                raw_rle=rle_bytes,
            ),
            notes,
        )

    raise ForgeError(ErrorCode.INVALID_INPUT, f"UNSUPPORTED_SPR_POOL: target pool {target_pool} is invalid.")


def _resolve_ledger_and_reviews(
    requirements: dict[str, Any],
    ledger: AssignmentLedger | dict[str, Any],
    source_bytes: Mapping[str, bytes | None] | None,
    *,
    reviewed_ledger: dict[str, Any] | None = None,
    review_events: list[dict[str, Any]] | None = None,
    project_id: str | None = None,
    expected_ledger_revision: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and resolve ledger declaration or report, applying review events if provided."""
    if isinstance(ledger, AssignmentLedger):
        ledger_doc = ledger.to_dict()
        loaded = load_ledger(ledger_doc, requirements=requirements)
        if expected_ledger_revision is not None:
            check(
                ledger_doc["revision"] == expected_ledger_revision,
                f"STALE_LEDGER_REVISION: expected {expected_ledger_revision}, got {ledger_doc['revision']}.",
            )
        resolved = resolve_ledger(loaded, requirements=requirements, source_bytes=source_bytes)
        ledger_ref = {
            "id": ledger_doc["id"],
            "revision": ledger_doc["revision"],
            "canonical_sha256": loaded.canonical_sha256,
        }
    elif isinstance(ledger, dict) and ledger.get("schema") == "rsf.assignment-ledger/v1":
        loaded = load_ledger(ledger, requirements=requirements)
        ledger_doc = loaded.to_dict()
        if expected_ledger_revision is not None:
            check(
                ledger_doc["revision"] == expected_ledger_revision,
                f"STALE_LEDGER_REVISION: expected {expected_ledger_revision}, got {ledger_doc['revision']}.",
            )
        if reviewed_ledger is not None:
            _validate_resolved_report(reviewed_ledger)
            check(
                reviewed_ledger["target"] == requirements["target"],
                "STALE_TARGET_REVISION_OR_IDENTITY: reviewed ledger target does not match requirements.",
            )
            check(
                reviewed_ledger["requirements_sha256"] == requirements["canonical_sha256"],
                "CHANGED_REQUIREMENTS: reviewed ledger requirements_sha256 mismatch.",
            )
            fresh = resolve_ledger(loaded, requirements=requirements, source_bytes=source_bytes)
            keys = ("id", "revision", "requirement_id", "composition_sha256", "effective_source",
                    "availability", "validation", "lineage", "transform_chain")
            project = lambda report: sorted(
                [{k: row[k] for k in keys} for row in report["assignments"]], key=lambda row: row["id"])
            check(project(fresh) == project(reviewed_ledger),
                  "STALE_REVIEWED_LEDGER: review projection differs from current assignments or source observations.")
            resolved = reviewed_ledger
        else:
            resolved = resolve_ledger(loaded, requirements=requirements, source_bytes=source_bytes)
            if review_events is not None:
                from ro_sprite_forge.core.review import apply_reviews, evaluate_reviews

                pid = project_id or "local-project"
                status = evaluate_reviews(pid, review_events, requirements, resolved, None)
                resolved = apply_reviews(resolved, status, ledger_doc, requirements, source_bytes)
        ledger_ref = {
            "id": ledger_doc["id"],
            "revision": ledger_doc["revision"],
            "canonical_sha256": loaded.canonical_sha256,
        }
    elif isinstance(ledger, dict) and ledger.get("schema") == "rsf.resolved-ledger/v1":
        _validate_resolved_report(ledger)
        check(
            ledger["target"] == requirements["target"],
            "STALE_TARGET_REVISION_OR_IDENTITY: resolved ledger target does not match requirements.",
        )
        check(
            ledger["requirements_sha256"] == requirements["canonical_sha256"],
            "CHANGED_REQUIREMENTS: resolved ledger requirements_sha256 mismatch.",
        )
        resolved = ledger
        ledger_ref = {
            "id": ledger["target"]["id"] + "-ledger",
            "revision": max([a["revision"] for a in ledger.get("assignments", [])] or [1]),
            "canonical_sha256": ledger["ledger_sha256"],
        }
        if expected_ledger_revision is not None:
            check(
                ledger_ref["revision"] == expected_ledger_revision,
                f"STALE_LEDGER_REVISION: expected {expected_ledger_revision}, got {ledger_ref['revision']}.",
            )
    else:
        raise ForgeError(ErrorCode.INVALID_INPUT, "INVALID_LEDGER_CONTRACT: expected rsf.assignment-ledger/v1 or rsf.resolved-ledger/v1.")

    return resolved, ledger_ref


def _production_scope_ready(requirements, coverage, selected, part):
    required = {layer["id"] for layer in requirements["layers"] if layer["requirement"] == "REQUIRED"}
    return bool(required and required <= set(selected)
                and all(layer["part"] == part for layer in requirements["layers"] if layer["id"] in required)
                and coverage["status"]["completeness"] == "COMPLETE_FOR_FULL_PROFILE")


def _finish_build_manifest(manifest, requirements=None, resolved=None, selected=(), coverage=None):
    value = {k: v for k, v in manifest.items() if k != "canonical_sha256"}
    value["build"] = canonical_build(value, requirements, resolved, selected)
    state = coverage["status"] if coverage else {}
    value["status"].update(
        export_label="PRODUCTION" if value["compilation_mode"] == "production_export" else
            "PRESERVED_REFERENCE" if value["compilation_mode"] == "preserve" else "PARTIAL_DIAGNOSTIC",
        declared_scope_completeness=state.get("completeness", "NOT_EVALUATED"),
        full_profile_completeness="COMPLETE_FOR_FULL_PROFILE" if state.get("completeness") == "COMPLETE_FOR_FULL_PROFILE" else "INCOMPLETE",
    )
    return sealed(value)


def _compilation_slot(layer, mode):
    offline = layer.get("offline")
    if offline is not None:
        check(mode != "production_export", "RUNTIME_ACTION_MAPPING_UNAVAILABLE: offline actions cannot authorize production export.")
        authority = layer.get("authority") or {}
        check(offline["compilation"] == "BOUND_EXISTING_SLOT_DIAGNOSTIC" and authority.get("kind") == "inherited",
              "UNSUPPORTED_ACT_SLOT: offline action has no explicit diagnostic storage binding.")
        check(layer.get("runtime_slot") is None, "CONFLICTING_NATIVE_ACTION_BINDING: offline actions cannot claim runtime slots.")
        return authority["source_slot"]
    return layer["runtime_slot"]


def plan_compilation(
    act_bytes: bytes,
    spr_bytes: bytes,
    *,
    requirements: dict[str, Any] | None = None,
    ledger: AssignmentLedger | dict[str, Any] | None = None,
    reviewed_ledger: dict[str, Any] | None = None,
    source_bytes: Mapping[str, bytes | None] | None = None,
    source_metadata: Mapping[str, dict[str, Any]] | None = None,
    review_events: list[dict[str, Any]] | None = None,
    project_id: str | None = None,
    replacement_requirement_ids: Sequence[str] | None = None,
    part: str = "body",
    compilation_mode: str = "bounded_replacement",
    replacement_policy: str = "preserve_pool",
    isolation_strategy: str = "auto",
    output_prefix: str = "compiled",
) -> dict[str, Any]:
    """Build an inspectable pre-compilation plan reporting scope, readiness, and blockers."""
    check(part in VALID_PARTS, f"INVALID_PART: unsupported part {part!r}.")
    check(compilation_mode in VALID_COMPILATION_MODES, f"INVALID_COMPILATION_MODE: unsupported mode {compilation_mode!r}.")
    check(replacement_policy in VALID_REPLACEMENT_POLICIES, f"INVALID_REPLACEMENT_POLICY: unsupported policy {replacement_policy!r}.")
    check(isolation_strategy in VALID_ISOLATION_STRATEGIES, f"INVALID_ISOLATION_STRATEGY: unsupported strategy {isolation_strategy!r}.")
    check(bool(_ID_RE.match(output_prefix)), "INVALID_OUTPUT_PREFIX: must be 1..64 alphanumeric, '_' or '-' chars.")

    orig_act = read_act(act_bytes)
    orig_spr = read_spr(spr_bytes)
    image_reference_inventory(orig_act, orig_spr)
    _ = inventory(act_bytes, spr_bytes)

    input_summary = {
        "act_sha256": digest(act_bytes),
        "spr_sha256": digest(spr_bytes),
        "act_slots": len(orig_act["actions"]),
        "spr_indexed_count": orig_spr.indexed_count,
        "spr_rgba_count": orig_spr.rgba_count,
    }

    if compilation_mode == "preserve":
        plan = {
            "schema": COMPILATION_PLAN_SCHEMA,
            "writer_version": WRITER_VERSION,
            "part": part,
            "compilation_mode": compilation_mode,
            "replacement_policy": replacement_policy,
            "isolation_strategy": isolation_strategy,
            "target": None,
            "input_summary": input_summary,
            "expected_outputs": {
                "act_filename": f"{output_prefix}.act",
                "spr_filename": f"{output_prefix}.spr",
                "manifest_filename": "compilation-manifest.json",
            },
            "selected_replacements": [],
            "unsupported_features": [],
            "blockers": [],
            "ready_to_compile": True,
            "production_authorized": False,
            "export_ready": False,
            "experimental_bounded_output": False,
        }
        return sealed(plan)

    check(requirements is not None and ledger is not None, "MISSING_COMPILATION_CONTRACTS: requirements and ledger are required.")
    check_seal(requirements, "rsf.resolved-requirements/v1")
    resolved_report, ledger_ref = _resolve_ledger_and_reviews(
        requirements,
        ledger,
        source_bytes,
        reviewed_ledger=reviewed_ledger,
        review_events=review_events,
        project_id=project_id,
    )
    coverage = evaluate_coverage(requirements, ledger=resolved_report, source_bytes=source_bytes)

    req_layers = {l["id"]: l for l in requirements["layers"]}
    req_frames = {f["id"]: f for f in requirements["frames"]}
    assign_by_req = {a["requirement_id"]: a for a in resolved_report["assignments"]}

    if replacement_requirement_ids is not None:
        selected_ids = list(replacement_requirement_ids)
    else:
        selected_ids = [
            a["requirement_id"]
            for a in resolved_report["assignments"]
            if a["kind"] != "UNASSIGNED" and req_layers.get(a["requirement_id"], {}).get("part") == part
        ]

    blockers: list[str] = []
    unsupported_features: list[str] = []
    planned_items: list[dict[str, Any]] = []

    if not selected_ids:
        blockers.append("EMPTY_REPLACEMENT_SCOPE: no replacement requirements selected.")

    if compilation_mode == "production_export" and not _production_scope_ready(requirements, coverage, selected_ids, part):
        blockers.append("PRODUCTION_EXPORT_NOT_READY: full profile coverage or operator review is incomplete.")

    for rid in selected_ids:
        if rid not in req_layers:
            blockers.append(f"UNRESOLVED_REQUIREMENT_ID: {rid}")
            continue
        layer = req_layers[rid]
        if layer["part"] != part:
            blockers.append(f"PART_MISMATCH: {rid} belongs to {layer['part']}, expected {part}")
            continue
        try:
            slot = _compilation_slot(layer, compilation_mode)
        except ForgeError as exc:
            blockers.append(str(exc))
            continue
        frame_idx = layer["frame"]
        layer_ord = layer["ordinal"]
        if slot is None or not (0 <= slot < len(orig_act["actions"])):
            unsupported_features.append(f"UNSUPPORTED_ACT_SLOT: {rid} maps to slot {slot}")
            blockers.append(f"UNSUPPORTED_ACT_SLOT: {rid}")
            continue
        motions = orig_act["actions"][slot]
        if not (0 <= frame_idx < len(motions)):
            unsupported_features.append(f"UNSUPPORTED_ACT_FRAME: {rid} maps to frame {frame_idx}")
            blockers.append(f"UNSUPPORTED_ACT_FRAME: {rid}")
            continue
        motion = motions[frame_idx]
        visible_indices = [i for i, c in enumerate(motion["clips"]) if c["sprite"] >= 0]
        frame_req = req_frames[layer["frame_id"]]
        if len(visible_indices) != frame_req["layer_count"]:
            unsupported_features.append(
                f"UNSUPPORTED_LAYER_STRUCTURE: slot {slot} frame {frame_idx} has {len(visible_indices)} visible clips, topology declares {frame_req['layer_count']}"
            )
            blockers.append(f"UNSUPPORTED_LAYER_STRUCTURE: {rid}")
            continue

        row = assign_by_req.get(rid)
        if row is None or row["kind"] == "UNASSIGNED":
            blockers.append(f"UNASSIGNED_REPLACEMENT_REQUIREMENT: {rid}")
            continue
        eff_src = row.get("effective_source")
        if eff_src is None or row["availability"] not in ("AVAILABLE", "REUSED") or row["validation"] != "VALID":
            blockers.append(f"INVALID_OR_MISSING_SOURCE: {rid}")
            continue
        if row["review_binding"] == "STALE":
            blockers.append(f"STALE_REVIEW_APPROVAL: {rid}")
        elif row["visual_review"] not in ("APPROVED", "NOT_REQUIRED") or row["review_binding"] != "BOUND_OPERATOR_DECLARATION":
            blockers.append(f"UNAPPROVED_REPLACEMENT_ARTWORK: {rid} is {row['visual_review']}")

        for step in row.get("transform_chain", []):
            op_name = step.get("operation", {}).get("op")
            if op_name != "mirror_x":
                unsupported_features.append(f"UNSUPPORTED_LEDGER_TRANSFORMATION: {op_name}")
                blockers.append(f"UNSUPPORTED_LEDGER_TRANSFORMATION: {rid}")

        planned_items.append({
            **(dict(runtime_slot=None, diagnostic_storage_slot=slot, runtime_mapping="UNSUPPORTED") if layer.get("offline") else {}),
            "requirement_id": rid,
            "assignment_id": row["id"],
            "slot": slot,
            "action": layer["action"],
            "view": layer["view"],
            "frame": frame_idx,
            "layer_ordinal": layer_ord,
            "source_id": eff_src["id"],
            "source_sha256": eff_src["sha256"],
            "visual_review": row["visual_review"],
            "review_binding": row["review_binding"],
        })

    export_ready = False
    production_authorized = bool(compilation_mode == "production_export" and export_ready and not blockers)

    plan = {
        "schema": COMPILATION_PLAN_SCHEMA,
        "writer_version": WRITER_VERSION,
        "part": part,
        "compilation_mode": compilation_mode,
        "replacement_policy": replacement_policy,
        "isolation_strategy": isolation_strategy,
        "target": requirements["target"],
        "ledger": ledger_ref,
        "input_summary": input_summary,
        "expected_outputs": {
            "act_filename": f"{output_prefix}.act",
            "spr_filename": f"{output_prefix}.spr",
            "manifest_filename": "compilation-manifest.json",
        },
        "selected_replacements": planned_items,
        "unsupported_features": unsupported_features,
        "blockers": blockers,
        "ready_to_compile": len(blockers) == 0,
        "production_authorized": production_authorized,
        "export_ready": export_ready,
        "experimental_bounded_output": compilation_mode == "bounded_replacement",
    }
    if not blockers:
        try:
            candidate = compile_resources(act_bytes, spr_bytes, requirements=requirements,
                ledger=ledger, reviewed_ledger=reviewed_ledger, source_bytes=source_bytes,
                source_metadata=source_metadata, review_events=review_events, project_id=project_id,
                replacement_requirement_ids=replacement_requirement_ids, part=part,
                compilation_mode=compilation_mode, replacement_policy=replacement_policy,
                isolation_strategy=isolation_strategy, output_prefix=output_prefix)
            plan["build"] = candidate["manifest"]["build"]
            plan["export_label"] = candidate["manifest"]["status"]["export_label"]
            plan["export_ready"] = candidate["manifest"]["status"]["export_ready"]
            plan["production_authorized"] = candidate["manifest"]["status"]["production_authorized"]
            plan["remapping"] = candidate["manifest"]["remapping"]
            plan["selected_replacements"] = candidate["manifest"]["replacements"]
            for item in plan["selected_replacements"]:
                if req_layers[item["requirement_id"]].get("offline"):
                    item.update(runtime_slot=None, diagnostic_storage_slot=item["slot"],
                                runtime_mapping="UNSUPPORTED")
        except ForgeError as exc:
            blockers.append(str(exc))
            plan["ready_to_compile"] = False
            plan["production_authorized"] = False
    return sealed(plan)


def verify_pair_with_rust_oracle(
    act_bytes: bytes,
    spr_bytes: bytes,
    oracle_executable: str | Path,
) -> dict[str, Any]:
    """Run independent Rust oracle binary on ACT/SPR bytes and verify exact structural/pixel parity."""
    exe_path = Path(oracle_executable).resolve()
    if not exe_path.is_file():
        raise ForgeError(
            ErrorCode.INPUT_NOT_FOUND,
            f"RUST_ORACLE_NOT_FOUND: executable not found at {exe_path.name}.",
        )

    # Build Python oracle structure report (matching tools/rust-oracle/parity.py)
    inventory(act_bytes, spr_bytes)
    a = copy.deepcopy(read_act(act_bytes))
    a["version"] = "2.4"
    a["delays"] = [struct.unpack("<I", struct.pack("<f", v))[0] for v in a["delays"]]
    for action in a["actions"]:
        for motion in action:
            motion["bounds"] = list(motion["bounds"])
            for layer in motion["clips"]:
                for k in ("scale_x", "scale_y"):
                    layer[k] = struct.unpack("<I", struct.pack("<f", layer[k]))[0]
    s = read_spr(spr_bytes)
    images = []
    for pool, entries in enumerate((s.indexed_images, s.rgba_images)):
        for index, image in enumerate(entries):
            images.append({
                "pool": pool,
                "index": index,
                "width": image.width,
                "height": image.height,
                "indices": image.pixels.hex() if pool == 0 else None,
                "rgba": (image.to_rgba(s.palette) if pool == 0 else image.rgba).hex(),
            })
    py_report = {
        "schema": "rsf.oracle-structure/v1",
        "sources": {"act": digest(act_bytes), "spr": digest(spr_bytes)},
        "act": a,
        "spr": {
            "version": "2.1",
            "indexed_count": s.indexed_count,
            "truecolor_count": s.rgba_count,
            "palette": s.palette.hex(),
            "images": images,
        },
    }

    with tempfile.TemporaryDirectory(prefix="rsf23-oracle-") as tmp:
        tmp_dir = Path(tmp)
        act_file = tmp_dir / "compiled.act"
        spr_file = tmp_dir / "compiled.spr"
        act_file.write_bytes(act_bytes)
        spr_file.write_bytes(spr_bytes)
        proc = subprocess.run(
            [str(exe_path), str(act_file), str(spr_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"RUST_ORACLE_REJECTED_BINARY: exit={proc.returncode} stderr={proc.stderr.strip()}",
            )
        rust_report = json.loads(proc.stdout)

    py_bytes = canonical_bytes(py_report)
    rust_bytes = canonical_bytes(rust_report)
    if py_bytes != rust_bytes:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            "RUST_ORACLE_PARITY_MISMATCH: Python and Rust oracle decoded structures differ.",
        )

    return sealed({
        "schema": "rsf.oracle-parity/v1",
        "result": "AGREEMENT",
        "sources": py_report["sources"],
        "python_report_sha256": digest(py_bytes),
        "rust_report_sha256": digest(rust_bytes),
    })


def compile_resources(
    act_bytes: bytes,
    spr_bytes: bytes,
    *,
    requirements: dict[str, Any] | None = None,
    ledger: AssignmentLedger | dict[str, Any] | None = None,
    reviewed_ledger: dict[str, Any] | None = None,
    source_bytes: Mapping[str, bytes | None] | None = None,
    source_metadata: Mapping[str, dict[str, Any]] | None = None,
    review_events: list[dict[str, Any]] | None = None,
    project_id: str | None = None,
    replacement_requirement_ids: Sequence[str] | None = None,
    compilation_id: str = "compile-default",
    part: str = "body",
    compilation_mode: str = "bounded_replacement",
    replacement_policy: str = "preserve_pool",
    isolation_strategy: str = "auto",
    expected_act_sha256: str | None = None,
    expected_spr_sha256: str | None = None,
    expected_target_revision: int | None = None,
    expected_ledger_revision: int | None = None,
    head_act_bytes: bytes | None = None,
    head_spr_bytes: bytes | None = None,
    expected_head_act_sha256: str | None = None,
    expected_head_spr_sha256: str | None = None,
    output_prefix: str = "compiled",
    oracle_executable: str | Path | None = None,
) -> dict[str, Any]:
    """Compile modified ACT 2.4 / SPR 2.1 resources with copy-on-write shared-reference isolation.

    Returns a dictionary containing:
    - 'manifest': sealed rsf.compilation-manifest/v1 dictionary
    - 'act_bytes': compiled ACT 2.4 binary bytes
    - 'spr_bytes': compiled SPR 2.1 binary bytes
    - 'head_act_bytes': unchanged head ACT bytes (if supplied)
    - 'head_spr_bytes': unchanged head SPR bytes (if supplied)
    """
    check(
        isinstance(compilation_id, str) and bool(_ID_RE.match(compilation_id)),
        "INVALID_COMPILATION_ID: must be 1..64 alphanumeric, '_' or '-' chars.",
    )
    check(part in VALID_PARTS, f"INVALID_PART: unsupported part {part!r}; expected 'body' or 'head'.")
    check(
        compilation_mode in VALID_COMPILATION_MODES,
        f"INVALID_COMPILATION_MODE: unsupported compilation_mode {compilation_mode!r}.",
    )
    check(
        replacement_policy in VALID_REPLACEMENT_POLICIES,
        f"INVALID_REPLACEMENT_POLICY: unsupported replacement_policy {replacement_policy!r}.",
    )
    check(
        isolation_strategy in VALID_ISOLATION_STRATEGIES,
        f"INVALID_ISOLATION_STRATEGY: unsupported isolation_strategy {isolation_strategy!r}.",
    )
    check(
        isinstance(output_prefix, str) and bool(_ID_RE.match(output_prefix)),
        "INVALID_OUTPUT_PREFIX: must be 1..64 alphanumeric, '_' or '-' chars.",
    )

    check(isinstance(act_bytes, bytes) and len(act_bytes) > 0, "MISSING_ORIGINAL_ACT: ACT bytes must be non-empty.")
    check(isinstance(spr_bytes, bytes) and len(spr_bytes) > 0, "MISSING_ORIGINAL_SPR: SPR bytes must be non-empty.")

    input_act_sha = digest(act_bytes)
    input_spr_sha = digest(spr_bytes)
    if expected_act_sha256 is not None:
        check(
            input_act_sha == expected_act_sha256,
            f"ACT_RESOURCE_HASH_MISMATCH: expected {expected_act_sha256}, got {input_act_sha}.",
        )
    if expected_spr_sha256 is not None:
        check(
            input_spr_sha == expected_spr_sha256,
            f"SPR_RESOURCE_HASH_MISMATCH: expected {expected_spr_sha256}, got {input_spr_sha}.",
        )

    # Decode and validate original pair using audited M0 codecs and inventory
    orig_act = read_act(act_bytes)
    orig_spr = read_spr(spr_bytes)
    image_reference_inventory(orig_act, orig_spr)
    _ = inventory(act_bytes, spr_bytes)

    # Validate optional head resource pair
    head_act_info = None
    head_spr_info = None
    out_head_act_info = None
    out_head_spr_info = None
    if head_act_bytes is not None or head_spr_bytes is not None:
        check(
            isinstance(head_act_bytes, bytes) and isinstance(head_spr_bytes, bytes),
            "HEAD_RESOURCE_PAIR_INCOMPLETE: supply both head_act_bytes and head_spr_bytes.",
        )
        h_act_sha = digest(head_act_bytes)
        h_spr_sha = digest(head_spr_bytes)
        if expected_head_act_sha256 is not None:
            check(h_act_sha == expected_head_act_sha256, "HEAD_ACT_HASH_MISMATCH")
        if expected_head_spr_sha256 is not None:
            check(h_spr_sha == expected_head_spr_sha256, "HEAD_SPR_HASH_MISMATCH")
        h_spr_doc = read_spr(head_spr_bytes)
        _ = inventory(head_act_bytes, head_spr_bytes)
        head_act_info = {"format": "ACT 2.4", "bytes": len(head_act_bytes), "sha256": h_act_sha}
        head_spr_info = {
            "format": "SPR 2.1",
            "bytes": len(head_spr_bytes),
            "sha256": h_spr_sha,
            "indexed_count": h_spr_doc.indexed_count,
            "rgba_count": h_spr_doc.rgba_count,
        }
        out_head_act_info = {
            "format": "ACT 2.4",
            "bytes": len(head_act_bytes),
            "sha256": h_act_sha,
            "filename": f"{output_prefix}_head.act",
        }
        out_head_spr_info = {
            "format": "SPR 2.1",
            "bytes": len(head_spr_bytes),
            "sha256": h_spr_sha,
            "indexed_count": h_spr_doc.indexed_count,
            "rgba_count": h_spr_doc.rgba_count,
            "filename": f"{output_prefix}_head.spr",
        }

    # Verify baseline no-op roundtrip on original codecs
    baseline_act_encoded = write_act(orig_act)
    baseline_spr_encoded = write_spr(orig_spr)
    check(read_act(baseline_act_encoded) == orig_act, "ACT baseline semantic roundtrip mismatch.")

    if compilation_mode == "preserve":
        check(
            not replacement_requirement_ids,
            "PRESERVE_MODE_FORBIDS_REPLACEMENTS: preserve mode cannot accept replacement_requirement_ids.",
        )
        check(baseline_act_encoded == act_bytes, "ACT no-op byte preservation mismatch.")
        check(baseline_spr_encoded == spr_bytes, "SPR no-op byte preservation mismatch.")
        output_act_bytes = baseline_act_encoded
        output_spr_bytes = baseline_spr_encoded
        out_spr_doc = read_spr(output_spr_bytes)
        oracle_status = "NOT_RUN"
        oracle_sha = None
        if oracle_executable is not None:
            oracle_res = verify_pair_with_rust_oracle(output_act_bytes, output_spr_bytes, oracle_executable)
            oracle_status = "PASS"
            oracle_sha = oracle_res["rust_report_sha256"]

        total_frames = sum(len(a) for a in orig_act["actions"])
        total_visible = sum(
            1 for a in orig_act["actions"] for m in a for c in m["clips"] if c["sprite"] >= 0
        )
        total_hidden = sum(
            1 for a in orig_act["actions"] for m in a for c in m["clips"] if c["sprite"] == -1
        )
        total_anchors = sum(len(m["anchors"]) for a in orig_act["actions"] for m in a)

        manifest = sealed({
            "schema": COMPILATION_MANIFEST_SCHEMA,
            "id": compilation_id,
            "writer_version": WRITER_VERSION,
            "compilation_mode": "preserve",
            "replacement_policy": replacement_policy,
            "isolation_strategy": isolation_strategy,
            "part": part,
            "target": None,
            "runtime_profile": None,
            "requirements_sha256": None,
            "ledger": None,
            "input_resources": {
                "act": {"format": "ACT 2.4", "bytes": len(act_bytes), "sha256": input_act_sha},
                "spr": {
                    "format": "SPR 2.1",
                    "bytes": len(spr_bytes),
                    "sha256": input_spr_sha,
                    "indexed_count": orig_spr.indexed_count,
                    "rgba_count": orig_spr.rgba_count,
                },
                "head_act": head_act_info,
                "head_spr": head_spr_info,
            },
            "output_resources": {
                "act": {
                    "format": "ACT 2.4",
                    "bytes": len(output_act_bytes),
                    "sha256": digest(output_act_bytes),
                    "filename": f"{output_prefix}.act",
                },
                "spr": {
                    "format": "SPR 2.1",
                    "bytes": len(output_spr_bytes),
                    "sha256": digest(output_spr_bytes),
                    "indexed_count": out_spr_doc.indexed_count,
                    "rgba_count": out_spr_doc.rgba_count,
                    "filename": f"{output_prefix}.spr",
                },
                "head_act": out_head_act_info,
                "head_spr": out_head_spr_info,
            },
            "remapping": _remapping_evidence(orig_act, orig_spr, orig_act, orig_spr, []),
            "replacements": [],
            "preservation_summary": {
                "total_action_slots": len(orig_act["actions"]),
                "modified_action_slots": [],
                "untouched_action_slots": len(orig_act["actions"]),
                "total_frames": total_frames,
                "modified_frames": 0,
                "untouched_frames": total_frames,
                "total_visible_clips": total_visible,
                "modified_clips": 0,
                "unaffected_visible_clips": total_visible,
                "hidden_clips_preserved": total_hidden,
                "anchors_preserved": total_anchors,
                "events_preserved": len(orig_act["events"]),
                "delays_preserved": len(orig_act["delays"]),
                "head_resources_preserved_unchanged": True,
                "classic_retained_outside_completeness": True,
            },
            "verification": {
                "decode_after_write": "PASS",
                "metadata_preservation": "PASS",
                "targeted_pixel_verification": "PASS",
                "unaffected_reference_preservation": "PASS",
                "shared_reference_isolation": "PASS",
                "noop_byte_equal": True,
                "rust_oracle": oracle_status,
                "rust_oracle_report_sha256": oracle_sha,
                "native_korangar": "UNVERIFIED",
            },
            "status": {
                "result": "COMPILED",
                "production_authorized": False,
                "export_ready": False,
                "experimental_bounded_output": False,
                "visual_approval_authority": "OPERATOR_ONLY",
                "diagnostics": ["NOOP_PRESERVATION_VERIFIED"],
            },
        })
        manifest = _finish_build_manifest(manifest)
        validate_compilation_manifest(manifest)
        return {
            "manifest": manifest,
            "act_bytes": output_act_bytes,
            "spr_bytes": output_spr_bytes,
            "head_act_bytes": head_act_bytes,
            "head_spr_bytes": head_spr_bytes,
        }

    # Non-preserve compilation requires resolved requirements and canonical assignment ledger
    check(
        requirements is not None and ledger is not None,
        "MISSING_COMPILATION_CONTRACTS: requirements and ledger are required for replacement compilation.",
    )
    check_seal(requirements, "rsf.resolved-requirements/v1")
    if requirements.get("status", {}).get("work_order") != "EXACT" or requirements.get("diagnostics"):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            "UNDERSPECIFIED_LAYER_TOPOLOGY: cannot compile against provisional or underspecified requirements.",
        )

    if expected_target_revision is not None:
        actual_t_rev = requirements["target"]["revision"]
        check(
            actual_t_rev == expected_target_revision,
            f"STALE_TARGET_REVISION: expected target revision {expected_target_revision}, got {actual_t_rev}.",
        )

    resolved_report, ledger_ref = _resolve_ledger_and_reviews(
        requirements,
        ledger,
        source_bytes,
        reviewed_ledger=reviewed_ledger,
        review_events=review_events,
        project_id=project_id,
        expected_ledger_revision=expected_ledger_revision,
    )
    coverage = evaluate_coverage(requirements, ledger=resolved_report, source_bytes=source_bytes)
    export_ready = False

    req_layers = {l["id"]: l for l in requirements["layers"]}
    req_frames = {f["id"]: f for f in requirements["frames"]}
    assign_by_req = {a["requirement_id"]: a for a in resolved_report["assignments"]}

    if replacement_requirement_ids is not None:
        check(
            isinstance(replacement_requirement_ids, (list, tuple)) and len(replacement_requirement_ids) > 0,
            "EMPTY_REPLACEMENT_SCOPE: specify at least one replacement requirement ID.",
        )
        check(
            len(replacement_requirement_ids) == len(set(replacement_requirement_ids)),
            "DUPLICATE_REPLACEMENT_REQUIREMENT: replacement_requirement_ids must be unique.",
        )
        selected_req_ids = list(replacement_requirement_ids)
    else:
        selected_req_ids = [
            a["requirement_id"]
            for a in resolved_report["assignments"]
            if a["kind"] != "UNASSIGNED" and req_layers.get(a["requirement_id"], {}).get("part") == part
        ]
        check(len(selected_req_ids) > 0, "EMPTY_REPLACEMENT_SCOPE: ledger has no assigned replacements for part.")

    if compilation_mode == "production_export":
        check(_production_scope_ready(requirements, coverage, selected_req_ids, part),
              "PRODUCTION_EXPORT_NOT_READY: full-profile approved coverage and all required occurrences in one supported part are mandatory.")
        check(all((req_layers.get(rid, {}).get("authority") or {}).get("kind") == "inherited"
                  for rid in selected_req_ids),
              "UNBOUND_PRODUCTION_COMPOSITION: production requires inherited resource-bound topology; explicit role declarations do not bind original placement, timing or anchors for approval.")
        export_ready = True

    data_bytes = source_bytes or {}
    meta_by_sha = source_metadata or {}

    # Resolve and validate every targeted replacement occurrence
    targeted_items: list[dict[str, Any]] = []
    seen_locations: set[tuple[int, int, int]] = set()

    for rid in selected_req_ids:
        check(rid in req_layers, f"UNRESOLVED_REQUIREMENT_ID: requirement '{rid}' not found in resolved requirements.")
        layer = req_layers[rid]
        authority = layer.get("authority") or {}
        if authority.get("kind") == "inherited":
            check(authority["sources"]["act"]["sha256"] == input_act_sha and
                  authority["sources"]["spr"]["sha256"] == input_spr_sha,
                  "CHANGED_COMPOSITION_RESOURCE: inherited pre-build composition references different original ACT/SPR bytes.")
        check(
            layer["part"] == part,
            f"PART_MISMATCH: requirement '{rid}' targets part {layer['part']!r}, but compilation is for part {part!r}.",
        )
        slot = _compilation_slot(layer, compilation_mode)
        frame_idx = layer["frame"]
        layer_ord = layer["ordinal"]
        check(
            slot is not None and 0 <= slot < len(orig_act["actions"]),
            f"UNSUPPORTED_ACT_SLOT: requirement '{rid}' maps to slot {slot}, out of range [0, {len(orig_act['actions'])}).",
        )
        motions = orig_act["actions"][slot]
        check(
            0 <= frame_idx < len(motions),
            f"UNSUPPORTED_ACT_FRAME: requirement '{rid}' maps to frame {frame_idx}, out of range [0, {len(motions)}) in slot {slot}.",
        )
        motion = motions[frame_idx]
        visible_indices = [i for i, c in enumerate(motion["clips"]) if c["sprite"] >= 0]
        frame_req = req_frames[layer["frame_id"]]
        check(
            frame_req["resolution"] == "RESOLVED" and frame_req["layer_count"] is not None,
            f"UNDERSPECIFIED_LAYER_TOPOLOGY: frame '{layer['frame_id']}' is not resolved.",
        )
        check(
            len(visible_indices) == frame_req["layer_count"],
            f"UNSUPPORTED_LAYER_STRUCTURE: ACT slot {slot} frame {frame_idx} has {len(visible_indices)} visible clips, "
            f"but target topology declares {frame_req['layer_count']} layers.",
        )
        if layer.get("source_layer_ordinal") is not None:
            clip_ord = layer["source_layer_ordinal"]
            check(
                0 <= clip_ord < len(motion["clips"]) and clip_ord == visible_indices[layer_ord],
                f"LAYER_TOPOLOGY_MISMATCH: source_layer_ordinal {clip_ord} does not match visible layer ordinal {layer_ord}.",
            )
        else:
            check(
                0 <= layer_ord < len(visible_indices),
                f"LAYER_TOPOLOGY_MISMATCH: layer ordinal {layer_ord} out of range for {len(visible_indices)} visible clips.",
            )
            clip_ord = visible_indices[layer_ord]

        loc = (slot, frame_idx, clip_ord)
        check(
            loc not in seen_locations,
            f"CONFLICTING_REPLACEMENT_SCOPE: multiple replacement requirements map to ACT location {loc}.",
        )
        seen_locations.add(loc)

        row = assign_by_req.get(rid)
        check(
            row is not None and row["kind"] != "UNASSIGNED",
            f"UNASSIGNED_REPLACEMENT_REQUIREMENT: requirement '{rid}' has no active assignment.",
        )
        eff_src = row.get("effective_source")
        check(eff_src is not None, f"MISSING_REPLACEMENT_SOURCE: requirement '{rid}' has no effective source.")

        sid = eff_src["id"]
        declared_sha = eff_src.get("sha256")
        raw_src_bytes = data_bytes.get(sid)
        decoded_src = _decode_source_image(sid, declared_sha, raw_src_bytes)

        check(
            row["availability"] in ("AVAILABLE", "REUSED") and row["validation"] == "VALID",
            f"INVALID_REPLACEMENT_SOURCE: requirement '{rid}' source state is availability={row['availability']} validation={row['validation']}.",
        )
        if row["review_binding"] == "STALE":
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"STALE_REVIEW_APPROVAL: requirement '{rid}' has a stale visual review basis and must be re-approved.",
            )
        if row["visual_review"] == "REJECTED":
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"REJECTED_REPLACEMENT_ARTWORK: requirement '{rid}' was rejected by the operator.",
            )
        check(
            row["visual_review"] in ("APPROVED", "NOT_REQUIRED") and row["review_binding"] == "BOUND_OPERATOR_DECLARATION",
            f"UNAPPROVED_REPLACEMENT_ARTWORK: requirement '{rid}' visual_review={row['visual_review']} "
            f"binding={row['review_binding']}; bound operator approval is required before compilation.",
        )
        if row["kind"] == "EXPLICIT_REUSE":
            check(
                row["reuse_accepted"] is True,
                f"UNAPPROVED_REUSE_CHAIN: requirement '{rid}' reuse dependency chain is not accepted.",
            )

        # Execute only ledger-level mirror_x operations; never re-execute RSF-21 staged recipes
        final_w, final_h, final_rgba, executed_ops = _apply_ledger_transform_chain(
            decoded_src["width"],
            decoded_src["height"],
            decoded_src["rgba_bytes"],
            row.get("transform_chain", []),
            requirement_id=rid,
        )

        orig_clip = motion["clips"][clip_ord]
        orig_pool = orig_clip["pool"]
        orig_sprite = orig_clip["sprite"]
        orig_w, orig_h, orig_rgba = _resolve_spr_image_rgba(orig_spr, orig_pool, orig_sprite)

        if replacement_policy == "preserve_pool":
            target_pool = orig_pool
        elif replacement_policy == "indexed_exact":
            target_pool = 0
        else:
            target_pool = 1

        encoded_img, rep_notes = _encode_image_for_pool(
            final_w,
            final_h,
            final_rgba,
            target_pool,
            orig_spr.palette,
            requirement_id=rid,
            orig_pool=orig_pool,
        )

        src_meta = meta_by_sha.get(declared_sha, {}) if declared_sha else {}
        derived_info = {
            "recipe_id": src_meta.get("recipe_id"),
            "recipe_sha256": src_meta.get("recipe_sha256"),
            "source_sha256": src_meta.get("source_sha256"),
            "reapplied_in_compiler": False,
        }

        targeted_items.append({
            "loc": loc,
            "requirement_id": rid,
            "assignment_id": row["id"],
            "assignment_revision": row["revision"],
            "slot": slot,
            "action": layer["action"],
            "view": layer["view"],
            "frame": frame_idx,
            "layer_ordinal": layer_ord,
            "clip_ordinal": clip_ord,
            "source_id": sid,
            "source_sha256": declared_sha,
            "source_origin": eff_src["origin"],
            "derived_processing": derived_info,
            "executed_ledger_ops": executed_ops,
            "review_state": row["visual_review"],
            "composition_sha256": row["composition_sha256"],
            "orig_pool": orig_pool,
            "orig_sprite": orig_sprite,
            "orig_width": orig_w,
            "orig_height": orig_h,
            "orig_rgba_sha256": _decoded_rgba_digest(orig_w, orig_h, orig_rgba),
            "target_pool": target_pool,
            "width": final_w,
            "height": final_h,
            "expected_rgba": final_rgba,
            "expected_rgba_sha256": _decoded_rgba_digest(final_w, final_h, final_rgba),
            "encoded_img": encoded_img,
            "representational_notes": rep_notes,
        })

    # Canonical ordering by (slot, frame, clip_ordinal)
    targeted_items.sort(key=lambda item: item["loc"])
    targeted_by_loc = {item["loc"]: item for item in targeted_items}

    # Build global consumer map across all ACT slots, frames, and clips
    consumers_by_image: dict[tuple[int, int], set[tuple[int, int, int]]] = {}
    for s_idx, action in enumerate(orig_act["actions"]):
        for m_idx, motion in enumerate(action):
            for c_idx, clip in enumerate(motion["clips"]):
                if clip["sprite"] >= 0:
                    ref = (clip["pool"], clip["sprite"])
                    consumers_by_image.setdefault(ref, set()).add((s_idx, m_idx, c_idx))

    # Group targeted items by their original SPR (pool, index) reference
    targeted_by_orig_ref: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for item in targeted_items:
        orig_ref = (item["orig_pool"], item["orig_sprite"])
        targeted_by_orig_ref.setdefault(orig_ref, []).append(item)

    new_act = copy.deepcopy(orig_act)
    new_indexed = list(orig_spr.indexed_images)
    new_rgba = list(orig_spr.rgba_images)

    # Deduplication cache for replacement images written during this compilation:
    # (target_pool, width, height, raw_pixel_bytes) -> (out_pool, out_index)
    compiled_entry_cache: dict[tuple[int, int, int, bytes], tuple[int, int]] = {}
    replacement_records: list[dict[str, Any]] = []

    for item in targeted_items:
        loc = item["loc"]
        orig_ref = (item["orig_pool"], item["orig_sprite"])
        all_consumers = consumers_by_image.get(orig_ref, {loc})
        unaffected_consumers = all_consumers - set(targeted_by_loc.keys())
        raw_pixel_key = (
            item["encoded_img"].pixels if item["target_pool"] == 0 else item["encoded_img"].rgba
        )
        cache_key = (item["target_pool"], item["width"], item["height"], raw_pixel_key)

        same_orig_items = targeted_by_orig_ref[orig_ref]
        all_same_replacement_for_orig = len({
            (
                x["target_pool"],
                x["width"],
                x["height"],
                x["encoded_img"].pixels if x["target_pool"] == 0 else x["encoded_img"].rgba,
            )
            for x in same_orig_items
        }) == 1

        if isolation_strategy == "in_place_only":
            if len(unaffected_consumers) > 0:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"SHARED_IMAGE_MUTATION_FORBIDDEN: SPR image pool={orig_ref[0]} index={orig_ref[1]} is referenced by "
                    f"{len(unaffected_consumers)} unaffected ACT clip(s); in_place_only replacement would corrupt unrelated animations.",
                )
            if item["target_pool"] != orig_ref[0]:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"SHARED_IMAGE_MUTATION_FORBIDDEN: cannot change SPR pool ({orig_ref[0]} -> {item['target_pool']}) under in_place_only strategy.",
                )
            if not all_same_replacement_for_orig:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"SHARED_IMAGE_MUTATION_FORBIDDEN: multiple targeted clips sharing SPR image {orig_ref} specify conflicting replacement images under in_place_only strategy.",
                )

        if cache_key in compiled_entry_cache:
            out_pool, out_idx = compiled_entry_cache[cache_key]
            resolution_mode = "REUSED_COMPILATION_ENTRY"
        else:
            can_replace_in_place = (
                isolation_strategy in ("auto", "in_place_only")
                and len(unaffected_consumers) == 0
                and item["target_pool"] == orig_ref[0]
                and all_same_replacement_for_orig
            )
            if can_replace_in_place:
                out_pool, out_idx = orig_ref
                if out_pool == 0:
                    new_indexed[out_idx] = item["encoded_img"]
                else:
                    new_rgba[out_idx] = item["encoded_img"]
                resolution_mode = "IN_PLACE_UNSHARED"
                compiled_entry_cache[cache_key] = (out_pool, out_idx)
            else:
                out_pool = item["target_pool"]
                if out_pool == 0:
                    out_idx = len(new_indexed)
                    new_indexed.append(item["encoded_img"])
                else:
                    out_idx = len(new_rgba)
                    new_rgba.append(item["encoded_img"])
                resolution_mode = "COPY_ON_WRITE_APPEND"
                compiled_entry_cache[cache_key] = (out_pool, out_idx)

        # Update ONLY the targeted clip's pool and sprite index; preserve all other clip fields
        s_idx, m_idx, c_idx = loc
        target_clip = new_act["actions"][s_idx][m_idx]["clips"][c_idx]
        target_clip["pool"] = out_pool
        target_clip["sprite"] = out_idx

        item["out_pool"] = out_pool
        item["out_idx"] = out_idx
        item["resolution_mode"] = resolution_mode

        replacement_records.append({
            "requirement_id": item["requirement_id"],
            "assignment_id": item["assignment_id"],
            "assignment_revision": item["assignment_revision"],
            "slot": item["slot"],
            "action": item["action"],
            "view": item["view"],
            "frame": item["frame"],
            "layer_ordinal": item["layer_ordinal"],
            "clip_ordinal": item["clip_ordinal"],
            "source_id": item["source_id"],
            "source_sha256": item["source_sha256"],
            "source_origin": item["source_origin"],
            "derived_processing": item["derived_processing"],
            "executed_ledger_ops": item["executed_ledger_ops"],
            "review_state": item["review_state"],
            "composition_sha256": item["composition_sha256"],
            "original_image": {
                "pool": item["orig_pool"],
                "index": item["orig_sprite"],
                "width": item["orig_width"],
                "height": item["orig_height"],
                "decoded_rgba_sha256": item["orig_rgba_sha256"],
            },
            "output_image": {
                "pool": out_pool,
                "index": out_idx,
                "width": item["width"],
                "height": item["height"],
                "decoded_rgba_sha256": item["expected_rgba_sha256"],
            },
            "resolution_mode": resolution_mode,
            "shared_consumers_count": len(all_consumers),
            "unaffected_consumers_count": len(unaffected_consumers),
            "representational_notes": item["representational_notes"],
        })

    new_spr_doc = SprDocument(
        indexed_images=new_indexed,
        rgba_images=new_rgba,
        palette=orig_spr.palette,
    )

    output_act_bytes = write_act(new_act)
    output_spr_bytes = write_spr(new_spr_doc)

    # Mandatory Decode-After-Write and Pre/Post Semantic & Pixel Verification
    decoded_act = read_act(output_act_bytes)
    decoded_spr = read_spr(output_spr_bytes)
    _ = inventory(output_act_bytes, output_spr_bytes)

    check(decoded_act["reserved"] == orig_act["reserved"], "POST_VERIFY_FAILED: ACT reserved header bytes changed.")
    check(decoded_act["events"] == orig_act["events"], "POST_VERIFY_FAILED: ACT sound/event table changed.")
    check(len(decoded_act["delays"]) == len(orig_act["delays"]), "POST_VERIFY_FAILED: ACT delay count changed.")
    for d_orig, d_dec in zip(orig_act["delays"], decoded_act["delays"]):
        check(
            struct.pack("<f", d_orig) == struct.pack("<f", d_dec),
            "POST_VERIFY_FAILED: ACT action delay float32 bits changed.",
        )
    check(len(decoded_act["actions"]) == len(orig_act["actions"]), "POST_VERIFY_FAILED: ACT action slot count changed.")

    modified_slots: set[int] = set()
    modified_frames_count = 0
    total_frames_count = 0
    modified_clips_count = 0
    unaffected_visible_count = 0
    hidden_clips_count = 0
    anchors_count = 0

    for s_idx, (orig_motions, dec_motions) in enumerate(zip(orig_act["actions"], decoded_act["actions"])):
        check(len(orig_motions) == len(dec_motions), f"POST_VERIFY_FAILED: motion count changed in slot {s_idx}.")
        for m_idx, (orig_m, dec_m) in enumerate(zip(orig_motions, dec_motions)):
            total_frames_count += 1
            frame_modified = False
            check(dec_m["bounds"] == orig_m["bounds"], f"POST_VERIFY_FAILED: bounds changed at ({s_idx}, {m_idx}).")
            check(dec_m["event"] == orig_m["event"], f"POST_VERIFY_FAILED: event index changed at ({s_idx}, {m_idx}).")
            check(dec_m["anchors"] == orig_m["anchors"], f"POST_VERIFY_FAILED: anchors changed at ({s_idx}, {m_idx}).")
            anchors_count += len(dec_m["anchors"])
            check(len(dec_m["clips"]) == len(orig_m["clips"]), f"POST_VERIFY_FAILED: clip count changed at ({s_idx}, {m_idx}).")

            for c_idx, (orig_c, dec_c) in enumerate(zip(orig_m["clips"], dec_m["clips"])):
                loc = (s_idx, m_idx, c_idx)
                for field_name in ("x", "y", "mirror", "color", "angle"):
                    check(
                        dec_c[field_name] == orig_c[field_name],
                        f"POST_VERIFY_FAILED: clip {field_name} changed at {loc}.",
                    )
                for f_field in ("scale_x", "scale_y"):
                    check(
                        struct.pack("<f", dec_c[f_field]) == struct.pack("<f", orig_c[f_field]),
                        f"POST_VERIFY_FAILED: clip {f_field} changed at {loc}.",
                    )

                if loc in targeted_by_loc:
                    t_item = targeted_by_loc[loc]
                    frame_modified = True
                    modified_slots.add(s_idx)
                    modified_clips_count += 1
                    check(
                        (dec_c["pool"], dec_c["sprite"]) == (t_item["out_pool"], t_item["out_idx"]),
                        f"POST_VERIFY_FAILED: targeted clip {loc} sprite reference mismatch.",
                    )
                    dec_w, dec_h, dec_rgba = _resolve_spr_image_rgba(decoded_spr, dec_c["pool"], dec_c["sprite"])
                    check(
                        (dec_w, dec_h) == (t_item["width"], t_item["height"]) and dec_rgba == t_item["expected_rgba"],
                        f"POST_VERIFY_FAILED: targeted clip {loc} decoded pixels do not match expected replacement artwork.",
                    )
                else:
                    if orig_c["sprite"] == -1:
                        hidden_clips_count += 1
                        check(dec_c == orig_c, f"POST_VERIFY_FAILED: hidden clip changed at {loc}.")
                    else:
                        unaffected_visible_count += 1
                        check(
                            (dec_c["pool"], dec_c["sprite"]) == (orig_c["pool"], orig_c["sprite"]),
                            f"POST_VERIFY_FAILED: unaffected clip {loc} (pool, sprite) reference changed.",
                        )
                        orig_w, orig_h, orig_rgba = _resolve_spr_image_rgba(orig_spr, orig_c["pool"], orig_c["sprite"])
                        dec_w, dec_h, dec_rgba = _resolve_spr_image_rgba(decoded_spr, dec_c["pool"], dec_c["sprite"])
                        check(
                            (dec_w, dec_h) == (orig_w, orig_h) and dec_rgba == orig_rgba,
                            f"POST_VERIFY_FAILED: unaffected clip {loc} effective SPR image pixels changed!",
                        )
                        if orig_c["pool"] == 0:
                            check(
                                decoded_spr.indexed_images[dec_c["sprite"]].pixels
                                == orig_spr.indexed_images[orig_c["sprite"]].pixels,
                                f"POST_VERIFY_FAILED: unaffected indexed image {orig_c['sprite']} palette indices changed!",
                            )
            if frame_modified:
                modified_frames_count += 1

    oracle_status = "NOT_RUN"
    oracle_sha = None
    if oracle_executable is not None:
        oracle_res = verify_pair_with_rust_oracle(output_act_bytes, output_spr_bytes, oracle_executable)
        oracle_status = "PASS"
        oracle_sha = oracle_res["rust_report_sha256"]

    untouched_slots_count = len(orig_act["actions"]) - len(modified_slots)
    production_authorized = bool(compilation_mode == "production_export" and export_ready)
    diagnostics: list[str] = []
    if compilation_mode == "bounded_replacement":
        diagnostics.append(
            f"BOUNDED_REPLACEMENT_ONLY: {len(replacement_records)} layer occurrence(s) replaced across "
            f"{len(modified_slots)} slot(s); {untouched_slots_count} numeric slot(s) retain classic reference art outside completeness."
        )
    for action_id in sorted({l["action"] for l in requirements["layers"] if l.get("offline") and l["id"] in selected_req_ids}):
        diagnostics.append(f"RUNTIME_ACTION_MAPPING_UNAVAILABLE: {action_id}; existing ACT storage is diagnostic only, not runtime invocation support.")
    if not export_ready:
        diagnostics.append("INCOMPLETE_ACTOR_SCOPE: export_ready remains False; not authorized as a full-profile production export.")

    manifest = sealed({
        "schema": COMPILATION_MANIFEST_SCHEMA,
        "id": compilation_id,
        "writer_version": WRITER_VERSION,
        "compilation_mode": compilation_mode,
        "replacement_policy": replacement_policy,
        "isolation_strategy": isolation_strategy,
        "part": part,
        "target": requirements["target"],
        "runtime_profile": requirements["runtime_profile"],
        "requirements_sha256": requirements["canonical_sha256"],
        "ledger": ledger_ref,
        "input_resources": {
            "act": {"format": "ACT 2.4", "bytes": len(act_bytes), "sha256": input_act_sha},
            "spr": {
                "format": "SPR 2.1",
                "bytes": len(spr_bytes),
                "sha256": input_spr_sha,
                "indexed_count": orig_spr.indexed_count,
                "rgba_count": orig_spr.rgba_count,
            },
            "head_act": head_act_info,
            "head_spr": head_spr_info,
        },
        "output_resources": {
            "act": {
                "format": "ACT 2.4",
                "bytes": len(output_act_bytes),
                "sha256": digest(output_act_bytes),
                "filename": f"{output_prefix}.act",
            },
            "spr": {
                "format": "SPR 2.1",
                "bytes": len(output_spr_bytes),
                "sha256": digest(output_spr_bytes),
                "indexed_count": decoded_spr.indexed_count,
                "rgba_count": decoded_spr.rgba_count,
                "filename": f"{output_prefix}.spr",
            },
            "head_act": out_head_act_info,
            "head_spr": out_head_spr_info,
        },
        "remapping": _remapping_evidence(orig_act, orig_spr, decoded_act, decoded_spr, replacement_records),
        "replacements": replacement_records,
        "preservation_summary": {
            "total_action_slots": len(orig_act["actions"]),
            "modified_action_slots": sorted(modified_slots),
            "untouched_action_slots": untouched_slots_count,
            "total_frames": total_frames_count,
            "modified_frames": modified_frames_count,
            "untouched_frames": total_frames_count - modified_frames_count,
            "total_visible_clips": modified_clips_count + unaffected_visible_count,
            "modified_clips": modified_clips_count,
            "unaffected_visible_clips": unaffected_visible_count,
            "hidden_clips_preserved": hidden_clips_count,
            "anchors_preserved": anchors_count,
            "events_preserved": len(orig_act["events"]),
            "delays_preserved": len(orig_act["delays"]),
            "head_resources_preserved_unchanged": True,
            "classic_retained_outside_completeness": untouched_slots_count > 0 or not export_ready,
        },
        "verification": {
            "decode_after_write": "PASS",
            "metadata_preservation": "PASS",
            "targeted_pixel_verification": "PASS",
            "unaffected_reference_preservation": "PASS",
            "shared_reference_isolation": "PASS",
            "noop_byte_equal": output_act_bytes == act_bytes and output_spr_bytes == spr_bytes,
            "rust_oracle": oracle_status,
            "rust_oracle_report_sha256": oracle_sha,
            "native_korangar": "UNVERIFIED",
        },
        "status": {
            "result": "COMPILED",
            "production_authorized": production_authorized,
            "export_ready": export_ready,
            "experimental_bounded_output": not production_authorized,
            "visual_approval_authority": "OPERATOR_ONLY",
            "diagnostics": diagnostics,
        },
    })

    manifest = _finish_build_manifest(manifest, requirements, resolved_report, selected_req_ids, coverage)
    validate_compilation_manifest(manifest)

    return {
        "manifest": manifest,
        "act_bytes": output_act_bytes,
        "spr_bytes": output_spr_bytes,
        "head_act_bytes": head_act_bytes,
        "head_spr_bytes": head_spr_bytes,
    }


def publish_compilation(
    output_dir: str | Path,
    compilation_result: dict[str, Any],
    *,
    cache_dir: str | Path | None = None,
) -> dict[str, str]:
    """Safely publish compiled ACT/SPR pair and compilation manifest without overwriting existing files."""
    target_dir = Path(output_dir)
    manifest = compilation_result["manifest"]
    validate_compilation_manifest(manifest)
    for name in ("act", "spr", "head_act", "head_spr"):
        raw = compilation_result.get(name + "_bytes")
        info = manifest["output_resources"].get(name)
        check((raw is None) == (info is None), f"COMPILATION_PAIR_MISMATCH: {name} presence differs from manifest.")
        if info is not None:
            check(isinstance(raw, bytes) and len(raw) == info["bytes"] and digest(raw) == info["sha256"],
                  f"COMPILATION_PAIR_MISMATCH: {name} bytes differ from manifest.")
    check((compilation_result.get("head_act_bytes") is None) == (compilation_result.get("head_spr_bytes") is None), "COMPILATION_PAIR_MISMATCH: incomplete head pair.")
    inventory(compilation_result["act_bytes"], compilation_result["spr_bytes"])
    if compilation_result.get("head_act_bytes") is not None:
        inventory(compilation_result["head_act_bytes"], compilation_result["head_spr_bytes"])
    out_res = manifest["output_resources"]
    contents = {"compilation-manifest.json": canonical_bytes(manifest)}
    resources = {}
    for name in ("act", "spr", "head_act", "head_spr"):
        if out_res.get(name) is None:
            continue
        filename = out_res[name]["filename"]
        check(Path(filename).name == filename and filename not in (".", "..", "compilation-manifest.json", "build-manifest.json", "PARTIAL_DIAGNOSTIC.txt") and filename not in contents,
              "INVALID_OUTPUT_FILENAME: resource filenames must be unique safe basenames.")
        contents[filename] = compilation_result[name + "_bytes"]
        resources[name + (".act" if name.endswith("act") else ".spr")] = compilation_result[name + "_bytes"]
    if "build" in manifest:
        contents["build-manifest.json"] = canonical_bytes(manifest["build"])
    if manifest["status"].get("export_label") == "PARTIAL_DIAGNOSTIC":
        contents["PARTIAL_DIAGNOSTIC.txt"] = (
            "PARTIAL_DIAGNOSTIC\nNot authorized as a full-profile production export.\n"
            "Native Korangar: UNVERIFIED. Visual approval authority: OPERATOR_ONLY.\n"
            f"Build: {manifest['build']['input_sha256']}\n").encode("ascii")
    if cache_dir is not None:
        check("build" in manifest, "LEGACY_MANIFEST_HAS_NO_CACHE_IDENTITY")
        cache_bundle(cache_dir, manifest["build"], resources)
    publish_bundle(target_dir, contents)
    return {"act_path": str(target_dir / out_res["act"]["filename"]),
            "spr_path": str(target_dir / out_res["spr"]["filename"]),
            "manifest_path": str(target_dir / "compilation-manifest.json")}
