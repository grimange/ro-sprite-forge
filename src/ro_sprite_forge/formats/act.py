"""ACT 2.4 parser and serializer with byte-exact round-trip preservation."""

import math
import struct
from typing import Any

from ro_sprite_forge.formats.errors import require
from ro_sprite_forge.formats.reader import BinaryReader

ACT_MAGIC = b"AC"
ACT_SUPPORTED_VERSION = b"\x04\x02"  # Version 2.4 (minor 4, major 2)

MAX_ACTIONS = 4096
MAX_MOTIONS_PER_ACTION = 4096
MAX_TOTAL_MOTIONS = 65536
MAX_CLIPS_PER_MOTION = 1024
MAX_TOTAL_CLIPS = 262144
MAX_ANCHORS_PER_MOTION = 64
MAX_EVENTS = 4096
EVENT_RECORD_SIZE = 40

CLIP_FIELDS = ["x", "y", "sprite", "mirror", "color", "scale_x", "scale_y", "angle", "pool"]
ANCHOR_FIELDS = ["opaque", "x", "y", "attribute"]


def read_act(data: bytes, *, path: str | None = None) -> dict[str, Any]:
    """Parse ACT 2.4 binary payload into structured dictionary.

    Preserves numeric actions, motion frames, ordered clip layers, bounds,
    anchor points, sound/event records, delays, and raw reserved bytes.
    """
    require(len(data) >= 16, "truncated binary resource: ACT file too small for header", path=path)
    magic = data[:2]
    require(magic == ACT_MAGIC, f"not an ACT file: invalid magic header {magic!r}", path=path)
    version = data[2:4]
    require(
        version == ACT_SUPPORTED_VERSION,
        f"only ACT 2.4 is supported; found version {version[1]}.{version[0]}",
        path=path,
    )

    r = BinaryReader(data, path=path)
    _ = r.take(4)  # magic and version verified above
    count = r.read("H")
    require(0 < count <= MAX_ACTIONS, "invalid action count", path=path)
    reserved = r.take(10)

    total_motions = 0
    total_clips = 0
    actions = []

    for _ in range(count):
        n = r.read("I")
        require(n <= MAX_MOTIONS_PER_ACTION, "invalid motion count", path=path)
        total_motions += n
        require(total_motions <= MAX_TOTAL_MOTIONS, "cumulative motion budget exceeded", path=path)
        motions = []
        for _ in range(n):
            bounds = r.read("8i")
            nc = r.read("I")
            require(nc <= MAX_CLIPS_PER_MOTION, "invalid layer count", path=path)
            total_clips += nc
            require(total_clips <= MAX_TOTAL_CLIPS, "cumulative clip budget exceeded", path=path)
            clips = [dict(zip(CLIP_FIELDS, r.read("iiiIIffiI"))) for _ in range(nc)]
            event = r.read("i")
            na = r.read("I")
            require(na <= MAX_ANCHORS_PER_MOTION, "invalid anchor count", path=path)
            anchors = [dict(zip(ANCHOR_FIELDS, r.read("IiiI"))) for _ in range(na)]
            motions.append(dict(bounds=bounds, clips=clips, event=event, anchors=anchors))
        actions.append(motions)

    ne = r.read("I")
    require(ne <= MAX_EVENTS, "invalid event count", path=path)
    events = [r.take(EVENT_RECORD_SIZE).hex() for _ in range(ne)]
    delays = [r.read("f") for _ in range(count)]
    require(r.pos == len(data), "trailing ACT data", path=path)

    return dict(reserved=reserved.hex(), actions=actions, events=events, delays=delays)


def _validate_act(act: dict[str, Any], *, path: str | None = None) -> None:
    """Reject malformed/unsupported edits before allocating serialized output."""
    def keys(record, expected):
        require(isinstance(record, dict) and set(record) == set(expected),
                "unsupported or missing ACT fields", path=path)

    def integer(value, low, high):
        require(type(value) is int and low <= value <= high, "ACT integer out of range", path=path)

    def floating(value, positive=False):
        require(type(value) in (int, float) and abs(value) <= 3.4028234663852886e38
                and math.isfinite(value) and (not positive or value > 0),
                "ACT float must be finite, representable and positive for delays", path=path)
        require(not positive or struct.unpack("<f", struct.pack("<f", value))[0] > 0,
                "ACT delay underflows float32", path=path)

    def raw(value, size):
        require(isinstance(value, str) and len(value) == size * 2,
                "ACT raw record must have exact hexadecimal length", path=path)
        try:
            decoded = bytes.fromhex(value)
        except ValueError:
            require(False, "ACT raw record must be hexadecimal", path=path)
        require(len(decoded) == size, "invalid ACT raw record length", path=path)

    def sequence(value, limit):
        require(isinstance(value, (list, tuple)) and len(value) <= limit,
                "invalid ACT sequence/count", path=path)

    keys(act, ("reserved", "actions", "events", "delays"))
    raw(act["reserved"], 10)
    sequence(act["actions"], MAX_ACTIONS)
    require(len(act["actions"]) > 0, "invalid action count", path=path)
    sequence(act["delays"], MAX_ACTIONS)
    require(len(act["delays"]) == len(act["actions"]), "delay count must match action count", path=path)
    for delay in act["delays"]:
        floating(delay, positive=True)
    sequence(act["events"], MAX_EVENTS)
    for event in act["events"]:
        raw(event, EVENT_RECORD_SIZE)
    motions = clips = 0
    for action in act["actions"]:
        sequence(action, MAX_MOTIONS_PER_ACTION)
        motions += len(action)
        require(motions <= MAX_TOTAL_MOTIONS, "cumulative motion budget exceeded", path=path)
        for motion in action:
            keys(motion, ("bounds", "clips", "event", "anchors"))
            sequence(motion["bounds"], 8)
            require(len(motion["bounds"]) == 8, "ACT bounds must contain eight integers", path=path)
            for value in motion["bounds"]:
                integer(value, -2**31, 2**31-1)
            integer(motion["event"], -1, len(act["events"])-1)
            sequence(motion["clips"], MAX_CLIPS_PER_MOTION)
            clips += len(motion["clips"])
            require(clips <= MAX_TOTAL_CLIPS, "cumulative clip budget exceeded", path=path)
            for clip in motion["clips"]:
                keys(clip, CLIP_FIELDS)
                for field in ("x", "y", "angle"):
                    integer(clip[field], -2**31, 2**31-1)
                integer(clip["sprite"], -1, 2**31-1)
                for field in ("mirror", "color", "pool"):
                    integer(clip[field], 0, 2**32-1)
                # Preserve raw uint mirror/pool metadata; pair validation checks visible pools.
                for field in ("scale_x", "scale_y"):
                    floating(clip[field])
            sequence(motion["anchors"], MAX_ANCHORS_PER_MOTION)
            for anchor in motion["anchors"]:
                keys(anchor, ANCHOR_FIELDS)
                for field in ("x", "y"):
                    integer(anchor[field], -2**31, 2**31-1)
                for field in ("opaque", "attribute"):
                    integer(anchor[field], 0, 2**32-1)


def write_act(act: dict[str, Any], *, path: str | None = None) -> bytes:
    """Serialize structured ACT data into ACT 2.4 binary format."""
    _validate_act(act, path=path)
    require("actions" in act and "reserved" in act and "events" in act and "delays" in act, "malformed ACT dictionary", path=path)
    actions = act["actions"]
    count = len(actions)
    require(0 < count <= MAX_ACTIONS, "invalid action count", path=path)
    delays = act["delays"]
    require(len(delays) == count, f"delay count ({len(delays)}) must match action count ({count})", path=path)
    reserved_bytes = bytes.fromhex(act["reserved"])
    require(len(reserved_bytes) == 10, "reserved header must be exactly 10 bytes", path=path)

    out = bytearray(ACT_MAGIC + ACT_SUPPORTED_VERSION + struct.pack("<H", count))
    out += reserved_bytes

    for action in actions:
        out += struct.pack("<I", len(action))
        for m in action:
            out += struct.pack("<8iI", *m["bounds"], len(m["clips"]))
            for c in m["clips"]:
                out += struct.pack(
                    "<iiiIIffiI",
                    *[c[k] for k in CLIP_FIELDS],
                )
            out += struct.pack("<iI", m["event"], len(m["anchors"]))
            for a in m["anchors"]:
                out += struct.pack("<IiiI", *[a[k] for k in ANCHOR_FIELDS])

    out += struct.pack("<I", len(act["events"]))
    out += b"".join(bytes.fromhex(e) for e in act["events"])
    out += struct.pack("<" + "f" * len(delays), *delays)
    return bytes(out)
