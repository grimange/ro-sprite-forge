"""Finite M0 work orders. No assignment ledger or production approval is inferred."""

from ro_sprite_forge.core.canonical import canonical_bytes, check, check_seal, digest, sealed
from ro_sprite_forge.core.inventory import SCHEMA as INVENTORY_SCHEMA, namespace
from ro_sprite_forge.core.profiles import validate_profile

SCHEMA = "rsf.requirements/v1"
TARGET_SCHEMA = "rsf.target/v1"


def fields(value: object, allowed: set[str], required: set[str]) -> dict:
    check(isinstance(value, dict), "Expected a JSON object.")
    check(required <= value.keys() and value.keys() <= allowed, "Missing or unknown contract fields.")
    return value


def integer(value: object, maximum: int) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _roles(value: object) -> list[str]:
    check(isinstance(value, list) and len(value) <= 1024, "Expected at most 1024 ordered layer roles.")
    roles = [namespace(role) for role in value]
    check(len(set(roles)) == len(roles), "Layer roles must be unique within a frame.")
    return roles


def requirements(observed: dict, profile: dict, target: dict) -> dict:
    """Validate an explicit finite target and report exact versus provisional work.

    Inventory supplies observations or explicitly requested topology inheritance;
    it never silently supplies frame counts, assignments, or visual approval.
    """
    check_seal(observed, INVENTORY_SCHEMA)
    profile = validate_profile(profile)
    check(observed.get("runtime_profile") == profile, "Inventory/profile identity mismatch; inspect with the requested profile first.")
    fields(target, {"schema", "actor", "part", "scope", "actions"}, {"schema", "actor", "part", "scope", "actions"})
    check(target["schema"] == TARGET_SCHEMA, "Unsupported target schema.")
    actor, part = namespace(target["actor"]), namespace(target["part"])
    check(target["scope"] in ("scoped", "full"), "Target scope must be scoped or full.")
    check(isinstance(target["actions"], list) and 0 < len(target["actions"]) <= 128, "Expected 1–128 declared actions.")
    check(isinstance(observed.get("actions"), list) and len(observed["actions"]) <= 4096, "Invalid inventory actions.")
    slots = {}
    for action in observed["actions"]:
        check(isinstance(action, dict) and integer(action.get("slot"), 4095) and isinstance(action.get("frames"), list), "Invalid inventory action record.")
        check(action["slot"] not in slots, "Duplicate inventory slot.")
        slots[action["slot"]] = action
    mapping = {a["action"]: a for a in profile["actions"]}
    diagnostics, work, canonical_actions = [], [], []
    seen, declared_pairs = set(), set()
    totals = {"required_frames": 0, "required_layers_known": 0, "optional_frames": 0, "optional_layers_known": 0}
    prefix = f"{actor}/{profile['id']}/{part}"
    for declaration in sorted(target["actions"], key=lambda x: canonical_bytes(x)):
        fields(declaration, {"action", "requirement", "views"}, {"action", "requirement", "views"})
        name, kind = namespace(declaration["action"]), declaration["requirement"]
        check(name not in seen, "Duplicate declared action.")
        seen.add(name)
        check(kind in ("required", "optional", "out_of_scope"), "Unknown action requirement.")
        views = declaration["views"]
        check(isinstance(views, list) and len(views) <= 8, "Expected at most eight views per action.")
        check(all(isinstance(v, dict) and integer(v.get("view"), 7) for v in views), "Views must be numeric 0–7.")
        check(len({v["view"] for v in views}) == len(views), "Duplicate action/view declaration.")
        canonical_views = []
        if kind != "out_of_scope" and not views:
            diagnostics.append({"code": "UNDERSPECIFIED_FRAME_COUNT", "action": name, "view": None})
            diagnostics.append({"code": "UNDERSPECIFIED_LAYER_TOPOLOGY", "action": name, "view": None})
        for view in sorted(views, key=lambda v: v["view"]):
            fields(view, {"view", "frame_count", "topology"}, {"view"})
            canonical_views.append(view)
            if kind == "out_of_scope":
                check(set(view) == {"view"}, "Out-of-scope views cannot declare work.")
                continue
            number = view["view"]
            declared_pairs.add((name, number))
            mapping_record = mapping.get(name)
            slot = mapping_record["group"] * 8 + number if mapping_record else None
            source = slots.get(slot)
            count = view.get("frame_count")
            check(count is None or integer(count, 4096), "Frame count must be an integer 0–4096.")
            if count is None:
                diagnostics.append({"code": "UNDERSPECIFIED_FRAME_COUNT", "action": name, "view": number})
            topology = view.get("topology")
            layers_by_frame = None
            if topology is None:
                diagnostics.append({"code": "UNDERSPECIFIED_LAYER_TOPOLOGY", "action": name, "view": number})
            else:
                check(isinstance(topology, dict), "Topology must be an explicit or inherited object.")
                if topology.get("kind") == "explicit":
                    fields(topology, {"kind", "layers", "frames"}, {"kind"})
                    check(("layers" in topology) != ("frames" in topology), "Declare uniform layers OR per-frame topology.")
                    if "layers" in topology:
                        roles = _roles(topology["layers"])
                        if count is not None:
                            check(len(roles) * count <= 262144, "Layer work budget exceeded.")
                            layers_by_frame = [roles] * count
                    else:
                        check(isinstance(topology["frames"], list) and len(topology["frames"]) <= 4096, "Invalid per-frame topology.")
                        layers_by_frame = [_roles(roles) for roles in topology["frames"]]
                        check(count is None or len(layers_by_frame) == count, "Topology length does not match frame count.")
                        if count is None:
                            layers_by_frame = None
                elif topology.get("kind") == "inherited":
                    fields(topology, {"kind", "inventory_sha256", "slot"}, {"kind", "inventory_sha256", "slot"})
                    check(topology["inventory_sha256"] == observed["canonical_sha256"], "Inheritance inventory hash mismatch.")
                    check(type(topology["slot"]) is int and slot is not None and topology["slot"] == slot and source is not None,
                          "Inheritance must reference the mapped action/view slot.")
                    check(len(source["frames"]) <= 4096, "Inherited frame budget exceeded.")
                    check(count is None or len(source["frames"]) == count, "Inherited topology frame count mismatch.")
                    layers_by_frame = []
                    for frame in source["frames"]:
                        check(isinstance(frame, dict) and isinstance(frame.get("layers"), list) and len(frame["layers"]) <= 1024,
                              "Invalid inherited inventory layers.")
                        check(all(isinstance(layer, dict) and type(layer.get("visible")) is bool for layer in frame["layers"]), "Invalid inherited layer record.")
                        layers_by_frame.append([f"layer{i}" for i, layer in enumerate(frame["layers"]) if layer["visible"]])
                    if count is None:
                        layers_by_frame = None
                else:
                    check(False, "Unknown topology kind.")
            bucket = "required" if kind == "required" else "optional"
            totals[f"{bucket}_frames"] += count or 0
            totals[f"{bucket}_layers_known"] += sum(map(len, layers_by_frame)) if layers_by_frame is not None else 0
            check(totals["required_frames"] + totals["optional_frames"] <= 65536, "Frame work budget exceeded.")
            check(totals["required_layers_known"] + totals["optional_layers_known"] <= 262144, "Layer work budget exceeded.")
            action_id = f"{prefix}/action/{name}/slot{slot if slot is not None else 'UNVERIFIED'}/view{number}"
            frames = []
            if count is not None and layers_by_frame is not None:
                for ordinal, roles in enumerate(layers_by_frame):
                    frame_id = f"{action_id}/frame{ordinal}"
                    frames.append({"id": frame_id, "ordinal": ordinal,
                                   "layers": [{"id": f"{frame_id}/layer{i}", "ordinal": i, "role": role} for i, role in enumerate(roles)]})
            work.append({"id": action_id, "action": name, "view": number, "slot": slot,
                         "requirement": kind, "frame_count": count, "topology": topology,
                         "frames": frames, "observed_resource": "PRESENT" if source else "ABSENT",
                         "runtime_mapping": "SOURCE_VERIFIED" if mapping_record else "UNVERIFIED",
                         "runtime_selection": mapping_record["selection_path"] if mapping_record else "UNVERIFIED"})
        canonical_actions.append({"action": name, "requirement": kind, "views": canonical_views})
    normalized_target = {**target, "actions": sorted(canonical_actions, key=lambda a: a["action"])}
    check(any(a["requirement"] != "out_of_scope" for a in canonical_actions), "Declare at least one in-scope action.")
    exact = bool(work) and not diagnostics
    full = exact and target["scope"] == "full" and bool(mapping) and declared_pairs == {(a, v) for a in mapping for v in range(8)}
    return sealed({"schema": SCHEMA, "inventory_sha256": observed["canonical_sha256"],
                   "runtime_profile_sha256": profile["canonical_sha256"],
                   "target_sha256": digest(canonical_bytes(normalized_target)), "target": normalized_target,
                   "work": sorted(work, key=lambda w: (w["action"], w["view"])), "totals": totals,
                   "diagnostics": sorted(diagnostics, key=canonical_bytes),
                   "status": {"work_order": "EXACT" if exact else "UNDERSPECIFIED",
                              "declared_scope_specified": exact, "full_profile_specified": full,
                              "observed_resources_are_assignments": False,
                              "artwork_coverage": "UNASSIGNED", "production_readiness": "NOT_READY",
                              "visual_approval": "UNREVIEWED", "native_evidence": "UNVERIFIED"}})
