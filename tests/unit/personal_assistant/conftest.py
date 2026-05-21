"""Conftest for personal_assistant unit tests.

Clears SOCKS/HTTP proxy env vars so httpx tests using non-local base URLs
don't fail with 'socksio not installed' when the dev environment has SOCKS
proxy configured (e.g. ALL_PROXY / HTTPS_PROXY pointing to a SOCKS server).
See regression.md §4.1.
"""

import pytest


@pytest.fixture(autouse=True)
def _clear_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "all_proxy", "https_proxy", "http_proxy"):
        monkeypatch.delenv(var, raising=False)
