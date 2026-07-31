"""Thin HTTP client for driving Open WebUI during end-to-end tests.

Open WebUI keeps its admin configuration behind bearer-token endpoints, so the
end-to-end suite talks to the API for setup and assertions and reserves the
browser for what actually needs rendering: the integrations page and charts.
"""

from __future__ import annotations

import os
import time

import requests

DEFAULT_BASE_URL = "http://openwebui.localhost"

# CI starts from an empty volume so the suite creates its own admin. Point these
# at an existing account to run the suite against an already-provisioned instance.
ADMIN_NAME = os.environ.get("E2E_ADMIN_NAME", "E2E Admin")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e@example.com")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "e2e-password-123")

MCP_URL = "http://mcp:8000/mcp"

# Mirrors the connection seeded by webui-init.py / TOOL_SERVER_CONNECTIONS.
# `path` is required by Open WebUI's ToolServerConnection model - omitting it
# makes GET /api/v1/configs/tool_servers fail response validation with a 500.
MCP_CONNECTION = {
    "url": MCP_URL,
    "path": "openapi.json",
    "type": "mcp",
    "auth_type": "bearer",
    "headers": None,
    "key": "",
    "config": {"enable": True, "function_name_filter_list": "", "access_grants": []},
    "info": {"id": "1", "name": "postgres-mcp", "description": "Northwind PostgreSQL MCP"},
    "spec_type": "url",
    "spec": "",
}


def base_url() -> str:
    return os.environ.get("WEBUI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


class WebUIClient:
    """Minimal authenticated client for the Open WebUI REST API."""

    def __init__(self, url: str | None = None) -> None:
        self.base_url = (url or base_url()).rstrip("/")
        self.session = requests.Session()
        self.token: str | None = None

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    # -- lifecycle ---------------------------------------------------------

    def wait_until_ready(self, timeout: int = 300) -> None:
        """Block until /health responds, so tests do not race container start."""
        deadline = time.time() + timeout
        last_error = "no attempt made"
        while time.time() < deadline:
            try:
                response = self.session.get(self.url("/health"), timeout=5)
                if response.ok:
                    return
                last_error = f"HTTP {response.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)
            time.sleep(2)
        raise TimeoutError(
            f"Open WebUI at {self.base_url} was not ready after {timeout}s (last: {last_error})"
        )

    def sign_in_or_up(self) -> str:
        """Sign in, creating the admin account on first run.

        Open WebUI never gates the *first* user on ENABLE_SIGNUP, so this works
        even though webui-init.py disables signup.
        """
        response = self.session.post(
            self.url("/api/v1/auths/signin"),
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=30,
        )
        if not response.ok:
            response = self.session.post(
                self.url("/api/v1/auths/signup"),
                json={"name": ADMIN_NAME, "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                timeout=30,
            )
            response.raise_for_status()

        self.token = response.json()["token"]
        return self.token

    # -- requests ----------------------------------------------------------

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("sign_in_or_up() must be called before authenticated requests")
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path: str, timeout: int = 60) -> requests.Response:
        return self.session.get(self.url(path), headers=self.auth_headers, timeout=timeout)

    def post(self, path: str, payload: dict, timeout: int = 120) -> requests.Response:
        return self.session.post(
            self.url(path), json=payload, headers=self.auth_headers, timeout=timeout
        )

    # -- domain helpers ----------------------------------------------------

    def tool_servers(self) -> requests.Response:
        return self.get("/api/v1/configs/tool_servers")

    def verify_tool_server(self, connection: dict | None = None) -> requests.Response:
        return self.post("/api/v1/configs/tool_servers/verify", connection or MCP_CONNECTION)

    def models(self) -> requests.Response:
        return self.get("/api/models")
