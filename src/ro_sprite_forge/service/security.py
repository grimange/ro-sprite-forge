"""Local HTTP service security: loopback binding, Host verification, Origin checks and CSRF protection (RSF-15).

Implements security boundaries for local-first single-operator tooling:
- Enforces loopback binding by default; rejects exposure to public/LAN interfaces.
- Protects against DNS rebinding attacks via strict Host header allowlists.
- Protects against cross-origin browser abuse via strict Origin validation (no wildcard CORS).
- Protects state-changing HTTP operations (POST, PUT, DELETE, PATCH) via cryptographically
  unpredictable CSRF tokens.
"""
from __future__ import annotations

import ipaddress
import secrets
from typing import Mapping

from ro_sprite_forge.core.errors import ErrorCode, ForgeError


class SecurityManager:
    """Manages security boundaries and request authorization for local HTTP service."""

    def __init__(self, host: str, port: int, *, allow_insecure_remote: bool = False):
        self.host = host
        self.port = port
        self.allow_insecure_remote = allow_insecure_remote
        self.csrf_token = secrets.token_urlsafe(32)

        self._validate_bind_address()
        self._build_allowlists()

    def _validate_bind_address(self) -> None:
        """Ensure the service binds only to loopback interfaces unless explicitly overridden."""
        if self.allow_insecure_remote:
            return

        clean_host = self.host.strip().lower()
        if clean_host in ("localhost", "127.0.0.1", "::1"):
            return

        try:
            ip = ipaddress.ip_address(clean_host)
            if ip.is_loopback:
                return
        except ValueError:
            pass

        raise ForgeError(
            ErrorCode.PERMISSION_DENIED,
            f"Binding to '{self.host}' rejected: only loopback interfaces (127.0.0.1, localhost, ::1) are permitted.",
        )

    def _build_allowlists(self) -> None:
        """Construct canonical allowed Host and Origin sets for this instance."""
        self.allowed_hosts: set[str] = set()
        self.allowed_origins: set[str] = set()

        host_candidates = ["127.0.0.1", "localhost", "[::1]", "::1"]
        if self.host not in host_candidates:
            host_candidates.append(self.host)

        for candidate in host_candidates:
            self.allowed_hosts.add(candidate.lower())
            self.allowed_hosts.add(f"{candidate}:{self.port}".lower())
            # Bracketed IPv6 variations
            if candidate == "::1":
                self.allowed_hosts.add(f"[::1]:{self.port}")

            # Origins
            origin_host = f"[{candidate}]" if ":" in candidate and not candidate.startswith("[") else candidate
            self.allowed_origins.add(f"http://{origin_host}:{self.port}".lower())
            self.allowed_origins.add(f"http://{origin_host}".lower())

    def validate_host(self, headers: Mapping[str, str]) -> None:
        """Validate the HTTP Host header against allowed local authorities."""
        host_header = headers.get("Host") or headers.get("host")
        if not host_header:
            raise ForgeError(ErrorCode.PERMISSION_DENIED, "Missing required 'Host' header.")

        clean_host = host_header.strip().lower()
        if clean_host not in self.allowed_hosts:
            raise ForgeError(
                ErrorCode.PERMISSION_DENIED,
                f"Unauthorized Host header '{host_header}': host does not match configured local authority.",
            )

    def validate_origin_and_csrf(self, method: str, headers: Mapping[str, str]) -> None:
        """Validate Host, browser Origin and CSRF token for incoming requests."""
        # Host header is always strictly validated first
        self.validate_host(headers)

        origin_header = headers.get("Origin") or headers.get("origin")
        clean_method = method.upper()

        # 1. Origin header validation (when present)
        if origin_header:
            clean_origin = origin_header.strip().lower()
            if clean_origin not in self.allowed_origins:
                raise ForgeError(
                    ErrorCode.PERMISSION_DENIED,
                    f"Cross-origin request rejected: Origin '{origin_header}' is not authorized.",
                )

        # 2. CSRF Token verification for state-changing HTTP methods
        if clean_method in ("POST", "PUT", "DELETE", "PATCH"):
            token_header = (
                headers.get("X-CSRF-Token")
                or headers.get("x-csrf-token")
                or headers.get("X-Csrf-Token")
            )
            if not token_header:
                raise ForgeError(
                    ErrorCode.PERMISSION_DENIED,
                    "CSRF protection: missing required 'X-CSRF-Token' header for state-changing request.",
                )

            if not secrets.compare_digest(token_header.strip(), self.csrf_token):
                raise ForgeError(
                    ErrorCode.PERMISSION_DENIED,
                    "CSRF protection: invalid 'X-CSRF-Token' header.",
                )

    def get_cors_headers(self, origin_header: str | None) -> dict[str, str]:
        """Generate safe, non-wildcard CORS headers matching allowed local origin."""
        if not origin_header:
            return {}

        clean_origin = origin_header.strip().lower()
        if clean_origin in self.allowed_origins:
            return {
                "Access-Control-Allow-Origin": origin_header.strip(),
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-CSRF-Token, X-Expected-Sha256, X-Filename",
                "Access-Control-Max-Age": "86400",
                "Vary": "Origin",
            }
        return {}
