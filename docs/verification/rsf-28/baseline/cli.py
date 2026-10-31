import hashlib
"""M0 CLI contracts and filesystem preflight; core owns operation semantics."""

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Sequence

from ro_sprite_forge import __version__
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.operations import Operation, Request, execute
from ro_sprite_forge.core.preservation import roundtrip_pair
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.requirements import requirements
from ro_sprite_forge.report_io import publish, publish_resources, read_bytes, read_json


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, message)


def build_parser() -> Parser:
    parser = Parser(
        prog="ro-sprite-forge",
        description="Local resource inventory and bounded requirements. No artwork or native verification.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation, purpose in (
        (Operation.INSPECT, "Inventory supported ACT 2.4 / SPR 2.1 resources as canonical JSON."),
        (Operation.PLAN, "Calculate bounded target requirements; unresolved declarations stay provisional."),
        (Operation.VERIFY, "Verify ACT/SPR structure and Python semantic roundtrip; no Rust/native claim."),
        (Operation.ROUNDTRIP, "Preserve unchanged ACT/SPR resources or explicitly serialize ACT."),
    ):
        sub = commands.add_parser(operation.value, help=purpose, description=purpose)
        if operation in (Operation.INSPECT, Operation.ROUNDTRIP):
            sub.add_argument("--act", required=True, help="Existing regular ACT input file.")
            sub.add_argument("--spr", required=True, help="Existing regular SPR input file.")
        if operation == Operation.INSPECT:
            sub.add_argument("--json", required=True, dest="output", help="New canonical inventory JSON path; parent must exist.")
            sub.add_argument("--actor", default="unspecified", help="Stable operator-supplied actor namespace, independent of filenames.")
            sub.add_argument("--part", default="body", help="Stable resource part namespace (body/head remain separate).")
            sub.add_argument("--runtime-profile", default="unverified", choices=("player", "npc", "monster", "unverified"), help="Frozen source-reviewed mapping, default unknown; never native proof.")
        elif operation == Operation.PLAN:
            for flag in ("inventory", "profile", "target"):
                sub.add_argument(f"--{flag}", required=True, help=f"Existing versioned {flag} JSON input; profile must match frozen record.")
            sub.add_argument("--output", required=True, help="New canonical requirements JSON path; parent must exist.")
        elif operation == Operation.VERIFY:
            sub.add_argument("--project", help="Legacy project verification (not yet implemented).")
            sub.add_argument("--act", help="Existing ACT 2.4 input.")
            sub.add_argument("--spr", help="Existing SPR 2.1 input.")
            sub.add_argument("--scope", choices=("full", "declared"), help="Explicit full-profile or declared-target scope.")
        else:
            sub.add_argument("--output-act", required=True, help="New ACT path; parent must exist.")
            sub.add_argument("--output-spr", required=True, help="New SPR path; parent must exist.")
            sub.add_argument("--mode", choices=("preserve", "act-semantic"), default="preserve", help="SPR always retains original bytes; conversion unsupported.")
    resolve = commands.add_parser('resolve', help='Resolve Target/v2 ordered topology without artwork.')
    for name in ('actor', 'profile', 'target'):
        resolve.add_argument('--' + name, required=True, help='Existing versioned contract JSON.')
    resolve.add_argument('--inventory', action='append', default=[], help='Explicit immutable inventory reference; repeat for resource parts.')
    resolve.add_argument('--output', required=True, help='New canonical requirements JSON path.')
    resolve.add_argument('--work-order', action='store_true', help='Also print the per-occurrence checklist.')
    ledger = commands.add_parser('ledger', help='Validate and resolve explicit artwork assignments; no image processing.')
    for name in ('requirements', 'ledger', 'output'):
        ledger.add_argument('--' + name, required=True)
    ledger.add_argument('--source', action='append', default=[], metavar='ID=PATH', help='Content bytes to verify; paths stay outside canonical reports.')
    ledger.add_argument('--missing-source', action='append', default=[], metavar='ID', help='Explicitly observed unavailable source.')
    impact = commands.add_parser('ledger-impact', help='Compare resolved ledger reports and dependency impact.')
    for name in ('before', 'after', 'output'):
        impact.add_argument('--' + name, required=True)
    impact.add_argument('--requirements', help='Current resolved requirements for orphan detection.')
    coverage = commands.add_parser('coverage', help='Evaluate target requirements coverage and export missing-art work orders.')
    coverage.add_argument('--requirements', required=True, help='Existing resolved requirements JSON.')
    coverage.add_argument('--ledger', help='Existing assignment ledger JSON (declaration or resolved report). Optional.')
    coverage.add_argument('--source', action='append', default=[], metavar='ID=PATH', help='Content bytes to verify; repeat for sources.')
    coverage.add_argument('--missing-source', action='append', default=[], metavar='ID', help='Explicitly observed unavailable source.')
    coverage.add_argument('--target', help='Optional target contract JSON.')
    coverage.add_argument('--output', help='New canonical coverage report JSON path.')
    coverage.add_argument('--work-order', action='store_true', help='Print human-readable missing-art work order to stdout.')
    coverage.add_argument('--work-order-output', help='New human-readable work order text output path.')
    coverage.add_argument('--filter', choices=('all', 'unresolved', 'supply_artwork', 'restore_or_locate_source', 'correct_invalid_source_or_assignment', 'resolve_requirements', 'verify_source_content', 'verify_transformation', 'review_artwork', 'review_stale', 'resolve_runtime_support'), default='unresolved', help='Filter displayed work order items.')
    missing = commands.add_parser('missing', help='Export human-readable missing-art work order.')
    missing.add_argument('--requirements', required=True, help='Existing resolved requirements JSON.')
    missing.add_argument('--ledger', help='Existing assignment ledger JSON. Optional.')
    missing.add_argument('--source', action='append', default=[], metavar='ID=PATH', help='Content bytes to verify.')
    missing.add_argument('--missing-source', action='append', default=[], metavar='ID', help='Explicitly observed unavailable source.')
    missing.add_argument('--target', help='Optional target contract JSON.')
    missing.add_argument('--output', help='New work order text output path; defaults to stdout.')
    missing.add_argument('--format', choices=('text', 'json'), default='text', help='Output format (text work order or canonical json).')
    missing.add_argument('--filter', choices=('all', 'unresolved', 'supply_artwork', 'restore_or_locate_source', 'correct_invalid_source_or_assignment', 'resolve_requirements', 'verify_source_content', 'verify_transformation', 'review_artwork', 'review_stale', 'resolve_runtime_support'), default='unresolved', help='Filter displayed work order items.')
    prev = commands.add_parser('preview', help='Render order-preserving multilayer preview frame.')
    prev.add_argument('--act', required=True, help='Existing regular ACT input file.')
    prev.add_argument('--spr', required=True, help='Existing regular SPR input file.')
    prev.add_argument('--action', type=int, default=0, help='Action/view slot index; default 0.')
    prev.add_argument('--frame', type=int, default=0, help='Frame/motion index within slot; default 0.')
    prev.add_argument('--head-act', help='Optional child/head ACT input for multipart actors.')
    prev.add_argument('--head-spr', help='Optional child/head SPR input for multipart actors.')
    prev.add_argument('--head-frame', type=int, help='Optional head frame index.')
    prev.add_argument('--origin', help='Canvas origin as X,Y; default 128,192.')
    prev.add_argument('--canvas-size', help='Canvas dimensions as W,H; default 256,256.')
    prev.add_argument('--auto-fit', action='store_true', help='Dynamically size canvas to contain all layers.')
    prev.add_argument('--output', help='Output PNG file path.')
    prev.add_argument('--json', help='Output canonical preview report JSON path.')
    prev.add_argument('--stdout-json', action='store_true', help='Print canonical report JSON to stdout.')
    animation = commands.add_parser('animation', help='Inspect raw ACT frames, pinned timing and compositor bounds; no approval.')
    for name in ('act', 'spr'):
        animation.add_argument('--' + name, required=True)
    animation.add_argument('--category', choices=('player', 'npc', 'monster', 'unverified'), default='unverified')
    select = animation.add_mutually_exclusive_group()
    select.add_argument('--action', help='Verified semantic action from the frozen category profile.')
    select.add_argument('--slot', type=int, help='Exact numeric ACT action/view slot; no modulo fallback.')
    animation.add_argument('--view', type=int, default=0)
    animation.add_argument('--direction', type=int)
    animation.add_argument('--camera-direction', type=int, default=0)
    animation.add_argument('--frame', type=int, default=0)
    movement = animation.add_mutually_exclusive_group()
    movement.add_argument('--step', type=int)
    movement.add_argument('--time-ms', type=int)
    animation.add_argument('--loop', action='store_true', help='Explicit manual-step wrap; runtime playback uses profile loop rules.')
    animation.add_argument('--speed', type=float, default=1.0, help='Explicit timed-preview speed multiplier.')
    animation.add_argument('--movement-speed', type=int, help='Required native Walk context.')
    animation.add_argument('--duration-ms', type=int, help='Required native Attack/Hurt context.')
    animation.add_argument('--diagnostic-frame-ms', type=float, help='Explicit diagnostic timing override; never native timing proof.')
    animation.add_argument('--head-act')
    animation.add_argument('--head-spr')
    animation.add_argument('--origin', default='128,192')
    animation.add_argument('--canvas-size', default='256,256')
    animation.add_argument('--auto-fit', action='store_true')
    animation.add_argument('--json', help='New canonical inspection report path; defaults to stdout.')
    animation.add_argument('--output', help='Optional new preview PNG path, published with the report.')

    comp = commands.add_parser('compare', help='Compare reference and candidate frames with objective metrics and overlays.')
    comp.add_argument('--ref-act', required=True, help='Reference ACT input.')
    comp.add_argument('--ref-spr', required=True, help='Reference SPR input.')
    ref_sel = comp.add_mutually_exclusive_group()
    ref_sel.add_argument('--ref-action', help='Reference semantic action.')
    ref_sel.add_argument('--ref-slot', type=int, help='Reference numeric slot.')
    comp.add_argument('--ref-view', type=int, default=0, help='Reference view index.')
    comp.add_argument('--ref-frame', type=int, default=0, help='Reference frame index.')
    comp.add_argument('--ref-category', choices=('player', 'npc', 'monster', 'unverified'), default='unverified')
    comp.add_argument('--ref-head-act', help='Optional reference head ACT input.')
    comp.add_argument('--ref-head-spr', help='Optional reference head SPR input.')
    comp.add_argument('--ref-actor', help='Reference actor namespace.')

    comp.add_argument('--cand-act', help='Candidate ACT input.')
    comp.add_argument('--cand-spr', help='Candidate SPR input.')
    cand_sel = comp.add_mutually_exclusive_group()
    cand_sel.add_argument('--cand-action', help='Candidate semantic action.')
    cand_sel.add_argument('--cand-slot', type=int, help='Candidate numeric slot.')
    comp.add_argument('--cand-view', type=int, default=0, help='Candidate view index.')
    comp.add_argument('--cand-frame', type=int, default=0, help='Candidate frame index.')
    comp.add_argument('--cand-category', choices=('player', 'npc', 'monster', 'unverified'), default='unverified')
    comp.add_argument('--cand-head-act', help='Optional candidate head ACT input.')
    comp.add_argument('--cand-head-spr', help='Optional candidate head SPR input.')
    comp.add_argument('--cand-actor', help='Candidate actor namespace.')

    comp.add_argument('--mode', choices=('SIDE_BY_SIDE', 'DIFFERENCE', 'ONION_SKIN', 'REFERENCE_ONLY', 'CANDIDATE_ONLY'), default='SIDE_BY_SIDE')
    comp.add_argument('--align', choices=('NONE', 'ORIGIN', 'BOUNDS_CENTER', 'EXPLICIT'), default='NONE')
    comp.add_argument('--displacement', default='0,0', help='Displacement X,Y for EXPLICIT alignment.')
    comp.add_argument('--overlays', help='Comma-separated overlays (origin,bounds,anchors,layers).')
    comp.add_argument('--canvas-size', default='256,256', help='Canvas dimensions W,H.')
    comp.add_argument('--origin', default='128,192', help='Canvas origin X,Y.')
    comp.add_argument('--auto-fit', action='store_true', help='Dynamically size canvas to fit layers.')
    comp.add_argument('--output', help='Output composite PNG path.')
    comp.add_argument('--diff-output', help='Optional difference PNG path.')
    comp.add_argument('--json', help='Output comparison report JSON path.')
    comp.add_argument('--stdout-json', action='store_true', help='Print report JSON to stdout.')

    cs = commands.add_parser('contact-sheet', help='Generate filmstrip / contact sheet of animation frames.')
    cs.add_argument('--act', required=True, help='ACT input file.')
    cs.add_argument('--spr', required=True, help='SPR input file.')
    cs.add_argument('--head-act', help='Optional head ACT input.')
    cs.add_argument('--head-spr', help='Optional head SPR input.')
    cs.add_argument('--category', choices=('player', 'npc', 'monster', 'unverified'), default='unverified')
    cs_sel = cs.add_mutually_exclusive_group()
    cs_sel.add_argument('--action', help='Semantic action name.')
    cs_sel.add_argument('--slot', type=int, help='Numeric ACT slot index.')
    cs.add_argument('--view', type=int, default=0)
    cs.add_argument('--direction', type=int)
    cs.add_argument('--camera-direction', type=int, default=0)
    cs.add_argument('--columns', type=int, default=8, help='Grid column count.')
    cs.add_argument('--scale', type=int, default=1, help='Integer zoom scale (nearest-neighbor).')
    cs.add_argument('--padding', type=int, default=4, help='Padding between tiles.')
    cs.add_argument('--margin', type=int, default=8, help='Margin around sheet.')
    cs.add_argument('--no-labels', action='store_true', help='Disable frame index labels.')
    cs.add_argument('--overlays', help='Comma-separated overlays (origin,bounds,anchors,layers).')
    cs.add_argument('--canvas-size', default='256,256')
    cs.add_argument('--origin', default='128,192')
    cs.add_argument('--auto-fit', action='store_true')
    cs.add_argument('--output', help='Output sheet PNG path.')
    cs.add_argument('--json', help='Output contact sheet report JSON path.')
    cs.add_argument('--stdout-json', action='store_true', help='Print report JSON to stdout.')

    seq = commands.add_parser('sequence', help='Export discrete PNG frame sequence and manifest.')
    seq.add_argument('--act', required=True, help='ACT input file.')
    seq.add_argument('--spr', required=True, help='SPR input file.')
    seq.add_argument('--head-act', help='Optional head ACT input.')
    seq.add_argument('--head-spr', help='Optional head SPR input.')
    seq.add_argument('--category', choices=('player', 'npc', 'monster', 'unverified'), default='unverified')
    seq_sel = seq.add_mutually_exclusive_group()
    seq_sel.add_argument('--action', help='Semantic action name.')
    seq_sel.add_argument('--slot', type=int, help='Numeric ACT slot index.')
    seq.add_argument('--view', type=int, default=0)
    seq.add_argument('--direction', type=int)
    seq.add_argument('--camera-direction', type=int, default=0)
    seq.add_argument('--output-dir', required=True, help='Output directory for exported frames and manifest.')
    seq.add_argument('--overlays', help='Comma-separated overlays (origin,bounds,anchors,layers).')
    seq.add_argument('--canvas-size', default='256,256')
    seq.add_argument('--origin', default='128,192')
    seq.add_argument('--auto-fit', action='store_true')
    seq.add_argument('--json', help='Optional additional output path for the manifest JSON.')
    seq.add_argument('--stdout-json', action='store_true', help='Print manifest JSON to stdout.')

    serve = commands.add_parser('serve', help='Start local loopback HTTP service for workbench.')
    serve.add_argument('--host', default='127.0.0.1', help='Host interface to bind (default: 127.0.0.1; must be loopback).')
    serve.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080).')
    serve.add_argument('--projects-dir', default='projects', help='Directory for project storage (default: ./projects).')
    serve.add_argument('--allow-insecure-remote', action='store_true', help='Explicitly allow binding to non-loopback interface.')

    comp_cmd = commands.add_parser('compile', help='Compile modified ACT 2.4 / SPR 2.1 resources with copy-on-write shared-reference isolation.')
    comp_cmd.add_argument('--act', required=True, help='Existing regular ACT 2.4 input file.')
    comp_cmd.add_argument('--spr', required=True, help='Existing regular SPR 2.1 input file.')
    comp_cmd.add_argument('--requirements', help='Resolved requirements JSON (required for replacement modes).')
    comp_cmd.add_argument('--ledger', help='Assignment ledger or resolved ledger JSON (required for replacement modes).')
    comp_cmd.add_argument('--source', action='append', default=[], metavar='ID=PATH', help='Staged PNG source bytes (ID=PATH); repeat for multiple sources.')
    comp_cmd.add_argument('--requirement-id', action='append', default=[], help='Specific requirement ID to replace; repeat for multiple.')
    comp_cmd.add_argument('--compilation-id', default='cli-compile', help='Compilation record ID (default: cli-compile).')
    comp_cmd.add_argument('--part', choices=('body', 'head'), default='body', help='Target actor part (default: body).')
    comp_cmd.add_argument('--mode', choices=('preserve', 'bounded_replacement', 'production_export'), default='bounded_replacement', help='Compilation mode.')
    comp_cmd.add_argument('--policy', choices=('preserve_pool', 'explicit_rgba', 'indexed_exact'), default='preserve_pool', help='Pool/encoding replacement policy.')
    comp_cmd.add_argument('--isolation', choices=('auto', 'always_append', 'in_place_only'), default='auto', help='Shared SPR reference isolation strategy.')
    comp_cmd.add_argument('--head-act', help='Optional companion head ACT input file.')
    comp_cmd.add_argument('--head-spr', help='Optional companion head SPR input file.')
    comp_cmd.add_argument('--oracle', help='Optional independent Rust oracle executable path for post-compile parity verification.')
    comp_cmd.add_argument('--output-prefix', default='compiled', help='Output filename prefix when using --output-dir (default: compiled).')
    comp_cmd.add_argument('--cache-dir', help='Optional immutable build cache (requires --output-dir).')
    comp_cmd.add_argument('--output-dir', help='Output directory for compiled .act, .spr, and compilation-manifest.json.')
    comp_cmd.add_argument('--output-act', help='Explicit new output ACT path (requires --output-spr).')
    comp_cmd.add_argument('--output-spr', help='Explicit new output SPR path (requires --output-act).')
    comp_cmd.add_argument('--manifest', help='Explicit new output compilation manifest JSON path.')
    comp_cmd.add_argument('--plan-only', action='store_true', help='Inspect pre-compilation plan JSON without writing ACT/SPR resources.')
    comp_cmd.add_argument('--stdout-json', action='store_true', help='Print compilation manifest or plan JSON to stdout.')
    return parser


def _path(value: str) -> Path:
    if not value or "\x00" in value:
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Paths must be nonempty and contain no NUL.")
    return Path(value)


def _input(value: str, *, directory: bool = False) -> None:
    path = _path(value)
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as exc:
        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, "Input path does not exist.", path=value) from exc
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot inspect input path.", path=value) from exc
    valid = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
    if not valid:
        raise ForgeError(ErrorCode.INVALID_INPUT, "Expected a directory." if directory else "Expected a regular file.", path=value)


def _output(value: str) -> None:
    path = _path(value)
    # lstat rejects even dangling output symlinks; never create, truncate or probe-write.
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot inspect output path.", path=value) from exc
    else:
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output already exists; overwriting is forbidden.", path=value)
    try:
        if not path.parent.is_dir():
            raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output parent must be an existing directory.", path=value)
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot inspect output parent.", path=value) from exc


def _publish_png(path: str, data: bytes) -> None:
    target = _path(path)
    temporary = None
    try:
        import os, tempfile
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".rsf-png-", delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    except FileExistsError as exc:
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output already exists; overwriting is forbidden.", path=path) from exc
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot publish PNG output.", path=path) from exc
    finally:
        if temporary is not None:
            try:
                import os
                os.unlink(temporary)
            except OSError:
                pass


def _publish_text(path: str, text: str) -> None:
    data = text.encode("utf-8")
    target = _path(path)
    temporary = None
    try:
        import os, tempfile
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".rsf-text-", delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    except FileExistsError as exc:
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output already exists; overwriting is forbidden.", path=path) from exc
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot publish text output.", path=path) from exc
    finally:
        if temporary is not None:
            try:
                import os
                os.unlink(temporary)
            except OSError:
                pass


def _request(args: argparse.Namespace) -> Request:
    operation = Operation(args.command)
    input_names = {
        Operation.INSPECT: ("act", "spr"),
        Operation.PLAN: ("inventory", "profile", "target"),
        Operation.VERIFY: ("project",),
        Operation.ROUNDTRIP: ("act", "spr"),
    }[operation]
    output_names = {
        Operation.INSPECT: ("output",), Operation.PLAN: ("output",),
        Operation.VERIFY: (), Operation.ROUNDTRIP: ("output_act", "output_spr"),
    }[operation]
    if operation == Operation.VERIFY:
        if args.project:
            if args.act or args.spr or not args.scope:
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Legacy project verification requires --scope and no resource inputs.")
        else:
            if not args.act or not args.spr or args.scope:
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Resource verification requires --act and --spr without --scope.")
            input_names = ("act", "spr")
    inputs = tuple((name, getattr(args, name)) for name in input_names)
    outputs = tuple((name, getattr(args, name)) for name in output_names)
    for name, value in inputs:
        _input(value, directory=name == "project")
    for _, value in outputs:
        _output(value)
    if len({str(_path(value).resolve()) for _, value in outputs}) != len(outputs):
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output paths must be distinct.")
    return Request(operation, inputs, outputs, getattr(args, "scope", None))


def main(argv: Sequence[str] | None = None) -> int:
    """Render expected errors on stderr; help/version use argparse's zero exit."""
    try:
        args = build_parser().parse_args(argv)
        if args.command == 'animation':
            from ro_sprite_forge.core.animation import AnimationInspector
            from ro_sprite_forge.core.canonical import check
            for value in (args.act, args.spr, args.head_act, args.head_spr):
                if value:
                    _input(value)
            for value in (args.json, args.output):
                if value:
                    _output(value)
            if args.time_ms is None:
                check(args.speed == 1.0 and args.movement_speed is None and args.duration_ms is None
                      and args.diagnostic_frame_ms is None, 'Timing options require --time-ms.')
                check(not args.loop or args.step is not None, '--loop requires --step.')
            else:
                check(not args.loop, '--loop controls manual stepping only; timed playback uses profile rules.')
            def pair(value):
                try:
                    values = tuple(int(v) for v in value.split(','))
                except ValueError as exc:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Expected two comma-separated integers.') from exc
                check(len(values) == 2, 'Expected two comma-separated integers.')
                return values
            inspector = AnimationInspector(read_bytes(args.act), read_bytes(args.spr), category=args.category,
                head_act_bytes=read_bytes(args.head_act) if args.head_act else None,
                head_spr_bytes=read_bytes(args.head_spr) if args.head_spr else None)
            selection = inspector.timeline.select(action=args.action, slot=args.slot if args.action else (args.slot if args.slot is not None else 0),
                view=args.view, direction=args.direction, camera_direction=args.camera_direction, frame=args.frame)
            if args.step is not None:
                selection = inspector.timeline.step(selection, args.step, loop=args.loop)
            if args.time_ms is not None:
                selection = inspector.timeline.seek(selection, args.time_ms, speed=args.speed,
                    movement_speed=args.movement_speed, duration_ms=args.duration_ms,
                    diagnostic_frame_ms=args.diagnostic_frame_ms)
            result = inspector.inspect(selection, canvas_size=pair(args.canvas_size), origin=pair(args.origin), auto_fit=args.auto_fit)
            artifacts = []
            if args.json:
                artifacts.append((args.json, canonical_bytes(result['report'])))
            if args.output:
                artifacts.append((args.output, result['png_bytes']))
            if artifacts:
                publish_resources(tuple(artifacts))
            if not args.json:
                sys.stdout.write(canonical_bytes(result['report']).decode('utf-8'))
            return 0
        if args.command == 'preview':
            from ro_sprite_forge.formats.act import read_act
            from ro_sprite_forge.formats.spr import read_spr
            from ro_sprite_forge.formats.preview import composite_frame
            _input(args.act)
            _input(args.spr)
            if args.head_act:
                _input(args.head_act)
            if args.head_spr:
                _input(args.head_spr)
            if args.output:
                _output(args.output)
            if args.json:
                _output(args.json)

            act_bytes = read_bytes(args.act)
            spr_bytes = read_bytes(args.spr)
            source_hashes = {
                'act': hashlib.sha256(act_bytes).hexdigest(),
                'spr': hashlib.sha256(spr_bytes).hexdigest(),
            }
            act_data = read_act(act_bytes, path=args.act)
            spr_doc = read_spr(spr_bytes, path=args.spr)

            head_act_data = None
            head_spr_doc = None
            if args.head_act and args.head_spr:
                h_act_b = read_bytes(args.head_act)
                h_spr_b = read_bytes(args.head_spr)
                head_act_data = read_act(h_act_b, path=args.head_act)
                head_spr_doc = read_spr(h_spr_b, path=args.head_spr)
                source_hashes['head_act'] = hashlib.sha256(h_act_b).hexdigest()
                source_hashes['head_spr'] = hashlib.sha256(h_spr_b).hexdigest()

            origin = None
            if args.origin:
                parts = args.origin.split(',')
                if len(parts) != 2:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Origin must be X,Y.')
                origin = (int(parts[0]), int(parts[1]))

            canvas_size = None
            if args.canvas_size:
                parts = args.canvas_size.split(',')
                if len(parts) != 2:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Canvas size must be W,H.')
                canvas_size = (int(parts[0]), int(parts[1]))

            res = composite_frame(
                act_data,
                spr_doc,
                args.action,
                args.frame,
                head_act_data=head_act_data,
                head_spr_doc=head_spr_doc,
                head_frame_idx=args.head_frame,
                origin=origin,
                canvas_size=canvas_size,
                auto_fit=args.auto_fit,
                source_hashes=source_hashes,
            )

            if args.output:
                _publish_png(args.output, res['png_bytes'])
            if args.json:
                publish(args.json, res['report'])
            if args.stdout_json or (not args.output and not args.json):
                sys.stdout.write(canonical_bytes(res['report']).decode('utf-8'))
            return 0
        if args.command in ('coverage', 'missing'):
            from ro_sprite_forge.core.coverage import evaluate_coverage, format_work_order
            _input(args.requirements)
            if getattr(args, 'ledger', None):
                _input(args.ledger)
            if getattr(args, 'target', None):
                _input(args.target)
            if getattr(args, 'output', None):
                _output(args.output)
            if getattr(args, 'work_order_output', None):
                _output(args.work_order_output)
            data = {}
            for declaration in args.source:
                if '=' not in declaration:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Source must be ID=PATH.')
                sid, path = declaration.split('=', 1)
                if sid in data or sid in args.missing_source:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Duplicate source observation.')
                _input(path)
                data[sid] = read_bytes(path)
            for sid in args.missing_source:
                if sid in data:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Duplicate source observation.')
                data[sid] = None
            resolved_requirements = read_json(args.requirements)
            ledger_data = read_json(args.ledger) if getattr(args, 'ledger', None) else None
            target_data = read_json(args.target) if getattr(args, 'target', None) else None
            report = evaluate_coverage(resolved_requirements, ledger_data, source_bytes=data, target=target_data)

            filter_cat = args.filter if args.filter not in ('all', 'unresolved') else None
            filter_st = args.filter if args.filter in ('all', 'unresolved') else 'unresolved'
            work_order_text = format_work_order(report, filter_category=filter_cat, filter_status=filter_st)

            if args.command == 'coverage':
                if args.output:
                    publish(args.output, report)
                if args.work_order_output:
                    _publish_text(args.work_order_output, work_order_text)
                if args.work_order or (not args.output and not args.work_order_output):
                    sys.stdout.write(work_order_text)
            else:  # missing
                fmt = getattr(args, 'format', 'text')
                if args.output:
                    if fmt == 'json':
                        publish(args.output, report)
                    else:
                        _publish_text(args.output, work_order_text)
                else:
                    if fmt == 'json':
                        sys.stdout.write(canonical_bytes(report).decode('utf-8'))
                    else:
                        sys.stdout.write(work_order_text)
            return 0
        if args.command in ('ledger', 'ledger-impact'):
            from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger, compare_ledgers
            _output(args.output)
            if args.command == 'ledger':
                for path in (args.requirements, args.ledger):
                    _input(path)
                data = {}
                for declaration in args.source:
                    if '=' not in declaration:
                        raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Source must be ID=PATH.')
                    sid, path = declaration.split('=', 1)
                    if sid in data or sid in args.missing_source:
                        raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Duplicate source observation.')
                    _input(path)
                    data[sid] = read_bytes(path)
                for sid in args.missing_source:
                    if sid in data:
                        raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Duplicate source observation.')
                    data[sid] = None
                resolved_requirements = read_json(args.requirements)
                ledger = load_ledger(read_json(args.ledger), requirements=resolved_requirements)
                report = resolve_ledger(ledger, requirements=resolved_requirements, source_bytes=data)
                publish(args.output, report)
                if any(a['kind'] != 'UNASSIGNED' and (a['validation'] != 'VALID' or a['availability'] not in ('AVAILABLE', 'REUSED'))
                       for a in report['assignments']):
                    raise ForgeError(ErrorCode.INVALID_INPUT, 'SOURCE_VERIFICATION_INCOMPLETE: diagnostic report published; no approved resource produced.')
            else:
                for path in (args.before, args.after):
                    _input(path)
                if args.requirements:
                    _input(args.requirements)
                report = compare_ledgers(read_json(args.before), read_json(args.after),
                    current_requirements=read_json(args.requirements) if args.requirements else None)
                publish(args.output, report)
            return 0
        if args.command == 'resolve':
            from ro_sprite_forge.core.contracts import load_actor, load_runtime_profile, load_target
            from ro_sprite_forge.core.topology import resolve_topology, topology_work_order
            for path in (args.actor, args.profile, args.target, *args.inventory):
                _input(path)
            _output(args.output)
            actor = load_actor(read_json(args.actor))
            profile = load_runtime_profile(read_json(args.profile))
            target = load_target(read_json(args.target), actor=actor, profile=profile)
            report = resolve_topology(target, actor=actor, profile=profile,
                                      inventories=tuple(read_json(p) for p in args.inventory))
            publish(args.output, report)
            if args.work_order:
                sys.stdout.write(topology_work_order(report))
            return 0
        if args.command == 'compare':
            from ro_sprite_forge.core.animation import AnimationInspector
            from ro_sprite_forge.core.comparison import compare_frames
            from ro_sprite_forge.core.canonical import check
            _input(args.ref_act)
            _input(args.ref_spr)
            if args.ref_head_act:
                _input(args.ref_head_act)
            if args.ref_head_spr:
                _input(args.ref_head_spr)
            if args.cand_act:
                _input(args.cand_act)
            if args.cand_spr:
                _input(args.cand_spr)
            if args.cand_head_act:
                _input(args.cand_head_act)
            if args.cand_head_spr:
                _input(args.cand_head_spr)
            if args.output:
                _output(args.output)
            if args.diff_output:
                _output(args.diff_output)
            if args.json:
                _output(args.json)

            def pair(value):
                try:
                    values = tuple(int(v.strip()) for v in value.split(','))
                except ValueError as exc:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Expected two comma-separated integers.') from exc
                check(len(values) == 2, 'Expected two comma-separated integers.')
                return values

            overlays = [o.strip() for o in args.overlays.split(',')] if args.overlays else None
            disp = pair(args.displacement)

            ref_inspector = AnimationInspector(
                read_bytes(args.ref_act),
                read_bytes(args.ref_spr),
                category=args.ref_category,
                head_act_bytes=read_bytes(args.ref_head_act) if args.ref_head_act else None,
                head_spr_bytes=read_bytes(args.ref_head_spr) if args.ref_head_spr else None,
            )
            ref_action = args.ref_action
            ref_slot = args.ref_slot if ref_action is None else None
            if ref_action is None and ref_slot is None:
                ref_slot = 0

            ref_selection = ref_inspector.timeline.select(
                action=ref_action,
                slot=ref_slot,
                view=args.ref_view,
                frame=args.ref_frame,
            )

            cand_inspector = None
            cand_selection = None
            if args.cand_act and args.cand_spr:
                cand_inspector = AnimationInspector(
                    read_bytes(args.cand_act),
                    read_bytes(args.cand_spr),
                    category=args.cand_category,
                    head_act_bytes=read_bytes(args.cand_head_act) if args.cand_head_act else None,
                    head_spr_bytes=read_bytes(args.cand_head_spr) if args.cand_head_spr else None,
                )
                cand_action = args.cand_action
                cand_slot = args.cand_slot if cand_action is None else None
                if cand_action is None and cand_slot is None:
                    cand_slot = 0
                cand_selection = cand_inspector.timeline.select(
                    action=cand_action,
                    slot=cand_slot,
                    view=args.cand_view,
                    frame=args.cand_frame,
                )

            res = compare_frames(
                ref_inspector,
                cand_inspector,
                ref_selection,
                cand_selection,
                mode=args.mode,
                alignment=args.align,
                displacement=disp,
                overlays=overlays,
                canvas_size=pair(args.canvas_size),
                origin=pair(args.origin),
                auto_fit=args.auto_fit,
                actor=args.ref_actor,
                candidate_actor=args.cand_actor,
            )

            artifacts = []
            if args.output:
                artifacts.append((args.output, res['png_bytes']))
            if args.diff_output and res['difference_png_bytes']:
                artifacts.append((args.diff_output, res['difference_png_bytes']))
            if args.json:
                artifacts.append((args.json, canonical_bytes(res['report'])))
            if artifacts:
                publish_resources(tuple(artifacts))
            if args.stdout_json or (not args.output and not args.json):
                sys.stdout.write(canonical_bytes(res['report']).decode('utf-8'))
            return 0

        if args.command == 'contact-sheet':
            from ro_sprite_forge.core.animation import AnimationInspector
            from ro_sprite_forge.core.contact_sheet import generate_contact_sheet
            from ro_sprite_forge.core.canonical import check
            _input(args.act)
            _input(args.spr)
            if args.head_act:
                _input(args.head_act)
            if args.head_spr:
                _input(args.head_spr)
            if args.output:
                _output(args.output)
            if args.json:
                _output(args.json)

            def pair(value):
                try:
                    values = tuple(int(v.strip()) for v in value.split(','))
                except ValueError as exc:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Expected two comma-separated integers.') from exc
                check(len(values) == 2, 'Expected two comma-separated integers.')
                return values

            overlays = [o.strip() for o in args.overlays.split(',')] if args.overlays else None
            inspector = AnimationInspector(
                read_bytes(args.act),
                read_bytes(args.spr),
                category=args.category,
                head_act_bytes=read_bytes(args.head_act) if args.head_act else None,
                head_spr_bytes=read_bytes(args.head_spr) if args.head_spr else None,
            )
            cs_action = args.action
            cs_slot = args.slot if cs_action is None else None
            if cs_action is None and cs_slot is None:
                cs_slot = 0
            selection = inspector.timeline.select(
                action=cs_action,
                slot=cs_slot,
                view=args.view,
                direction=args.direction,
                camera_direction=args.camera_direction,
                frame=0,
            )
            res = generate_contact_sheet(
                inspector,
                selection,
                columns=args.columns,
                scale=args.scale,
                padding=args.padding,
                margin=args.margin,
                labels=not args.no_labels,
                overlays=overlays,
                canvas_size=pair(args.canvas_size),
                origin=pair(args.origin),
                auto_fit=args.auto_fit,
            )
            artifacts = []
            if args.output:
                artifacts.append((args.output, res['png_bytes']))
            if args.json:
                artifacts.append((args.json, canonical_bytes(res['report'])))
            if artifacts:
                publish_resources(tuple(artifacts))
            if args.stdout_json or (not args.output and not args.json):
                sys.stdout.write(canonical_bytes(res['report']).decode('utf-8'))
            return 0

        if args.command == 'sequence':
            from ro_sprite_forge.core.animation import AnimationInspector
            from ro_sprite_forge.core.contact_sheet import export_frame_sequence
            from ro_sprite_forge.core.canonical import check
            _input(args.act)
            _input(args.spr)
            if args.head_act:
                _input(args.head_act)
            if args.head_spr:
                _input(args.head_spr)
            if args.json:
                _output(args.json)

            def pair(value):
                try:
                    values = tuple(int(v.strip()) for v in value.split(','))
                except ValueError as exc:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Expected two comma-separated integers.') from exc
                check(len(values) == 2, 'Expected two comma-separated integers.')
                return values

            overlays = [o.strip() for o in args.overlays.split(',')] if args.overlays else None
            inspector = AnimationInspector(
                read_bytes(args.act),
                read_bytes(args.spr),
                category=args.category,
                head_act_bytes=read_bytes(args.head_act) if args.head_act else None,
                head_spr_bytes=read_bytes(args.head_spr) if args.head_spr else None,
            )
            cs_action = args.action
            cs_slot = args.slot if cs_action is None else None
            if cs_action is None and cs_slot is None:
                cs_slot = 0
            selection = inspector.timeline.select(
                action=cs_action,
                slot=cs_slot,
                view=args.view,
                direction=args.direction,
                camera_direction=args.camera_direction,
                frame=0,
            )
            manifest = export_frame_sequence(
                inspector,
                selection,
                args.output_dir,
                overlays=overlays,
                canvas_size=pair(args.canvas_size),
                origin=pair(args.origin),
                auto_fit=args.auto_fit,
            )
            if args.json:
                publish(args.json, manifest)
            if args.stdout_json or not args.json:
                sys.stdout.write(canonical_bytes(manifest).decode('utf-8'))
            return 0
        if args.command == 'compile':
            from ro_sprite_forge.core.compiler import compile_resources, plan_compilation, publish_compilation
            _input(args.act)
            _input(args.spr)
            if args.requirements:
                _input(args.requirements)
            if args.ledger:
                _input(args.ledger)
            if args.head_act:
                _input(args.head_act)
            if args.head_spr:
                _input(args.head_spr)
            if args.oracle:
                _input(args.oracle)
            if bool(args.output_act) != bool(args.output_spr):
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Supply both --output-act and --output-spr together.')
            if args.output_dir and (args.output_act or args.output_spr):
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Cannot combine --output-dir with --output-act/--output-spr.')
            if not args.plan_only and not args.output_dir and not args.output_act:
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Compilation requires --output-dir or (--output-act and --output-spr), unless --plan-only is set.')
            if args.cache_dir and not args.output_dir:
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, '--cache-dir requires --output-dir.')
            if args.mode == 'production_export' and not args.plan_only and not args.output_dir:
                raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Production export requires atomic --output-dir publication.')
            if args.output_act:
                _output(args.output_act)
                _output(args.output_spr)
                if Path(args.output_act).resolve() == Path(args.output_spr).resolve():
                    raise ForgeError(ErrorCode.INVALID_OUTPUT, 'Output paths must be distinct.')
            if args.manifest:
                _output(args.manifest)

            source_data = {}
            for declaration in args.source:
                if '=' not in declaration:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, 'Source must be ID=PATH.')
                sid, spath = declaration.split('=', 1)
                if sid in source_data:
                    raise ForgeError(ErrorCode.INVALID_ARGUMENT, f'Duplicate source observation for {sid}.')
                _input(spath)
                source_data[sid] = read_bytes(spath)

            req_doc = read_json(args.requirements) if args.requirements else None
            led_doc = read_json(args.ledger) if args.ledger else None
            req_ids = args.requirement_id if args.requirement_id else None

            if args.plan_only:
                plan = plan_compilation(
                    read_bytes(args.act),
                    read_bytes(args.spr),
                    requirements=req_doc,
                    ledger=led_doc,
                    source_bytes=source_data,
                    replacement_requirement_ids=req_ids,
                    part=args.part,
                    compilation_mode=args.mode,
                    replacement_policy=args.policy,
                    isolation_strategy=args.isolation,
                    output_prefix=args.output_prefix,
                )
                if args.manifest:
                    publish(args.manifest, plan)
                if args.stdout_json or not args.manifest:
                    sys.stdout.write(canonical_bytes(plan).decode('utf-8'))
                return 0

            comp_res = compile_resources(
                read_bytes(args.act),
                read_bytes(args.spr),
                requirements=req_doc,
                ledger=led_doc,
                source_bytes=source_data,
                replacement_requirement_ids=req_ids,
                compilation_id=args.compilation_id,
                part=args.part,
                compilation_mode=args.mode,
                replacement_policy=args.policy,
                isolation_strategy=args.isolation,
                head_act_bytes=read_bytes(args.head_act) if args.head_act else None,
                head_spr_bytes=read_bytes(args.head_spr) if args.head_spr else None,
                output_prefix=args.output_prefix,
                oracle_executable=args.oracle,
            )

            if args.output_dir:
                publish_compilation(args.output_dir, comp_res, cache_dir=args.cache_dir)
            elif args.output_act and args.output_spr:
                publish_resources(((args.output_act, comp_res['act_bytes']), (args.output_spr, comp_res['spr_bytes'])))
            if args.manifest:
                publish(args.manifest, comp_res['manifest'])
            if args.stdout_json or (not args.manifest and not args.output_dir):
                sys.stdout.write(canonical_bytes(comp_res['manifest']).decode('utf-8'))
            return 0
        if args.command == 'serve':
            from ro_sprite_forge.service.server import create_server
            server = create_server(
                projects_dir=args.projects_dir,
                host=args.host,
                port=args.port,
                allow_insecure_remote=args.allow_insecure_remote,
            )
            print(f"RO Sprite Forge service running at {server.url}", flush=True)
            print(f"CSRF Token: {server.security.csrf_token}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        request = _request(args)
        if request.operation == Operation.INSPECT:
            report = inventory(read_bytes(args.act), read_bytes(args.spr), actor=args.actor,
                               part=args.part, profile=get_profile(args.runtime_profile))
            publish(args.output, report)
        elif request.operation == Operation.PLAN:
            report = requirements(read_json(args.inventory), read_json(args.profile), read_json(args.target))
            publish(args.output, report)
        elif request.operation == Operation.ROUNDTRIP or (request.operation == Operation.VERIFY and not args.project):
            act, spr, report = roundtrip_pair(read_bytes(args.act), read_bytes(args.spr), mode=getattr(args, "mode", "preserve"))
            if request.operation == Operation.ROUNDTRIP:
                publish_resources(((args.output_act, act), (args.output_spr, spr)))
            sys.stdout.write(canonical_bytes(report).decode("utf-8"))
        else:
            execute(request)
    except ForgeError as exc:
        error = {"code": exc.code.value, "message": exc.message}
        if exc.path is not None:
            error["path"] = exc.path
        print(json.dumps({"error": error}, sort_keys=True), file=sys.stderr)
        if exc.code == ErrorCode.INVALID_ARGUMENT:
            return 2
        if exc.code == ErrorCode.NOT_IMPLEMENTED:
            return 4
        return 3
    return 0
