"""Public behavior tests for shared IM HTTP transport normalization."""

from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("configured_url", "expected"),
    [
        ("http://im.local:8011/", "http://im.local:8011"),
        ("https://im.example.com/base/", "https://im.example.com/base"),
        ("ws://im.local:8011/im/ws/gateway", "http://im.local:8011/im/ws/gateway"),
        ("wss://im.example.com/im/ws/gateway", "https://im.example.com/im/ws/gateway"),
    ],
)
def test_im_http_base_url_normalizes_http_and_websocket_schemes(
    configured_url: str,
    expected: str,
) -> None:
    transport = import_module("personal_assistant.gateway.im_http_transport")

    assert transport.normalize_im_http_base_url(configured_url) == expected


def test_im_http_base_url_rejects_non_http_transport() -> None:
    transport = import_module("personal_assistant.gateway.im_http_transport")

    with pytest.raises(ValueError, match=r"http\(s\) or ws\(s\)"):
        transport.normalize_im_http_base_url("ftp://im.example.com")


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (None, {"User-Agent": "nano-multiagent-gateway-bootstrap"}),
        (
            "token-a",
            {
                "User-Agent": "nano-multiagent-gateway-bootstrap",
                "Authorization": "Bearer token-a",
            },
        ),
    ],
)
def test_im_http_headers_preserve_bootstrap_identity_and_auth(
    token: str | None,
    expected: dict[str, str],
) -> None:
    transport = import_module("personal_assistant.gateway.im_http_transport")

    assert transport.build_im_http_headers(token) == expected
