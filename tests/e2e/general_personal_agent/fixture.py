"""Authenticated clients and isolation validation for real PA evaluation fixtures."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

from tests.e2e.critical_paths._im_client import IMClient


class EvaluationClient(IMClient):
    """Renew the fixture login during long real-time observations without replaying actions."""

    def register_or_login(self, username, password, *, display_name=None):
        token = super().register_or_login(username, password, display_name=display_name)
        self._login = {"username": username, "password": password}
        self._logged_at = time.monotonic()
        return token

    @property
    def _auth_headers(self):
        if time.monotonic() - self._logged_at >= 300:
            response = self._http.post("/im/v1/auth/login", json=self._login)
            response.raise_for_status()
            self.token = response.json()["access_token"]
            self._logged_at = time.monotonic()
        return super()._auth_headers


def request(client, method, path, payload):
    """Use the authenticated public interface and preserve its real response."""
    response = client._http.request(
        method, path, headers=client._auth_headers, json=payload
    )
    response.raise_for_status()
    return response.json()


def validate_manifest(path: Path) -> dict:
    """Require the daily profile's isolated local node and PA binding."""
    manifest = json.loads(path.read_text())
    address = urlparse(manifest["im_url"])
    if address.hostname not in {"127.0.0.1", "localhost", "::1"} or address.port in {
        None,
        8011,
        5173,
    }:
        raise ValueError("evaluation requires a loopback isolated high-port IM")
    if (
        not manifest["node_id"].startswith("wt-")
        or not manifest["personal"]["agent_id"]
    ):
        raise ValueError("evaluation requires a daily worktree manifest")
    return manifest
