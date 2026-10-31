"""Local HTTP application server and request router for RO Sprite Forge (RSF-15).

Provides a secure, bounded loopback HTTP API exposing existing core use cases:
- Project creation, loading, saving and listing.
- Atomic publication and optimistic concurrency control.
- Content-addressed source blob imports and retrievals.
- Host, Origin and CSRF token protection on all state-changing endpoints.
- Strict payload limits, anti-traversal protections and typed JSON errors.
"""
from __future__ import annotations

import base64
from http import HTTPStatus
import http.server
import json
import logging
from pathlib import Path
import re
import socket
from typing import Any
import urllib.parse

from ro_sprite_forge import __version__
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.contracts import (
    ActorContract,
    RuntimeProfileContract,
    TargetContract,
    frozen_runtime_profile,
    load_actor,
    load_runtime_profile,
    load_target,
    reference,
)
from ro_sprite_forge.core.coverage import evaluate_coverage, format_work_order
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import (
    create_project,
    get_blob,
    import_blob,
    list_projects,
    load_project,
    save_project,
    validate_path_containment,
)
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.service.security import SecurityManager

logger = logging.getLogger("ro_sprite_forge.service")

MAX_REQUEST_BODY_SIZE = 48 * 1024 * 1024  # 48 MiB (allows 32 MiB raw binary or base64 JSON upload)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

STATIC_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def make_standard_actor_doc(
    actor_id: str,
    profile_contract: RuntimeProfileContract,
    parts: list[str] | None = None,
) -> dict:
    if parts is None:
        parts = ["body", "head"] if profile_contract.category == "player" else ["body"]
    return {
        "schema": "rsf.actor/v1",
        "id": actor_id,
        "revision": 1,
        "previous_sha256": None,
        "category": profile_contract.category,
        "gameplay_job": "job-default",
        "visual": {"body_family": "default", "sex": None, "body_variant": "adult", "costume": "default"},
        "parts": parts,
        "runtime_profile": reference(profile_contract),
        "action_profile": "operator-choreography",
        "compatibility": {"status": "UNVERIFIED", "declarations": []},
        "resources": [],
    }


def _get_project_actor_and_profile(
    manifest: dict[str, Any], project_dir: Path | None = None
) -> tuple[ActorContract, RuntimeProfileContract]:
    profile_val = manifest.get("profile", "player")
    if isinstance(profile_val, dict):
        profile_contract = load_runtime_profile(profile_val)
    elif isinstance(profile_val, str) and profile_val in ("player", "monster", "npc", "unverified"):
        profile_contract = frozen_runtime_profile(profile_val)
    else:
        profile_contract = frozen_runtime_profile("player")

    if project_dir is not None:
        actor_file = project_dir / "actor.json"
        if actor_file.exists() and actor_file.is_file():
            try:
                actor_contract = load_actor(json.loads(actor_file.read_text(encoding="utf-8")))
                return actor_contract, profile_contract
            except Exception:
                pass

    actor_val = manifest.get("actor", "player")
    if isinstance(actor_val, dict):
        actor_contract = load_actor(actor_val)
    else:
        target_data = manifest.get("target")
        actor_id = (
            target_data.get("actor", {}).get("id")
            if target_data and isinstance(target_data.get("actor"), dict)
            else str(actor_val)
        )
        cat = profile_contract.category
        parts = (
            target_data.get("parts")
            if target_data and isinstance(target_data.get("parts"), list)
            else (["body", "head"] if cat == "player" else ["body"])
        )
        actor_doc = make_standard_actor_doc(actor_id, profile_contract, parts)
        actor_contract = load_actor(actor_doc)

    return actor_contract, profile_contract


def _resolve_project_requirements(
    project_dir: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Any] | None, TargetContract | None]:
    target_data = manifest.get("target")
    if not target_data:
        return None, None

    actor_contract, profile_contract = _get_project_actor_and_profile(manifest, project_dir=project_dir)
    target_contract = load_target(target_data, actor=actor_contract, profile=profile_contract)

    inv_list = []
    if manifest.get("inventory"):
        inv_list.append(manifest["inventory"])
    for r in manifest.get("resources", []):
        if isinstance(r, dict) and r.get("inventory") and r["inventory"] not in inv_list:
            inv_list.append(r["inventory"])
    inventories = tuple(inv_list)
    resolved = resolve_topology(
        target_contract, actor=actor_contract, profile=profile_contract, inventories=inventories
    )
    return resolved, target_contract


def _evaluate_project_coverage(project_dir: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    resolved_reqs, target_contract = _resolve_project_requirements(project_dir, manifest)
    if resolved_reqs is None or target_contract is None:
        return None

    from ro_sprite_forge.service.workbench import workspace
    coverage_report = workspace(project_dir.parent, manifest)['coverage']
    return coverage_report


class ForgeRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler implementing RESTful endpoints over the Python application core."""

    server: ForgeServer  # Type hint for server attribute

    # Disable default noisy HTTP request stderr logging in automated tests
    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

    def _send_cors_and_security_headers(self) -> None:
        origin = self.headers.get("Origin") or self.headers.get("origin")
        cors_headers = self.server.security.get_cors_headers(origin)
        for header, val in cors_headers.items():
            self.send_header(header, val)

        # Baseline security headers for all responses
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")

    def send_json(self, status: int, data: dict[str, Any]) -> None:
        from ro_sprite_forge.service.media import browser_safe
        body = canonical_bytes(browser_safe(data))
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_and_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status: int, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_and_security_headers()
        self.end_headers()
        self.wfile.write(data)

    def send_forge_error(self, exc: ForgeError) -> None:
        status_map = {
            ErrorCode.INVALID_ARGUMENT: HTTPStatus.BAD_REQUEST,
            ErrorCode.INVALID_INPUT: HTTPStatus.UNPROCESSABLE_ENTITY,
            ErrorCode.INPUT_NOT_FOUND: HTTPStatus.NOT_FOUND,
            ErrorCode.CONFLICT: HTTPStatus.CONFLICT,
            ErrorCode.PERMISSION_DENIED: HTTPStatus.FORBIDDEN,
            ErrorCode.PAYLOAD_TOO_LARGE: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            ErrorCode.INVALID_OUTPUT: HTTPStatus.BAD_REQUEST,
            ErrorCode.IO_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
            ErrorCode.NOT_IMPLEMENTED: HTTPStatus.NOT_IMPLEMENTED,
        }
        status = status_map.get(exc.code, HTTPStatus.BAD_REQUEST)
        error_payload: dict[str, Any] = {
            "code": exc.code.value,
            "message": exc.message,
        }
        if exc.path is not None:
            # Mask absolute machine paths to avoid filesystem information disclosure
            error_payload["path"] = Path(exc.path).name

        self.send_json(status.value, {"error": error_payload})

    def read_request_body(self) -> bytes:
        """Safely read request body with bounded size validation."""
        content_length_str = self.headers.get("Content-Length")
        if not content_length_str:
            return b""

        try:
            content_length = int(content_length_str)
        except ValueError as exc:
            raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Invalid Content-Length header.") from exc

        if content_length < 0:
            raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Negative Content-Length header.")

        if content_length > MAX_REQUEST_BODY_SIZE:
            raise ForgeError(
                ErrorCode.PAYLOAD_TOO_LARGE,
                f"Request body size {content_length} bytes exceeds {MAX_REQUEST_BODY_SIZE} bytes limit.",
            )

        body = self.rfile.read(content_length)
        if len(body) != content_length:
            raise ForgeError(ErrorCode.INVALID_INPUT, "Incomplete request body read.")
        return body

    def read_json_body(self) -> dict[str, Any]:
        body = self.read_request_body()
        if not body:
            raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Missing required JSON request body.")
        try:
            val = json.loads(body.decode("utf-8"))
            if not isinstance(val, dict):
                raise ValueError("JSON root must be an object.")
            return val
        except Exception as exc:
            raise ForgeError(ErrorCode.INVALID_INPUT, f"Malformed JSON request body: {exc}") from exc

    def do_OPTIONS(self) -> None:
        """Handle browser CORS preflight requests."""
        try:
            self.server.security.validate_host(self.headers)
            origin = self.headers.get("Origin") or self.headers.get("origin")
            if not origin:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            clean_origin = origin.strip().lower()
            if clean_origin not in self.server.security.allowed_origins:
                raise ForgeError(ErrorCode.PERMISSION_DENIED, f"Preflight rejected: Origin '{origin}' not authorized.")

            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_and_security_headers()
            self.end_headers()
        except ForgeError as exc:
            self.send_forge_error(exc)
        except Exception as exc:
            logger.exception("Unexpected error in do_OPTIONS: %s", exc)
            self.send_forge_error(ForgeError(ErrorCode.IO_ERROR, "Internal server error."))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        try:
            # Enforce Host, Origin and CSRF validation before routing
            self.server.security.validate_origin_and_csrf(method, self.headers)

            parsed_url = urllib.parse.urlparse(self.path)
            path = parsed_url.path.rstrip("/")
            query = urllib.parse.parse_qs(parsed_url.query)

            # Route mapping
            if method == "GET":
                if path == "" or path == "/index.html":
                    index_file = STATIC_DIR / "index.html"
                    if not index_file.exists():
                        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, "index.html not found.")
                    self.send_bytes(HTTPStatus.OK.value, index_file.read_bytes(), "text/html; charset=utf-8")
                    return

                if path.startswith("/static/"):
                    rel_path = path[len("/static/"):]
                    target_file = (STATIC_DIR / rel_path).resolve()
                    validate_path_containment(STATIC_DIR, target_file)
                    if not target_file.exists() or not target_file.is_file():
                        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Static file '{rel_path}' not found.")
                    content_type = STATIC_MIME_TYPES.get(target_file.suffix.lower(), "application/octet-stream")
                    self.send_bytes(HTTPStatus.OK.value, target_file.read_bytes(), content_type)
                    return

                if path == "/api/health":
                    self.send_json(HTTPStatus.OK.value, {
                        "status": "ok",
                        "version": __version__,
                        "loopback_only": not self.server.security.allow_insecure_remote,
                    })
                    return

                if path == "/api/csrf-token":
                    self.send_json(HTTPStatus.OK.value, {
                        "csrf_token": self.server.security.csrf_token,
                    })
                    return

                if path == '/api/video-capabilities':
                    from ro_sprite_forge.adapters.video import capabilities
                    self.send_json(200, capabilities())
                    return

                m_video = re.fullmatch(r'/api/projects/([^/]+)/video-imports', path)
                if m_video:
                    from ro_sprite_forge.service.media import wire_record
                    project = load_project(self.server.projects_dir, m_video.group(1), verify_blobs=False)
                    self.send_json(200, dict(collections=wire_record(project.get('video_imports', [])),
                        sources=[s for s in project['sources'].values() if s.get('kind') == 'VIDEO']))
                    return

                if path == "/api/actors":
                    self.send_json(HTTPStatus.OK.value, {
                        "actors": [
                            {"id": "player", "name": "Player Character", "category": "player", "parts": ["body", "head"]},
                            {"id": "monster", "name": "Monster / Creature", "category": "monster", "parts": ["body"]},
                            {"id": "npc", "name": "NPC", "category": "npc", "parts": ["body"]},
                            {"id": "unverified", "name": "Unverified Actor", "category": "unverified", "parts": ["body"]},
                        ]
                    })
                    return

                if path == "/api/profiles":
                    self.send_json(HTTPStatus.OK.value, {
                        "profiles": [
                            {"id": "player", "name": "Korangar Player Profile (8 directions)", "category": "player", "views": 8},
                            {"id": "monster", "name": "Korangar Monster Profile (8 directions)", "category": "monster", "views": 8},
                            {"id": "npc", "name": "Korangar NPC Profile (8 directions)", "category": "npc", "views": 8},
                            {"id": "unverified", "name": "Unverified Profile", "category": "unverified", "views": 8},
                        ]
                    })
                    return

                if path == "/api/projects":
                    projects = list_projects(self.server.projects_dir)
                    self.send_json(HTTPStatus.OK.value, {"projects": projects})
                    return

                m_workspace = re.fullmatch(r"/api/projects/([^/]+)/workspace", path)
                if m_workspace:
                    from ro_sprite_forge.service.workbench import workspace
                    manifest = load_project(self.server.projects_dir, m_workspace.group(1), verify_blobs=False)
                    self.send_json(200, workspace(self.server.projects_dir, manifest))
                    return

                # GET /api/projects/{project_id}/requirements
                m_req = re.match(r"^/api/projects/([^/]+)/requirements$", path)
                if m_req:
                    project_id = m_req.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    project_dir = self.server.projects_dir / project_id
                    resolved_reqs, _ = _resolve_project_requirements(project_dir, manifest)
                    if resolved_reqs is None:
                        self.send_json(HTTPStatus.OK.value, {
                            "resolved": False,
                            "project_id": project_id,
                            "reason": "NO_TARGET_DECLARED",
                            "message": "No target declared for this project yet. Please define target and layer topology.",
                        })
                    else:
                        self.send_json(HTTPStatus.OK.value, {
                            "resolved": True,
                            "project_id": project_id,
                            "requirements": resolved_reqs,
                        })
                    return

                # GET /api/projects/{project_id}/coverage
                m_cov = re.match(r"^/api/projects/([^/]+)/coverage$", path)
                if m_cov:
                    project_id = m_cov.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    project_dir = self.server.projects_dir / project_id
                    coverage_report = _evaluate_project_coverage(project_dir, manifest)
                    if coverage_report is None:
                        self.send_json(HTTPStatus.OK.value, {
                            "evaluated": False,
                            "project_id": project_id,
                            "reason": "NO_TARGET_DECLARED",
                            "message": "Coverage evaluation requires an active target declaration.",
                        })
                    else:
                        self.send_json(HTTPStatus.OK.value, {
                            "evaluated": True,
                            "project_id": project_id,
                            "coverage": coverage_report,
                        })
                    return

                # GET /api/projects/{project_id}/work-order
                m_wo = re.match(r"^/api/projects/([^/]+)/work-order$", path)
                if m_wo:
                    project_id = m_wo.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    project_dir = self.server.projects_dir / project_id
                    coverage_report = _evaluate_project_coverage(project_dir, manifest)
                    if coverage_report is None:
                        raise ForgeError(ErrorCode.INVALID_INPUT, "Cannot generate work order: target is not declared.")

                    fmt = query.get("format", ["text"])[0].lower()
                    if fmt == "json":
                        self.send_json(HTTPStatus.OK.value, {
                            "project_id": project_id,
                            "counts": coverage_report["counts"],
                            "status": coverage_report["status"],
                            "unresolved_items": coverage_report["unresolved_items"],
                            "excluded_actions": coverage_report["excluded_actions"],
                        })
                    else:
                        wo_text = format_work_order(coverage_report)
                        self.send_bytes(HTTPStatus.OK.value, wo_text.encode("utf-8"), "text/plain; charset=utf-8")
                    return

                # GET /api/projects/{project_id}/sequences
                m_seqs = re.match(r"^/api/projects/([^/]+)/sequences$", path)
                if m_seqs:
                    project_id = m_seqs.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    self.send_json(HTTPStatus.OK.value, {
                        "project_id": project_id,
                        "sequences": manifest.get("sequences", []),
                    })
                    return

                # GET /api/projects/{project_id}/extractions
                m_exts = re.match(r"^/api/projects/([^/]+)/extractions$", path)
                if m_exts:
                    project_id = m_exts.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    self.send_json(HTTPStatus.OK.value, {
                        "project_id": project_id,
                        "extractions": manifest.get("extractions", []),
                    })
                    return

                # GET /api/projects/{project_id}/recipes
                m_recipes = re.match(r"^/api/projects/([^/]+)/recipes$", path)
                if m_recipes:
                    project_id = m_recipes.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    self.send_json(HTTPStatus.OK.value, {
                        "project_id": project_id,
                        "recipes": manifest.get("recipes", []),
                    })
                    return

                # GET /api/projects/{project_id}/compilations
                m_comps = re.match(r"^/api/projects/([^/]+)/compilations$", path)
                if m_comps:
                    project_id = m_comps.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    self.send_json(HTTPStatus.OK.value, {
                        "project_id": project_id,
                        "compilations": manifest.get("compilations", []),
                    })
                    return

                # GET /api/projects/{project_id}
                m_proj = re.match(r"^/api/projects/([^/]+)$", path)
                if m_proj:
                    project_id = m_proj.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    self.send_json(HTTPStatus.OK.value, manifest)
                    return

                # GET /api/projects/{project_id}/blobs/{sha256}
                m_blob = re.match(r"^/api/projects/([^/]+)/blobs/([0-9a-fA-F]{64})$", path)
                if m_blob:
                    project_id = m_blob.group(1)
                    sha256_hash = m_blob.group(2)
                    blob_bytes = get_blob(self.server.projects_dir, project_id, sha256_hash)
                    self.send_bytes(HTTPStatus.OK.value, blob_bytes, "application/octet-stream")
                    return

            elif method == "POST":
                m_video = re.fullmatch(r'/api/projects/([^/]+)/(video-metadata|video-frames|video-preview|video-stage)', path)
                if m_video:
                    from ro_sprite_forge.service.media import media_operation
                    result = media_operation(self.server.projects_dir, m_video.group(1),
                                             m_video.group(2), self.read_json_body())
                    self.send_json(200, result)
                    return
                m_operation = re.fullmatch(r"/api/projects/([^/]+)/(target|import-pair|assign|stage-sequence|stage-png|extract-spritesheet|apply-transform|compile|compile-plan|preview|compare|source-preview|transform-preview|review-proposal|review)", path)
                if m_operation:
                    from ro_sprite_forge.service import workbench
                    manifest = load_project(self.server.projects_dir, m_operation.group(1), verify_blobs=False)
                    data = self.read_json_body()
                    operation = m_operation.group(2)
                    try:
                        if operation in ('target','import-pair','assign','stage-sequence','stage-png','extract-spritesheet','apply-transform','compile'):
                            result = workbench.mutate(self.server.projects_dir, manifest, operation, data)
                        else:
                            function = {'preview': workbench.preview, 'compare': workbench.comparison,
                                        'source-preview': workbench.source_preview,
                                        'transform-preview': workbench.transform_preview,
                                        'compile-plan': workbench.compile_plan,
                                        'review-proposal': workbench.review_proposal,
                                        'review': workbench.record_review}[operation]
                            result = function(self.server.projects_dir, manifest, data)
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Invalid workbench input: ' + str(exc)) from exc
                    self.send_json(200, result)
                    return

                # POST /api/projects
                if path == "/api/projects":
                    data = self.read_json_body()
                    project_id = data.get("project_id")
                    name = data.get("name")
                    actor = data.get("actor")
                    profile = data.get("profile")

                    if not project_id or not name or not actor or not profile:
                        raise ForgeError(
                            ErrorCode.INVALID_ARGUMENT,
                            "Missing required fields: project_id, name, actor, and profile are mandatory.",
                        )

                    if any(a.get('review') for a in (data.get('ledger') or {}).get('assignments', [])):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use explicit review proposals to record decisions.')
                    manifest = create_project(
                        self.server.projects_dir,
                        project_id,
                        name,
                        actor,
                        profile,
                        target=data.get("target"),
                        ledger=data.get("ledger"),
                        inventory=data.get("inventory"),
                    )
                    self.send_json(HTTPStatus.CREATED.value, manifest)
                    return

                # POST /api/projects/{project_id}/blobs
                m_blob_import = re.match(r"^/api/projects/([^/]+)/blobs$", path)
                if m_blob_import:
                    project_id = m_blob_import.group(1)
                    content_type = self.headers.get("Content-Type", "")

                    if "application/json" in content_type:
                        payload = self.read_json_body()
                        filename = payload.get("filename")
                        b64_data = payload.get("data_base64")
                        expected_hash = payload.get("expected_sha256")
                        if not filename or b64_data is None:
                            raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Missing filename or data_base64 in JSON payload.")
                        try:
                            blob_bytes = base64.b64decode(b64_data, validate=True)
                        except Exception as exc:
                            raise ForgeError(ErrorCode.INVALID_INPUT, f"Invalid base64 payload: {exc}") from exc
                    else:
                        # Raw binary upload
                        blob_bytes = self.read_request_body()
                        filename = (
                            self.headers.get("X-Filename")
                            or (query.get("filename", [None])[0])
                            or "unnamed.blob"
                        )
                        expected_hash = (
                            self.headers.get("X-Expected-Sha256")
                            or (query.get("expected_sha256", [None])[0])
                        )

                    result = import_blob(
                        self.server.projects_dir,
                        project_id,
                        filename,
                        blob_bytes,
                        expected_sha256=expected_hash,
                    )
                    self.send_json(HTTPStatus.CREATED.value, result)
                    return

                # POST /api/projects/{project_id}/validate
                m_val = re.match(r"^/api/projects/([^/]+)/validate$", path)
                if m_val:
                    project_id = m_val.group(1)
                    manifest = load_project(self.server.projects_dir, project_id, verify_blobs=True)
                    self.send_json(HTTPStatus.OK.value, {
                        "valid": True,
                        "project_id": project_id,
                        "revision": manifest["revision"],
                        "schema": manifest["schema"],
                        "canonical_sha256": manifest["canonical_sha256"],
                        "sources_count": len(manifest.get("sources", {})),
                        "reviews_count": len(manifest.get("reviews", {})),
                    })
                    return

            elif method == "PUT":
                # PUT /api/projects/{project_id}
                m_save = re.match(r"^/api/projects/([^/]+)$", path)
                if m_save:
                    project_id = m_save.group(1)
                    payload = self.read_json_body()
                    expected_rev = payload.get("expected_revision")
                    project_data = payload.get("project")

                    if expected_rev is None or project_data is None:
                        raise ForgeError(
                            ErrorCode.INVALID_ARGUMENT,
                            "Missing required fields: expected_revision and project object are required.",
                        )
                    if not isinstance(expected_rev, int):
                        raise ForgeError(ErrorCode.INVALID_ARGUMENT, "expected_revision must be an integer.")

                    if project_data.get("project_id") != project_id:
                        raise ForgeError(
                            ErrorCode.INVALID_ARGUMENT,
                            f"Path project_id '{project_id}' does not match body project_id '{project_data.get('project_id')}'.",
                        )

                    from ro_sprite_forge.service.workbench import workspace
                    existing = load_project(self.server.projects_dir, project_id, verify_blobs=False)
                    from ro_sprite_forge.service.media import browser_safe
                    incoming_video = project_data.get('video_imports', [])
                    original_video = existing.get('video_imports', [])
                    if incoming_video != original_video and incoming_video != browser_safe(original_video):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use validated video-stage operations; video provenance is immutable.')
                    if 'video_imports' in existing:
                        project_data['video_imports'] = original_video
                    if project_data.get('resources', []) != existing.get('resources', []):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use the validated import-pair operation to add immutable resources.')
                    if project_data.get('review_events',[]) != existing.get('review_events',[]) or project_data.get('reviews',{}) != existing.get('reviews',{}):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use the validated review operation; review history is immutable.')
                    if project_data.get('sequences', []) != existing.get('sequences', []):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use validated stage-sequence operations to manage sequences.')
                    if project_data.get('extractions', []) != existing.get('extractions', []):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use validated extract-spritesheet operations to manage extractions.')
                    if project_data.get('recipes', []) != existing.get('recipes', []):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use validated apply-transform operations to manage recipes.')
                    if project_data.get('compilations', []) != existing.get('compilations', []):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use validated compile operations to manage compilations.')
                    # Generic save cannot bypass ledger validation/revision/invalidation.
                    if project_data.get('ledger') != existing.get('ledger') or project_data.get('target') != existing.get('target'):
                        raise ForgeError(ErrorCode.INVALID_INPUT, 'Use validated assignment/target operations.')
                    workspace(self.server.projects_dir, project_data)
                    updated = save_project(self.server.projects_dir, project_data, expected_rev)
                    self.send_json(HTTPStatus.OK.value, updated)
                    return

            # Unknown route
            raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Resource not found: {method} {path}")

        except ForgeError as exc:
            self.send_forge_error(exc)
        except Exception as exc:
            logger.exception("Unhandled server exception: %s", exc)
            self.send_forge_error(ForgeError(ErrorCode.IO_ERROR, "An internal server error occurred."))


class ForgeServer(http.server.ThreadingHTTPServer):
    """Threaded HTTP server bound to loopback by default with strict security management."""

    def __init__(
        self,
        projects_dir: Path | str,
        host: str = "127.0.0.1",
        port: int = 8080,
        *,
        allow_insecure_remote: bool = False,
    ):
        self.projects_dir = Path(projects_dir).resolve()
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        # Security manager validates loopback before binding socket
        self.security = SecurityManager(host, port, allow_insecure_remote=allow_insecure_remote)

        super().__init__((host, port), ForgeRequestHandler)

        # Update actual bound port if port 0 was passed
        self.actual_port = self.server_address[1]
        if self.actual_port != port:
            self.security.port = self.actual_port
            self.security._build_allowlists()

    @property
    def url(self) -> str:
        return f"http://{self.security.host}:{self.actual_port}"


def create_server(
    projects_dir: Path | str,
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    allow_insecure_remote: bool = False,
) -> ForgeServer:
    """Factory helper to create a configured ForgeServer instance."""
    return ForgeServer(projects_dir, host=host, port=port, allow_insecure_remote=allow_insecure_remote)
