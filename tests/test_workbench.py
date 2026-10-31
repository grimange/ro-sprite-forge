"""Comprehensive test suite for Operator Workbench, Service Integration and Concurrency (RSF-16)."""

import base64
import concurrent.futures
from http import HTTPStatus
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, reference
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import (
    create_project,
    load_project,
    save_project,
)
from ro_sprite_forge.service.server import MAX_REQUEST_BODY_SIZE, create_server, make_standard_actor_doc


def make_target_doc(project_id: str, *, topology: bool = True, frame_count: int = 4, scope: str = "scoped") -> dict:
    profile = frozen_runtime_profile("player")
    actor_doc = make_standard_actor_doc(project_id, profile, parts=["body"])
    actor = load_actor(actor_doc)

    views = []
    for v in range(8):
        views.append({
            "view": v,
            "frame_count": frame_count,
            "topology": {"kind": "explicit", "layers": ["torso", "cloak"]} if topology else None,
        })

    return {
        "schema": "rsf.target/v2",
        "id": f"{project_id}-target",
        "revision": 1,
        "previous_sha256": None,
        "actor": reference(actor),
        "runtime_profile": reference(profile),
        "scope": scope,
        "parts": ["body"],
        "compatibility": {"status": "UNVERIFIED", "declarations": []},
        "actions": [
            {
                "id": "Walk",
                "requirement": "REQUIRED",
                "parts": [{"part": "body", "views": views}],
            }
        ],
    }


class WorkbenchServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="rsf16-test-")
        self.projects_dir = Path(self.temp_dir.name)
        self.server = create_server(self.projects_dir, host="127.0.0.1", port=0)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = self.server.url
        self.csrf_token = self.server.security.csrf_token

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)
        self.temp_dir.cleanup()

    def request(
        self,
        method: str,
        path: str,
        data: bytes | dict | None = None,
        headers: dict | None = None,
    ) -> tuple[int, dict | bytes, dict]:
        url = f"{self.base_url}{path}"
        req_headers = {
            "Host": f"127.0.0.1:{self.server.actual_port}",
            "Origin": f"http://127.0.0.1:{self.server.actual_port}",
        }
        if self.csrf_token and method in ("POST", "PUT", "DELETE"):
            req_headers["X-CSRF-Token"] = self.csrf_token

        body_bytes = None
        if isinstance(data, dict):
            body_bytes = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, bytes):
            body_bytes = data
            req_headers["Content-Type"] = "application/octet-stream"

        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                resp_bytes = resp.read()
                resp_headers = dict(resp.headers)
                content_type = resp_headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return status, json.loads(resp_bytes.decode("utf-8")), resp_headers
                return status, resp_bytes, resp_headers
        except urllib.error.HTTPError as exc:
            err_bytes = exc.read()
            resp_headers = dict(exc.headers)
            content_type = resp_headers.get("Content-Type", "")
            if "application/json" in content_type:
                return exc.code, json.loads(err_bytes.decode("utf-8")), resp_headers
            return exc.code, err_bytes, resp_headers

    def test_rsf15_correction_concurrent_save_conflict(self):
        """Verify per-project serialization ensures exactly one success and one HTTP 409 conflict."""
        project_id = "concurrent-proj"
        create_project(self.projects_dir, project_id, "Concurrent Project", "player", "player")

        def attempt_save(client_id: int):
            manifest = load_project(self.projects_dir, project_id, verify_blobs=False)
            updated = dict(manifest)
            updated["name"] = f"Updated by client {client_id}"
            return self.request(
                "PUT",
                f"/api/projects/{project_id}",
                {"expected_revision": 1, "project": updated},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(attempt_save, 1)
            fut2 = executor.submit(attempt_save, 2)
            res1 = fut1.result()
            res2 = fut2.result()

        statuses = sorted([res1[0], res2[0]])
        self.assertEqual(statuses, [200, 409], f"Expected exactly one 200 and one 409, got {statuses}")

        final_manifest = load_project(self.projects_dir, project_id, verify_blobs=False)
        self.assertEqual(final_manifest["revision"], 2)

    def test_rsf15_correction_upload_limit_reconciliation(self):
        """Verify MAX_REQUEST_BODY_SIZE allows up to 48 MiB while rejecting over-limit payloads."""
        self.assertEqual(MAX_REQUEST_BODY_SIZE, 48 * 1024 * 1024)

        project_id = "blob-proj"
        create_project(self.projects_dir, project_id, "Blob Project", "player", "player")

        # Directly verify server checks Content-Length and raises PAYLOAD_TOO_LARGE
        import http.client
        conn = http.client.HTTPConnection(f"127.0.0.1:{self.server.actual_port}")
        conn.putrequest("POST", f"/api/projects/{project_id}/blobs")
        conn.putheader("Host", f"127.0.0.1:{self.server.actual_port}")
        conn.putheader("Origin", f"http://127.0.0.1:{self.server.actual_port}")
        conn.putheader("X-CSRF-Token", self.csrf_token)
        conn.putheader("Content-Length", str(49 * 1024 * 1024))
        conn.putheader("X-Filename", "over.bin")
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual(resp.status, HTTPStatus.REQUEST_ENTITY_TOO_LARGE.value)
        conn.close()

    def test_static_files_serving(self):
        """Verify index.html, CSS and JS are served with correct MIME types and security headers."""
        # GET /
        status, content, headers = self.request("GET", "/")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"RO Sprite Forge", content)
        self.assertIn(b"Requirements Workbench", content)
        self.assertIn(b'role="tree"', content)
        self.assertIn(b'role="toolbar"', content)
        self.assertIn(b'badge badge-unsupported', content)
        self.assertIn(b'alert-warning', content)

        # GET /static/workbench.css
        status, content, headers = self.request("GET", "/static/workbench.css")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertIn("text/css", headers.get("Content-Type", ""))
        self.assertIn(b"--status-underspecified-bg", content)
        self.assertIn(b"*:focus-visible", content)

        # GET /static/workbench.js
        status, content, headers = self.request("GET", "/static/workbench.js")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertIn("application/javascript", headers.get("Content-Type", ""))
        self.assertIn(b'treeitem', content)
        self.assertIn(b"UNDERSPECIFIED_LAYER_TOPOLOGY", content)

    def test_static_file_traversal_protection(self):
        """Verify directory traversal escapes from /static/ are strictly rejected."""
        status, _, _ = self.request("GET", "/static/../schemas/project-v1.json")
        self.assertIn(status, (HTTPStatus.FORBIDDEN.value, HTTPStatus.NOT_FOUND.value))

    def test_actors_and_profiles_endpoints(self):
        """Verify /api/actors and /api/profiles endpoints return standard templates."""
        status, data, _ = self.request("GET", "/api/actors")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertIn("actors", data)
        categories = {a["category"] for a in data["actors"]}
        self.assertTrue({"player", "monster", "npc", "unverified"}.issubset(categories))

        status, data, _ = self.request("GET", "/api/profiles")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertIn("profiles", data)
        p_categories = {p["category"] for p in data["profiles"]}
        self.assertTrue({"player", "monster", "npc", "unverified"}.issubset(p_categories))

    def test_requirements_endpoint_without_target(self):
        """Verify /api/projects/{id}/requirements returns clean diagnostic when target not declared."""
        project_id = "no-target-proj"
        create_project(self.projects_dir, project_id, "No Target Project", "player", "player")

        status, data, _ = self.request("GET", f"/api/projects/{project_id}/requirements")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertFalse(data["resolved"])
        self.assertEqual(data["reason"], "NO_TARGET_DECLARED")

    def test_requirements_endpoint_with_explicit_topology(self):
        """Verify /api/projects/{id}/requirements resolves topology into canonical tree."""
        project_id = "walk-proj"
        target_doc = make_target_doc(project_id, topology=True, frame_count=4)
        create_project(self.projects_dir, project_id, "Walk Project", "player", "player", target=target_doc)

        status, data, _ = self.request("GET", f"/api/projects/{project_id}/requirements")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertTrue(data["resolved"])
        reqs = data["requirements"]
        self.assertEqual(reqs["schema"], "rsf.resolved-requirements/v1")
        self.assertEqual(len(reqs["slots"]), 8)
        self.assertEqual(len(reqs["frames"]), 32)
        self.assertEqual(len(reqs["layers"]), 64)

    def test_coverage_and_work_order_with_unassigned_layers(self):
        """Verify /api/projects/{id}/coverage reports unassigned occurrences and work order can be exported."""
        project_id = "cov-proj"
        target_doc = make_target_doc(project_id, topology=True, frame_count=4)
        create_project(self.projects_dir, project_id, "Coverage Project", "player", "player", target=target_doc)

        # GET /api/projects/{id}/coverage
        status, data, _ = self.request("GET", f"/api/projects/{project_id}/coverage")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertTrue(data["evaluated"])
        report = data["coverage"]
        self.assertEqual(report["counts"]["assignments"]["unassigned"], 64)
        self.assertEqual(report["status"]["assignment_coverage"], "UNASSIGNED")
        self.assertEqual(report["status"]["technical_validation"], "NOT_RUN")
        self.assertEqual(report["status"]["preview_fidelity"], "UNVERIFIED")
        self.assertEqual(report["status"]["native_evidence"], "UNVERIFIED")

        # GET /api/projects/{id}/work-order (JSON format)
        status, data_json, _ = self.request("GET", f"/api/projects/{project_id}/work-order?format=json")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertEqual(len(data_json["unresolved_items"]), 64)
        self.assertEqual(data_json["status"]["assignment_coverage"], "UNASSIGNED")

        # GET /api/projects/{id}/work-order (Text format)
        status, data_txt, headers = self.request("GET", f"/api/projects/{project_id}/work-order?format=text")
        self.assertEqual(status, HTTPStatus.OK.value)
        self.assertIn("text/plain", headers.get("Content-Type", ""))
        self.assertIn(b"Missing-Art Work Order", data_txt)
        self.assertIn(b"Walk", data_txt)
        self.assertIn(b"SUPPLY_ARTWORK", data_txt)

    def test_work_order_without_target_fails_cleanly(self):
        """Verify requesting work order on a project without a target raises typed error."""
        project_id = "empty-proj"
        create_project(self.projects_dir, project_id, "Empty Project", "player", "player")

        status, data, _ = self.request("GET", f"/api/projects/{project_id}/work-order")
        self.assertEqual(status, HTTPStatus.UNPROCESSABLE_ENTITY.value)
        self.assertEqual(data["error"]["code"], ErrorCode.INVALID_INPUT.value)


if __name__ == "__main__":
    unittest.main()
