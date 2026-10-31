"""Independently check native observations against original bytes and frozen rules.

The native executable never consumes Python-decoded structures. This checker reads
the original resources after execution and fails at the first precise mismatch.
It does not approve artwork, gameplay reachability or unexecuted platforms.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr


class NativeMismatch(ValueError):
    pass


def equal(actual, expected, location):
    if actual != expected:
        raise NativeMismatch(f"{location}: expected {expected!r}, observed {actual!r}")


def close(actual, expected, location):
    if not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=2e-6, rel_tol=2e-6):
        raise NativeMismatch(f"{location}: expected {expected!r}, observed {actual!r}")


def close_vector(actual, expected, location):
    equal(len(actual), len(expected), location + "/length")
    for index, (a, b) in enumerate(zip(actual, expected)):
        close(a, b, location + f"/{index}")


def check_selection(case, kind, delays, frame_counts):
    groups = {"novice": {"Idle": 0, "Walk": 1, "Attack": 5, "Hurt": 6, "Die": 8},
              "orc": {"Idle": 0, "Walk": 1, "Attack": 2, "Hurt": 3, "Die": 4}}
    action = case["requested_action"]
    direction, camera = case["requested_direction"], case["camera_view"]
    if direction not in range(8) or camera not in (0, 4):
        raise NativeMismatch("ACTION_UNSUPPORTED: invalid requested camera/direction")
    view = (direction + camera) & 7
    slot = groups[kind][action] * 8 + view
    location = f"{kind}/{action}/camera{camera}/direction{direction}"
    for field in ("requested_slot", "resolved_slot"):
        equal(case[field], slot, location + "/" + field)
    equal(case["resolved_view"], view, location + "/view")
    equal(case["fallback"], "NONE", location + "/fallback")
    equal(case["status"], "REQUESTED_SLOT_VERIFIED", location + "/status")
    delay = delays[slot]
    close(case["source_delay"], delay, location + "/delay")
    factor = 20.0 if action == "Walk" else 50.0
    equal(case["native_delay_factor"], factor, location + "/factor")
    count = frame_counts[slot]
    equal(case["frames_in_slot"], count, location + "/frame_count")
    equal(case["duration"], 1000 if action in ("Attack", "Hurt") else None, location + "/duration")
    equal(len(case["sequence"]), count + 2, location + "/sequence_length")
    for index, sample in enumerate(case["sequence"]):
        equal(sample["resolved_slot"], slot, location + f"/sample{index}/resolved_slot")
        equal(sample["resolved_view"], view, location + f"/sample{index}/resolved_view")
        tick = sample["tick"]
        # Samples deliberately lie inside a frame interval, away from float
        # boundaries. Native arithmetic is u32 for duration, f32 otherwise.
        frame_time = tick * count // 1000 if action in ("Attack", "Hurt") else int(tick / (delay * factor))
        expected = 0 if kind == "novice" and action == "Idle" else (
            frame_time % count if action in ("Idle", "Walk") else min(frame_time, count - 1))
        equal(sample["frame"], expected, location + f"/sample{index}/frame")


def verify(inputs, report):
    equal(report["schema"], "rsf.native.v1", "schema")
    equal(report["revision"], "3f3d88a583203f09d079712f43343c1041258ffd", "revision")
    equal(report["mode"], "isolated_native_presentation", "mode")
    documents = {}
    source_hashes = {}
    for name in ("novice_body", "novice_head", "orc_skeleton"):
        raw = {}
        for extension in ("act", "spr"):
            identifier = f"data\\sprite\\{name}.{extension}"
            spec = inputs["files"][identifier]
            raw[extension] = Path(spec["path"]).read_bytes()
            digest = hashlib.sha256(raw[extension]).hexdigest()
            equal(digest, spec["sha256"], identifier + "/source_immutable")
            source_hashes[identifier] = digest
        documents[name] = read_act(raw["act"]), read_spr(raw["spr"])
    prepared = {r["actor"]: r["actions"] for r in report["prepared"]}
    resources = {r["actor"]: r for r in report["resources"]}
    equal(len(report["prepared"]), 2, "prepared/record_count")
    equal(len(report["resources"]), 2, "resources/record_count")
    equal(set(prepared), {"novice", "orc"}, "prepared/actors")
    equal(set(resources), {"novice", "orc"}, "resources/actors")
    total_parts = 0
    for kind, names in (("novice", ("novice_body", "novice_head")), ("orc", ("orc_skeleton",))):
        equal(resources[kind]["parts"], list(names), kind + "/resource_order")
        loaded = resources[kind]["loaded"]
        equal(len(loaded), 2 * len(names), kind + "/load_count")
        equal({r["path"] for r in loaded}, {f"data\\sprite\\{n}.{e}" for n in names for e in ("act", "spr")}, kind + "/loaded_identifiers")
        for item in loaded:
            equal(item["status"], "LOADED_CORRECT_RESOURCE", item["path"])
            equal(item["sha256"], source_hashes[item["path"]], item["path"] + "/delivered_hash")
        acts = [documents[n][0] for n in names]
        sprites = [documents[n][1] for n in names]
        equal(resources[kind]["stored_images"], [len(s.images) for s in sprites], kind + "/stored_images")
        equal(len(prepared[kind]), len(acts[0]["actions"]), kind + "/slots")
        for slot, frames in enumerate(prepared[kind]):
            equal(len(frames), len(acts[0]["actions"][slot]), f"{kind}/{slot}/motions")
            # Pinned loader skips zero-clip motions before multipart merging.
            motions = [[m for m in a["actions"][slot] if m["clips"]] for a in acts]
            for frame_index, frame in enumerate(frames):
                expected = []
                for part, action_motions in enumerate(motions):
                    if frame_index >= len(action_motions):
                        continue
                    motion = action_motions[frame_index]
                    for layer in motion["clips"]:
                        if layer["sprite"] == -1:
                            continue
                        sprite = layer["sprite"] + (sprites[part].indexed_count if layer["pool"] == 1 else 0)
                        image = sprites[part].images[sprite]
                        x, y = layer["x"], layer["y"]
                        if kind == "novice" and part == 1 and len(motion["anchors"]) == 1:
                            # Parent uses original raw motion index, not compressed
                            # frame index. These audited pairs contain no skipped
                            # parent motions; assert this rather than guessing.
                            equal(len(motions[0]), len(acts[0]["actions"][slot]), f"{kind}/{slot}/parent_motion_mapping")
                            parent = acts[0]["actions"][slot][frame_index]["anchors"][0]
                            anchor = motion["anchors"][0]
                            x += parent["x"] - anchor["x"]
                            y += parent["y"] - anchor["y"]
                        expected.append(dict(part=part, image=sprite, offset=[x, y],
                                             size=[math.ceil(image.width * layer["scale_x"]), math.ceil(image.height * layer["scale_y"])],
                                             mirror=layer["mirror"] != 0, angle=layer["angle"] / 180 * math.pi,
                                             color=[((layer["color"] >> shift) & 255) / 255 for shift in (0, 8, 16, 24)]))
                location = f"{kind}/slot{slot}/frame{frame_index}"
                equal(len(frame["parts"]), len(expected), location + "/layers")
                for layer_index, (observed, required) in enumerate(zip(frame["parts"], expected)):
                    for field in ("part", "image", "offset", "size", "mirror"):
                        equal(observed[field], required[field], location + f"/layer{layer_index}/{field}")
                    close(observed["angle"], required["angle"], location + f"/layer{layer_index}/angle")
                    close_vector(observed["color"], required["color"], location + f"/layer{layer_index}/color")
                total_parts += len(expected)
    expected_cases = {(kind, action, camera, direction) for kind in ("novice", "orc") for action in ("Idle", "Walk", "Attack", "Hurt", "Die") for camera in (0, 4) for direction in range(8)}
    equal(len(report["cases"]), len(expected_cases), "case_count")
    equal({(c["actor"], c["requested_action"], c["camera_view"], c["requested_direction"]) for c in report["cases"]}, expected_cases, "case_coverage")
    captures = 0
    selections = 0
    for case in report["cases"]:
        kind = case["actor"]
        act = documents["novice_body" if kind == "novice" else "orc_skeleton"][0]
        check_selection(case, kind, act["delays"], [len(a) for a in prepared[kind]])
        for sample in case["sequence"]:
            selections += 1
            layers = prepared[kind][case["resolved_slot"]][sample["frame"]]["parts"]
            equal(sample["layers"], len(layers), f"{kind}/{case['resolved_slot']}/{sample['frame']}/draw_layers")
            if sample["capture"] is not None:
                captures += 1
                capture = sample["capture"]
                equal(capture["drawn_layers"], len(layers), "capture/drawn_layers")
                equal(capture["passes"], ["opaque", "transparent", "wboit_resolve"], "capture/passes")
                if capture["non_background_pixels"] <= 0:
                    raise NativeMismatch("NATIVE_FAILURE: empty native capture")
    if captures < 50:
        raise NativeMismatch("NATIVE_UNVERIFIED: representative captures absent")
    negative = {n["case"]: n for n in report["negative_cases"]}
    equal(set(negative), {"monster_critical_attack", "truncated_action_set_modulo", "incorrect_view_expectation", "native_loader_missing_and_hash_mismatch", "unsupported_direction_8"}, "negative_coverage")
    equal(len(report["negative_cases"]), 5, "negative_count")
    for name in ("monster_critical_attack", "truncated_action_set_modulo", "native_loader_missing_and_hash_mismatch"):
        equal(negative[name]["status"], "FALLBACK_DETECTED", name)
    equal(negative["monster_critical_attack"]["resolved_slot"], 0, "critical_fallback")
    equal(negative["truncated_action_set_modulo"]["resolved_slot"], 7, "modulo_fallback")
    equal(negative["incorrect_view_expectation"]["status"], "NATIVE_FAILURE", "wrong_view")
    equal(negative["unsupported_direction_8"]["status"], "ACTION_UNSUPPORTED", "invalid_direction")
    equal(negative["unsupported_direction_8"]["accepted_as_success"], False, "invalid_direction_acceptance")
    equal({t["status"] for t in negative["native_loader_missing_and_hash_mismatch"]["trace"]}, {"MISSING", "RESOURCE_MISMATCH", "LOADED_CORRECT_RESOURCE"}, "negative_loader_trace")
    return dict(schema="rsf.native-verification.v1", result="NATIVE_CHECKS_PASSED", cases=len(expected_cases), selected_frames=selections,
                compared_prepared_layers=total_parts, capture_observations=captures, source_hashes=source_hashes,
                scope="isolated native presentation; gameplay reachability and audio not tested", visual_review="NOT_REQUIRED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = verify(json.loads(args.inputs.read_text()), json.loads(args.report.read_text()))
    result["native_report_sha256"] = hashlib.sha256(args.report.read_bytes()).hexdigest()
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
