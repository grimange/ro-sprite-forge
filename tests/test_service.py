"""Comprehensive HTTP service, security and API endpoint tests (RSF-15)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from ro_sprite_forge import __version__
from ro_sprite_forge.core.canonical import digest
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.service.security import SecurityManager
from ro_sprite_forge.service.server import MAX_REQUEST_BODY_SIZE, create_server


class ServiceSecurityAndApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="rsf-http-test-")
        cls.projects_dir = Path(cls.temp_dir.name).resolve()

        # Start loopback server with dynamic port
        cls.server = create_server(cls.projects_dir, host="127.0.0.1", port=0)
        cls.port = cls.server.actual_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.default_host = f"127.0.0.1:{cls.port}"
        cls.default_origin = f"http://127.0.0.1:{cls.port}"

        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp_dir.cleanup()

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        data: bytes | dict | None = None,
        headers: dict[str, str] | None = None,
        raw_headers: bool = False,
    ) -> tuple[int, bytes, dict[str, str]]:
        url = f"{self.base_url}{path}"
        req_headers = {}
        if not raw_headers:
            req_headers["Host"] = self.default_host
        if headers:
            req_headers.update(headers)

        body_bytes = None
        if data is not None:
            if isinstance(data, dict):
                body_bytes = json.dumps(data).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")
            else:
                body_bytes = data
                req_headers.setdefault("Content-Type", "application/octet-stream")

        req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                resp_headers = {k: v for k, v in resp.headers.items()}
                return resp.status, resp.read(), resp_headers
        except urllib.error.HTTPError as exc:
            resp_headers = {k: v for k, v in exc.headers.items()}
            content = exc.read()
            exc.close()
            return exc.code, content, resp_headers

    def _get_csrf_token(self) -> str:
        status, body, _ = self._request("/api/csrf-token")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        return data["csrf_token"]

    # -------------------------------------------------------------------------
    # PART A: BINDING & HOST SECURITY
    # -------------------------------------------------------------------------

    def test_non_loopback_binding_rejected_by_default(self):
        with self.assertRaises(ForgeError) as cm:
            SecurityManager("0.0.0.0", 8080, allow_insecure_remote=False)
        self.assertEqual(cm.exception.code, ErrorCode.PERMISSION_DENIED)

        with self.assertRaises(ForgeError) as cm:
            SecurityManager("192.168.1.100", 8080, allow_insecure_remote=False)
        self.assertEqual(cm.exception.code, ErrorCode.PERMISSION_DENIED)

        # Explicit allow_insecure_remote overrides
        sec = SecurityManager("0.0.0.0", 8080, allow_insecure_remote=True)
        self.assertTrue(sec.allow_insecure_remote)

    def test_missing_host_header_rejected(self):
        status, body, _ = self._request("/api/health", headers={"Host": ""}, raw_headers=True)
        self.assertEqual(status, 403)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "PERMISSION_DENIED")

    def test_dns_rebinding_host_header_rejected(self):
        hostile_hosts = ["evil-site.com", "attacker.local", "127.0.0.1.attacker.com", "localhost.evil.com"]
        for bad_host in hostile_hosts:
            with self.subTest(bad_host=bad_host):
                status, body, _ = self._request("/api/health", headers={"Host": bad_host}, raw_headers=True)
                self.assertEqual(status, 403)
                data = json.loads(body.decode("utf-8"))
                self.assertEqual(data["error"]["code"], "PERMISSION_DENIED")

    # -------------------------------------------------------------------------
    # PART B: ORIGIN & CORS PROTECTION
    # -------------------------------------------------------------------------

    def test_hostile_origin_rejected_on_get(self):
        status, body, _ = self._request("/api/health", headers={"Origin": "http://evil-site.com"})
        self.assertEqual(status, 403)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "PERMISSION_DENIED")

    def test_hostile_origin_rejected_on_post(self):
        token = self._get_csrf_token()
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data={"project_id": "proj", "name": "N", "actor": "A", "profile": "player"},
            headers={"Origin": "http://evil-site.com", "X-CSRF-Token": token},
        )
        self.assertEqual(status, 403)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "PERMISSION_DENIED")

    def test_preflight_cors_options(self):
        # Allowed origin preflight
        status, _, headers = self._request(
            "/api/projects",
            method="OPTIONS",
            headers={"Origin": self.default_origin},
        )
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), self.default_origin)
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("X-CSRF-Token", headers.get("Access-Control-Allow-Headers", ""))

        # Hostile origin preflight rejected
        status, body, _ = self._request(
            "/api/projects",
            method="OPTIONS",
            headers={"Origin": "http://malicious-web.com"},
        )
        self.assertEqual(status, 403)

    # -------------------------------------------------------------------------
    # PART C: CSRF PROTECTION
    # -------------------------------------------------------------------------

    def test_csrf_token_endpoint(self):
        status, body, _ = self._request("/api/csrf-token")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        token = data.get("csrf_token")
        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 32)

    def test_missing_csrf_token_on_mutation_rejected(self):
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data={"project_id": "p1", "name": "N", "actor": "A", "profile": "player"},
            headers={},  # Missing X-CSRF-Token
        )
        self.assertEqual(status, 403)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "PERMISSION_DENIED")
        self.assertIn("CSRF", data["error"]["message"])

    def test_invalid_csrf_token_on_mutation_rejected(self):
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data={"project_id": "p1", "name": "N", "actor": "A", "profile": "player"},
            headers={"X-CSRF-Token": "invalid-token-string"},
        )
        self.assertEqual(status, 403)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "PERMISSION_DENIED")

    # -------------------------------------------------------------------------
    # PART D: HEALTH & BASELINE HEADERS
    # -------------------------------------------------------------------------

    def test_health_endpoint(self):
        status, body, headers = self._request("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], __version__)
        self.assertTrue(data["loopback_only"])
        # Check security headers
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")

    # -------------------------------------------------------------------------
    # PART E: PROJECT LIFECYCLE (CREATE, LIST, GET, PUT, VALIDATE)
    # -------------------------------------------------------------------------

    def test_project_lifecycle_endpoints(self):
        token = self._get_csrf_token()

        # 1. Create project
        create_payload = {
            "project_id": "http_novice",
            "name": "HTTP Novice Project",
            "actor": "novice-male",
            "profile": "player",
        }
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data=create_payload,
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 201)
        created = json.loads(body.decode("utf-8"))
        self.assertEqual(created["project_id"], "http_novice")
        self.assertEqual(created["revision"], 1)

        # 2. Duplicate create fails with 409 Conflict
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data=create_payload,
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 409)

        # 3. List projects
        status, body, _ = self._request("/api/projects")
        self.assertEqual(status, 200)
        proj_list = json.loads(body.decode("utf-8"))["projects"]
        self.assertTrue(any(p["project_id"] == "http_novice" for p in proj_list))

        # 4. Get project
        status, body, _ = self._request("/api/projects/http_novice")
        self.assertEqual(status, 200)
        proj = json.loads(body.decode("utf-8"))
        self.assertEqual(proj["revision"], 1)

        # 5. Save project (revision 1 -> 2)
        proj["name"] = "Updated HTTP Novice"
        status, body, _ = self._request(
            "/api/projects/http_novice",
            method="PUT",
            data={"expected_revision": 1, "project": proj},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 200)
        saved = json.loads(body.decode("utf-8"))
        self.assertEqual(saved["revision"], 2)
        self.assertEqual(saved["name"], "Updated HTTP Novice")

        # 6. Save with stale expected_revision=1 fails with 409 Conflict
        status, body, _ = self._request(
            "/api/projects/http_novice",
            method="PUT",
            data={"expected_revision": 1, "project": proj},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 409)

        # 7. Validate endpoint
        status, body, _ = self._request(
            "/api/projects/http_novice/validate",
            method="POST",
            data={},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 200)
        val = json.loads(body.decode("utf-8"))
        self.assertTrue(val["valid"])
        self.assertEqual(val["revision"], 2)

    def test_missing_project_returns_404(self):
        status, body, _ = self._request("/api/projects/nonexistent_proj")
        self.assertEqual(status, 404)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "INPUT_NOT_FOUND")

    # -------------------------------------------------------------------------
    # PART F: BLOB IMPORT & RETRIEVAL (BINARY & JSON BASE64)
    # -------------------------------------------------------------------------

    def test_blob_binary_upload_and_download(self):
        token = self._get_csrf_token()
        # Create project first
        self._request(
            "/api/projects",
            method="POST",
            data={"project_id": "blob_proj", "name": "B", "actor": "orc", "profile": "monster"},
            headers={"X-CSRF-Token": token},
        )

        content = b"sample sprite content bytes 12345"
        expected_sha = digest(content)

        # Binary upload
        status, body, _ = self._request(
            "/api/projects/blob_proj/blobs",
            method="POST",
            data=content,
            headers={
                "X-CSRF-Token": token,
                "X-Filename": "monster.spr",
                "X-Expected-Sha256": expected_sha,
                "Content-Type": "application/octet-stream",
            },
        )
        self.assertEqual(status, 201)
        res = json.loads(body.decode("utf-8"))
        self.assertEqual(res["sha256"], expected_sha)
        self.assertEqual(res["size"], len(content))

        # Binary download
        status, get_body, headers = self._request(f"/api/projects/blob_proj/blobs/{expected_sha}")
        self.assertEqual(status, 200)
        self.assertEqual(get_body, content)
        self.assertEqual(headers.get("Content-Type"), "application/octet-stream")

    def test_blob_json_base64_upload(self):
        token = self._get_csrf_token()
        self._request(
            "/api/projects",
            method="POST",
            data={"project_id": "json_blob_proj", "name": "J", "actor": "orc", "profile": "monster"},
            headers={"X-CSRF-Token": token},
        )

        raw_data = b"base64 encoded blob test content"
        b64_data = base64.b64encode(raw_data).decode("ascii")
        expected_sha = digest(raw_data)

        status, body, _ = self._request(
            "/api/projects/json_blob_proj/blobs",
            method="POST",
            data={
                "filename": "head.act",
                "data_base64": b64_data,
                "expected_sha256": expected_sha,
            },
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(status, 201)
        res = json.loads(body.decode("utf-8"))
        self.assertEqual(res["sha256"], expected_sha)

    # -------------------------------------------------------------------------
    # PART G: ADVERSARIAL & BOUNDARY TESTING
    # -------------------------------------------------------------------------

    def test_oversized_request_body_rejected(self):
        token = self._get_csrf_token()
        # Declare Content-Length exceeding 16 MiB limit
        headers = {
            "Content-Length": str(MAX_REQUEST_BODY_SIZE + 1024),
            "X-CSRF-Token": token,
            "Host": self.default_host,
        }
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data=b"",
            headers=headers,
            raw_headers=True,
        )
        self.assertEqual(status, 413)

    def test_malformed_json_body_rejected(self):
        token = self._get_csrf_token()
        status, body, _ = self._request(
            "/api/projects",
            method="POST",
            data=b"{not valid json...",
            headers={"X-CSRF-Token": token, "Content-Type": "application/json"},
        )
        self.assertIn(status, (400, 422))
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "INVALID_INPUT")

    def test_unknown_endpoint_returns_404(self):
        status, body, _ = self._request("/api/unknown-endpoint-xyz")
        self.assertEqual(status, 404)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error"]["code"], "INPUT_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
